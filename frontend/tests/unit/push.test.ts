import { describe, expect, it } from 'vitest';

import {
  keyBytes,
  pushStatus,
  type PushEnvironment,
} from '../../src/features/notifications/usePush';

const ready: PushEnvironment = {
  ios: false,
  standalone: false,
  supported: true,
  key: 'BCle',
  permission: 'default',
  subscribed: false,
};

describe('pushStatus', () => {
  it('can be turned on, then is on', () => {
    expect(pushStatus(ready)).toBe('off');
    expect(pushStatus({ ...ready, permission: 'granted', subscribed: true })).toBe('on');
  });

  it('tells an iPhone to add the app to its home screen first', () => {
    expect(pushStatus({ ...ready, ios: true, supported: false })).toBe('ios-install');
    expect(pushStatus({ ...ready, ios: true, standalone: true })).toBe('off');
  });

  it('says why it cannot', () => {
    expect(pushStatus({ ...ready, supported: false })).toBe('unsupported');
    expect(pushStatus({ ...ready, key: null })).toBe('unavailable');
    expect(pushStatus({ ...ready, permission: 'denied' })).toBe('denied');
    expect(pushStatus({ ...ready, key: undefined })).toBe('loading');
    expect(pushStatus({ ...ready, subscribed: undefined })).toBe('loading');
  });

  it('is off again when the permission was taken back', () => {
    expect(pushStatus({ ...ready, permission: 'default', subscribed: true })).toBe('off');
  });
});

describe('keyBytes', () => {
  it('decodes base64url without padding', () => {
    expect(Array.from(keyBytes('BP_-'))).toEqual([4, 255, 254]);
    expect(Array.from(keyBytes('AQID'))).toEqual([1, 2, 3]);
  });
});
