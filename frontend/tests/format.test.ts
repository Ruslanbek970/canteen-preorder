import { formatPrice, formatTime } from '@/lib/format';

describe('formatPrice', () => {
  it('groups thousands and adds the tenge sign', () => {
    expect(formatPrice(1500)).toBe('1 500 ₸');
  });

  it('accepts decimal strings from the API and rounds to whole tenge', () => {
    expect(formatPrice('1250.50')).toBe('1 251 ₸');
    expect(formatPrice('990.00')).toBe('990 ₸');
  });
});

describe('formatTime', () => {
  it('renders time in Asia/Almaty', () => {
    expect(formatTime('2026-10-12T07:30:00Z')).toBe('12:30');
  });
});
