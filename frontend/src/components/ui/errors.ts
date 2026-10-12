import { useTranslation } from 'react-i18next';

import { ApiError } from '@/api/client';

/** Translates an API error by its code, falling back to the server message. */
export function useErrorMessage() {
  const { t } = useTranslation();
  return (error: unknown): string => {
    if (error instanceof ApiError) {
      return t(`errors.${error.code}`, {
        ...error.details,
        defaultValue: error.message || t('errors.generic'),
      });
    }
    return t('errors.generic');
  };
}
