// What finding the word pays now: 50 laurels at the opening, falling in a line to 3 at the end of
// the drawing's week (the server's `pixel_gain`), so that the page and la une count it down to the
// minute along with their countdown. The server's `gain_now` is the figure at the last fetch.
import { useNow } from '../../../ui/Countdown';
import type { PixelStatus } from '../api';

const START_GAIN = 50;
const FLOOR_GAIN = 3;

export function gainAt(status: PixelStatus, now: number): number | null {
  if (status.gain_now == null) return null;
  if (!status.started_at || !status.gain_ends_at) return status.gain_now;
  const start = new Date(status.started_at).getTime();
  const duration = new Date(status.gain_ends_at).getTime() - start;
  if (duration <= 0) return status.gain_now;
  const done = Math.min(Math.max(now - start, 0), duration);
  return (
    START_GAIN - Math.floor(((START_GAIN - FLOOR_GAIN) * done * 2 + duration) / (2 * duration))
  );
}

/** The laurels whoever finds the word now would win, refreshed every 15 seconds. */
export function useGainNow(status: PixelStatus | null): number | null {
  const now = useNow(15_000);
  return status ? gainAt(status, now) : null;
}
