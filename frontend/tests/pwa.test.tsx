import { act, render, screen } from '@testing-library/react';
import { readFileSync } from 'node:fs';

import { OfflineBanner } from '@/components/OfflineBanner';
import { clearPersonalCache } from '@/lib/pwa';

function setOnline(value: boolean) {
  Object.defineProperty(navigator, 'onLine', { configurable: true, get: () => value });
  window.dispatchEvent(new Event(value ? 'online' : 'offline'));
}

afterEach(() => {
  setOnline(true);
  vi.unstubAllGlobals();
});

describe('pwa', () => {
  it('shows the offline banner only while the network is down', () => {
    render(<OfflineBanner />);
    expect(screen.queryByRole('status')).toBeNull();
    act(() => setOnline(false));
    expect(screen.getByRole('status')).toHaveTextContent('Нет сети');
    act(() => setOnline(true));
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('drops the cached menu with allergy marks on sign-out', async () => {
    const deleted: string[] = [];
    vi.stubGlobal('caches', {
      delete: (name: string) => {
        deleted.push(name);
        return Promise.resolve(true);
      },
    });
    await clearPersonalCache();
    expect(deleted).toEqual(['api-menu']);
  });

  it('has an installable manifest', () => {
    const manifest = JSON.parse(readFileSync('public/manifest.webmanifest', 'utf-8')) as {
      display: string;
      start_url: string;
      icons: { sizes: string; purpose?: string }[];
    };
    expect(manifest.display).toBe('standalone');
    expect(manifest.start_url).toBe('/');
    const sizes = manifest.icons.map((i) => i.sizes);
    expect(sizes).toContain('192x192');
    expect(sizes).toContain('512x512');
    expect(manifest.icons.some((i) => i.purpose === 'maskable')).toBe(true);
  });
});
