import { execSync } from 'node:child_process';

// The e2e canteen closes at 23:59 with 10-minute slots and a 5-minute order cutoff, so in the
// last minutes of the Almaty day there is no slot left to order for today. The kitchen board
// and pickup work with today's orders only, so the run waits for the new day instead.
const LAST_ORDER_MINUTE = 23 * 60 + 44;

function almatyMinuteOfDay(now = new Date()): number {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Almaty',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(now);
  const value = (type: string) => Number(parts.find((p) => p.type === type)?.value ?? 0);
  return value('hour') * 60 + value('minute');
}

async function waitForNewDay() {
  const minute = almatyMinuteOfDay();
  if (minute <= LAST_ORDER_MINUTE) return;
  const waitMs = ((24 * 60 - minute) * 60 + 30) * 1000;
  console.log(`e2e: no slots left today in Asia/Almaty, waiting ${Math.ceil(waitMs / 1000)} s`);
  await new Promise((resolve) => setTimeout(resolve, waitMs));
}

/** Prepares the e2e canteen (open around the clock) and its users in the running stack. */
export default async function globalSetup() {
  await waitForNewDay();
  const command =
    process.env.E2E_SETUP_CMD ?? 'docker compose exec -T backend python -m scripts.e2e_setup';
  execSync(command, { stdio: 'inherit', cwd: '..' });
}
