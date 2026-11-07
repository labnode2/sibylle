// One WebSocket per tab (contracts/realtime.md): topics are followed while a screen needs them,
// and after a reconnection the client subscribes again and reloads what is on screen.
import { useEffect, useRef } from 'react';

import { queryClient } from '../app/queryClient';

export type RealtimeEvent = {
  topic: string;
  event: string;
  at?: string;
  data: Record<string, unknown>;
};

type Listener = (event: RealtimeEvent) => void;

type ServerMessage =
  | { type: 'ping' }
  | ({ type: 'event' } & RealtimeEvent)
  | { type: 'subscribed'; topics: string[] }
  | { type: 'error'; code: string; topic?: string };

export type RealtimeOptions = {
  url: () => string;
  createSocket?: (url: string) => WebSocket;
  /** Called after a reconnection, to reload the data on screen. */
  onReconnect?: () => void;
  /** Called when the server closes with 4401: the session is gone. */
  onUnauthenticated?: () => void;
  random?: () => number;
};

const CLOSE_UNAUTHENTICATED = 4401;
const FIRST_DELAY = 1000;
const MAX_DELAY = 30_000;

export class RealtimeClient {
  private socket: WebSocket | null = null;
  private readonly listeners = new Map<string, Set<Listener>>();
  private attempt = 0;
  private opened = false;
  private stopped = false;
  private timer: ReturnType<typeof setTimeout> | null = null;

  constructor(private readonly options: RealtimeOptions) {}

  /** Follows a topic; the returned function stops following it. */
  subscribe(topic: string, listener: Listener): () => void {
    let set = this.listeners.get(topic);
    if (!set) {
      set = new Set();
      this.listeners.set(topic, set);
      this.send({ type: 'subscribe', topics: [topic] });
    }
    set.add(listener);
    this.ensureConnected();
    return () => {
      set.delete(listener);
      if (set.size === 0 && this.listeners.get(topic) === set) {
        this.listeners.delete(topic);
        this.send({ type: 'unsubscribe', topics: [topic] });
      }
    };
  }

  /** Reconnects after a new sign-in. */
  restart(): void {
    this.stopped = false;
    this.ensureConnected();
  }

  close(): void {
    this.stopped = true;
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
    this.socket?.close();
    this.socket = null;
  }

  private ensureConnected(): void {
    if (!this.socket && !this.timer && !this.stopped) this.connect();
  }

  private send(message: object): void {
    if (this.socket?.readyState === WebSocket.OPEN) this.socket.send(JSON.stringify(message));
  }

  private connect(): void {
    const create = this.options.createSocket ?? ((url: string) => new WebSocket(url));
    const socket = create(this.options.url());
    this.socket = socket;

    socket.onopen = () => {
      const reconnected = this.opened;
      this.opened = true;
      this.attempt = 0;
      const topics = [...this.listeners.keys()];
      if (topics.length) this.send({ type: 'subscribe', topics });
      if (reconnected) this.options.onReconnect?.();
    };

    socket.onmessage = (message: MessageEvent) => {
      let data: ServerMessage;
      try {
        data = JSON.parse(String(message.data)) as ServerMessage;
      } catch {
        return;
      }
      if (data.type === 'ping') {
        this.send({ type: 'pong' });
      } else if (data.type === 'event') {
        for (const listener of this.listeners.get(data.topic) ?? []) {
          listener({ topic: data.topic, event: data.event, at: data.at, data: data.data });
        }
      }
    };

    socket.onclose = (event: CloseEvent) => {
      if (this.socket === socket) this.socket = null;
      if (this.stopped) return;
      if (event.code === CLOSE_UNAUTHENTICATED) {
        this.stopped = true;
        this.options.onUnauthenticated?.();
        return;
      }
      this.scheduleReconnect();
    };
  }

  private scheduleReconnect(): void {
    const random = this.options.random ?? Math.random;
    const base = Math.min(MAX_DELAY, FIRST_DELAY * 2 ** this.attempt);
    const delay = Math.round(base * (0.8 + random() * 0.4));
    this.attempt += 1;
    this.timer = setTimeout(() => {
      this.timer = null;
      if (!this.stopped) this.connect();
    }, delay);
  }
}

export const realtime = new RealtimeClient({
  url: () =>
    `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/api/ws`,
  onReconnect: () => void queryClient.invalidateQueries(),
  // A session that ended elsewhere (signed out, or closed by Keycloak): sign in again, then back.
  onUnauthenticated: () => {
    const { pathname, search } = window.location;
    if (!pathname.startsWith('/connexion')) {
      window.location.assign(`/connexion?${new URLSearchParams({ suite: pathname + search })}`);
    }
  },
});

/** Calls `onEvent` for each event of the topic while the component is on screen. */
export function useTopic(
  topic: string | null | undefined,
  onEvent: (event: RealtimeEvent) => void,
) {
  const handler = useRef(onEvent);
  useEffect(() => {
    handler.current = onEvent;
  });
  useEffect(() => {
    if (!topic) return;
    return realtime.subscribe(topic, (event) => handler.current(event));
  }, [topic]);
}
