import { useTranslation } from 'react-i18next';
import { Link, Outlet, useLocation } from 'react-router-dom';

/** Sign-in and sign-up share one card: on wide screens a red panel slides between the two
 *  halves when the person switches forms; on phones the panel becomes a banner on top. */
export function AuthLayout() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const register = pathname.startsWith('/register');
  const other = register
    ? {
        title: t('auth.welcomeBack'),
        text: t('auth.welcomeBackText'),
        to: '/login',
        cta: t('auth.login'),
      }
    : {
        title: t('auth.helloNew'),
        text: t('auth.helloNewText'),
        to: '/register',
        cta: t('auth.register'),
      };
  const slide =
    'transition-[left] duration-700 ease-[cubic-bezier(0.65,0,0.35,1)] motion-reduce:transition-none';

  return (
    <section className="relative px-4 py-6 sm:py-10">
      <div
        className="pointer-events-none absolute left-1/2 top-0 -z-10 h-72 w-[40rem] max-w-full -translate-x-1/2 rounded-full bg-brand-200/40 blur-3xl"
        aria-hidden
      />
      <div className="relative mx-auto max-w-4xl overflow-hidden rounded-3xl bg-white shadow-[0_24px_60px_-24px_rgba(118,8,35,0.35)] ring-1 ring-slate-200/70 md:min-h-[660px]">
        <div
          className={`md:absolute md:inset-y-0 md:w-1/2 ${slide} ${register ? 'md:left-1/2' : 'md:left-0'}`}
        >
          <div className="on-brand relative overflow-hidden bg-gradient-to-br from-brand-600 to-brand-800 px-6 py-6 text-white md:hidden">
            <Bubbles />
            <p className="relative text-lg font-bold">{other.title}</p>
            <p className="relative mt-1 text-sm text-white">{other.text}</p>
            <Link
              to={other.to}
              className="relative mt-3 inline-block rounded-full border-2 border-white px-5 py-1.5 text-sm font-semibold hover:bg-white hover:text-brand-700"
            >
              {other.cta}
            </Link>
          </div>
          <div
            key={pathname}
            className="flex h-full flex-col justify-center px-6 py-8 motion-safe:animate-fade-up sm:px-10"
          >
            <Outlet />
          </div>
        </div>

        <div
          className={`on-brand absolute inset-y-0 hidden w-1/2 overflow-hidden bg-gradient-to-br from-brand-600 via-brand-700 to-brand-800 text-white md:block ${slide} ${register ? 'left-0' : 'left-1/2'}`}
        >
          <Bubbles />
          <div
            key={other.to}
            className="relative flex h-full flex-col items-center justify-center px-12 text-center motion-safe:animate-fade-in"
          >
            <PlateIcon />
            <h2 className="mt-6 text-3xl font-bold tracking-tight">{other.title}</h2>
            <p className="mt-3 max-w-xs leading-relaxed text-white">{other.text}</p>
            <Link
              to={other.to}
              className="mt-8 rounded-full border-2 border-white px-10 py-2.5 font-semibold uppercase tracking-wider transition hover:bg-white hover:text-brand-700"
            >
              {other.cta}
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}

function Bubbles() {
  return (
    <div className="pointer-events-none absolute inset-0" aria-hidden>
      <span className="absolute -right-10 -top-10 h-44 w-44 rounded-full bg-white/10 motion-safe:animate-float" />
      <span className="absolute -bottom-16 -left-12 h-56 w-56 rounded-full bg-white/10 motion-safe:animate-float [animation-delay:-3s]" />
      <span className="absolute bottom-24 right-10 h-16 w-16 rounded-full bg-white/10 motion-safe:animate-float [animation-delay:-1.5s]" />
    </div>
  );
}

function PlateIcon() {
  return (
    <span
      className="flex h-20 w-20 items-center justify-center rounded-3xl bg-white/15 ring-1 ring-white/30 backdrop-blur"
      aria-hidden
    >
      <svg viewBox="0 0 512 512" className="h-12 w-12" fill="none" stroke="currentColor">
        <circle cx="256" cy="268" r="120" strokeWidth={28} />
        <circle cx="256" cy="268" r="56" fill="currentColor" stroke="none" />
        <path
          d="M112 120v84M88 120v56a24 24 0 0 0 48 0v-56M112 204v196"
          strokeWidth={22}
          strokeLinecap="round"
        />
        <path
          d="M400 120c-28 16-32 70-32 100h32v180"
          strokeWidth={22}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  );
}
