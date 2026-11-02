import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { RealtimeClient, type RealtimeEvent } from '../../src/api/realtime';

class FakeSocket {
  static instances: FakeSocket[] = [];
  readyState = 0;
  sent: unknown[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((message: { data: string }) => void) | null = null;
  onclose: ((event: { code: number }) => void) | null = null;

  constructor(readonly url: string) {
    FakeSocket.instances.push(this);
  }

  send(data: string) {
    this.sent.push(JSON.parse(data));
  }

  close() {
    this.readyState = 3;
  }

  open() {
    this.readyState = 1;
    this.onopen?.();
  }

  receive(message: object) {
    this.onmessage?.({ data: JSON.stringify(message) });
  }

  drop(code = 1006) {
    this.readyState = 3;
    this.onclose?.({ code });
  }
}

const last = () => FakeSocket.instances[FakeSocket.instances.length - 1]!;

function makeClient(extra: Partial<ConstructorParameters<typeof RealtimeClient>[0]> = {}) {
  return new RealtimeClient({
    url: () => 'ws://test/api/ws',
    createSocket: (url) => new FakeSocket(url) as unknown as WebSocket,
    random: () => 0.5,
    ...extra,
  });
}

describe('RealtimeClient', () => {
  beforeEach(() => {
    FakeSocket.instances = [];
    vi.useFakeTimers();
    vi.stubGlobal('WebSocket', { OPEN: 1 });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('connects on the first subscription and subscribes once open', () => {
    const client = makeClient();
    client.subscribe('org:1', () => {});
    expect(FakeSocket.instances).toHaveLength(1);
    last().open();
    expect(last().sent).toEqual([{ type: 'subscribe', topics: ['org:1'] }]);
  });

  it('answers pings and hands events to the topic listeners', () => {
    const client = makeClient();
    const received: RealtimeEvent[] = [];
    client.subscribe('prono:7', (event) => received.push(event));
    client.subscribe('org:1', () => {
      throw new Error('wrong topic');
    });
    last().open();
    last().receive({ type: 'ping' });
    last().receive({ type: 'event', topic: 'prono:7', event: 'bet.placed', data: { pot: 40 } });
    expect(last().sent).toContainEqual({ type: 'pong' });
    expect(received).toEqual([
      { topic: 'prono:7', event: 'bet.placed', at: undefined, data: { pot: 40 } },
    ]);
  });

  it('unsubscribes when the last listener leaves', () => {
    const client = makeClient();
    const stopA = client.subscribe('org:1', () => {});
    const stopB = client.subscribe('org:1', () => {});
    last().open();
    stopA();
    expect(last().sent).not.toContainEqual({ type: 'unsubscribe', topics: ['org:1'] });
    stopB();
    expect(last().sent).toContainEqual({ type: 'unsubscribe', topics: ['org:1'] });
  });

  it('reconnects with a growing delay, then subscribes again and reloads', () => {
    const onReconnect = vi.fn();
    const client = makeClient({ onReconnect });
    client.subscribe('org:1', () => {});
    last().open();

    last().drop();
    vi.advanceTimersByTime(999);
    expect(FakeSocket.instances).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(FakeSocket.instances).toHaveLength(2);

    last().drop(); // the second attempt fails too: wait 2 s
    vi.advanceTimersByTime(1999);
    expect(FakeSocket.instances).toHaveLength(2);
    vi.advanceTimersByTime(1);
    expect(FakeSocket.instances).toHaveLength(3);

    last().open();
    expect(last().sent).toEqual([{ type: 'subscribe', topics: ['org:1'] }]);
    expect(onReconnect).toHaveBeenCalledTimes(1);
  });

  it('caps the delay at 30 seconds', () => {
    const client = makeClient();
    client.subscribe('org:1', () => {});
    for (let i = 0; i < 8; i += 1) {
      last().drop();
      vi.runOnlyPendingTimers();
    }
    const before = FakeSocket.instances.length;
    last().drop();
    vi.advanceTimersByTime(29_999);
    expect(FakeSocket.instances).toHaveLength(before);
    vi.advanceTimersByTime(1);
    expect(FakeSocket.instances).toHaveLength(before + 1);
  });

  it('stops and reports a lost session on 4401', () => {
    const onUnauthenticated = vi.fn();
    const client = makeClient({ onUnauthenticated });
    client.subscribe('org:1', () => {});
    last().open();
    last().drop(4401);
    vi.advanceTimersByTime(60_000);
    expect(onUnauthenticated).toHaveBeenCalledTimes(1);
    expect(FakeSocket.instances).toHaveLength(1);
    client.restart();
    expect(FakeSocket.instances).toHaveLength(2);
  });
});
