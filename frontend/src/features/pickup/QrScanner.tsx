import jsQR from 'jsqr';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Alert } from '@/components/ui';

/** Camera QR scanner: decodes video frames with jsQR (works on iPad Safari too). */
export function QrScanner({ onScan, paused }: { onScan: (text: string) => void; paused: boolean }) {
  const { t } = useTranslation();
  const video = useRef<HTMLVideoElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const handler = useRef(onScan);
  handler.current = onScan;
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (paused) return;
    let stream: MediaStream | null = null;
    let frame = 0;
    let last = '';
    let stopped = false;
    const tick = () => {
      if (stopped) return;
      const v = video.current;
      const c = canvas.current;
      if (v && c && v.readyState >= v.HAVE_ENOUGH_DATA) {
        c.width = v.videoWidth;
        c.height = v.videoHeight;
        const ctx = c.getContext('2d', { willReadFrequently: true });
        if (ctx) {
          ctx.drawImage(v, 0, 0, c.width, c.height);
          const image = ctx.getImageData(0, 0, c.width, c.height);
          const code = jsQR(image.data, image.width, image.height);
          if (code?.data && code.data !== last) {
            last = code.data;
            handler.current(code.data);
          }
        }
      }
      frame = requestAnimationFrame(tick);
    };
    if (!navigator.mediaDevices?.getUserMedia) {
      setError(t('pickup.noCamera'));
      return;
    }
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: 'environment' } })
      .then((s) => {
        if (stopped) {
          s.getTracks().forEach((track) => track.stop());
          return;
        }
        stream = s;
        if (video.current) {
          video.current.srcObject = s;
          void video.current.play();
        }
        frame = requestAnimationFrame(tick);
      })
      .catch(() => setError(t('pickup.noCamera')));
    return () => {
      stopped = true;
      cancelAnimationFrame(frame);
      stream?.getTracks().forEach((track) => track.stop());
    };
  }, [paused, t]);

  if (error) return <Alert tone="warning">{error}</Alert>;
  return (
    <div className="relative overflow-hidden rounded-xl bg-black">
      <video ref={video} className="aspect-video w-full object-cover" muted playsInline />
      <canvas ref={canvas} className="hidden" />
      <div className="pointer-events-none absolute inset-8 rounded-xl border-4 border-white/70" />
    </div>
  );
}
