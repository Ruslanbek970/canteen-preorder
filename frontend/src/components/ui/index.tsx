import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
} from 'react';
import { useTranslation } from 'react-i18next';

import { useErrorMessage } from './errors';

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost';

const VARIANTS: Record<Variant, string> = {
  primary:
    'bg-brand-600 text-white shadow-sm hover:bg-brand-700 active:bg-brand-800 disabled:bg-brand-200 disabled:text-brand-900 disabled:shadow-none',
  secondary:
    'border border-brand-200 bg-white text-brand-700 hover:border-brand-300 hover:bg-brand-50 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900 dark:text-brand-200 dark:hover:bg-slate-800',
  danger:
    'border-2 border-red-700 bg-white text-red-700 hover:bg-red-50 disabled:opacity-50 dark:border-red-400 dark:bg-transparent dark:text-red-300 dark:hover:bg-red-950',
  ghost: 'text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800',
};

export function Button({
  variant = 'primary',
  className = '',
  type = 'button',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      type={type}
      className={`inline-flex min-h-[44px] items-center justify-center gap-2 rounded-lg px-4 py-2 font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 focus-visible:ring-offset-2 disabled:cursor-not-allowed ${VARIANTS[variant]} ${className}`}
      {...props}
    />
  );
}

export function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: string;
  error?: string | null;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-slate-500">{hint}</span>}
      {error && <span className="mt-1 block text-sm text-red-600">{error}</span>}
    </label>
  );
}

const INPUT =
  'block rounded-lg border border-slate-300 bg-white px-3 py-2 text-base focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-600/30 dark:border-slate-700 dark:bg-slate-900';

const widthOf = (className: string) => (/(^|\s)w-/.test(className) ? '' : 'w-full');

export function Input({ className = '', ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`${INPUT} ${widthOf(className)} ${className}`} {...props} />;
}

export function Select({ className = '', ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={`${INPUT} ${widthOf(className)} ${className}`} {...props} />;
}

export function Card({ className = '', children }: { className?: string; children: ReactNode }) {
  return (
    <div
      className={`rounded-2xl border border-slate-200/80 bg-white p-4 shadow-[0_1px_3px_rgba(15,23,42,0.06),0_1px_2px_rgba(15,23,42,0.04)] dark:border-slate-800 dark:bg-slate-900 ${className}`}
    >
      {children}
    </div>
  );
}

export function Spinner() {
  return (
    <span
      className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-brand-600"
      aria-hidden
    />
  );
}

export function LoadingState() {
  const { t } = useTranslation();
  return (
    <div className="flex items-center justify-center gap-2 p-8 text-slate-500" role="status">
      <Spinner /> {t('common.loading')}
    </div>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <div className="p-8 text-center text-slate-500">{children}</div>;
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useTranslation();
  const message = useErrorMessage();
  return (
    <div
      className="m-4 rounded-lg border border-red-200 bg-red-50 p-4 text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200"
      role="alert"
    >
      <p>{message(error)}</p>
      {onRetry && (
        <Button variant="secondary" className="mt-2" onClick={onRetry}>
          {t('common.retry')}
        </Button>
      )}
    </div>
  );
}

export function Alert({
  tone = 'error',
  children,
}: {
  tone?: 'error' | 'warning' | 'success' | 'info';
  children: ReactNode;
}) {
  const tones = {
    error:
      'border-red-200 bg-red-50 text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200',
    warning:
      'border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200',
    success:
      'border-green-200 bg-green-50 text-green-800 dark:border-green-900 dark:bg-green-950 dark:text-green-200',
    info: 'border-sky-200 bg-sky-50 text-sky-900 dark:border-sky-900 dark:bg-sky-950 dark:text-sky-200',
  };
  return (
    <div
      className={`rounded-lg border p-3 ${tones[tone]}`}
      role={tone === 'error' ? 'alert' : 'status'}
    >
      {children}
    </div>
  );
}

export function PageTitle({ children, actions }: { children: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
      <h1 className="border-l-4 border-brand-600 pl-3 text-2xl font-bold tracking-tight">
        {children}
      </h1>
      {actions}
    </div>
  );
}

export function Badge({
  tone = 'gray',
  children,
}: {
  tone?: 'gray' | 'green' | 'red' | 'amber' | 'blue';
  children: ReactNode;
}) {
  const tones = {
    gray: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200',
    green: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100',
    red: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-100',
    amber: 'bg-amber-100 text-amber-900 dark:bg-amber-900 dark:text-amber-100',
    blue: 'bg-sky-100 text-sky-800 dark:bg-sky-900 dark:text-sky-100',
  };
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${tones[tone]}`}
    >
      {children}
    </span>
  );
}
