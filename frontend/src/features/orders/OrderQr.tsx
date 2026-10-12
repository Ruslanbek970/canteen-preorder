import QRCode from 'qrcode';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

/** QR with the order's secret token; the cashier scans it at pickup (SPEC 7.9). */
export function OrderQr({ token }: { token: string }) {
  const { t } = useTranslation();
  const [svg, setSvg] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    void QRCode.toString(token, { type: 'svg', margin: 1, errorCorrectionLevel: 'M' }).then(
      (value) => alive && setSvg(value),
    );
    return () => {
      alive = false;
    };
  }, [token]);
  return (
    <figure className="flex flex-col items-center">
      <div
        role="img"
        aria-label={t('orders.qrLabel')}
        className="h-56 w-56 rounded-lg bg-white p-2"
        // The SVG is generated locally from our own token, not from user input.
        dangerouslySetInnerHTML={svg ? { __html: svg } : undefined}
      />
      <figcaption className="mt-2 text-sm text-slate-500">{t('orders.qrHint')}</figcaption>
    </figure>
  );
}
