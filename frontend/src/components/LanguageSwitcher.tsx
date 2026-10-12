import { useTranslation } from 'react-i18next';

import { SUPPORTED_LANGUAGES } from '@/i18n';

export function LanguageSwitcher() {
  const { t, i18n } = useTranslation();
  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="sr-only">{t('nav.language')}</span>
      <select
        aria-label={t('nav.language')}
        className="rounded-lg border border-white/40 bg-transparent px-2 py-1 font-medium text-white hover:bg-white/10 [&>option]:text-slate-900"
        value={i18n.resolvedLanguage}
        onChange={(e) => void i18n.changeLanguage(e.target.value)}
      >
        {SUPPORTED_LANGUAGES.map((lng) => (
          <option key={lng} value={lng}>
            {lng.toUpperCase()}
          </option>
        ))}
      </select>
    </label>
  );
}
