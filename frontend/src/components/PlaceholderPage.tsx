import { useTranslation } from 'react-i18next';

interface PlaceholderPageProps {
  titleKey: string;
}

export function PlaceholderPage({ titleKey }: PlaceholderPageProps) {
  const { t } = useTranslation();
  return (
    <section className="mx-auto max-w-3xl p-4">
      <h1 className="text-2xl font-semibold">{t(titleKey)}</h1>
      <p className="mt-2 text-slate-500 dark:text-slate-400">{t('app.comingSoon')}</p>
    </section>
  );
}
