import { execSync } from 'node:child_process';

/** Prepares the e2e canteen (open around the clock) and its users in the running stack. */
export default function globalSetup() {
  const command =
    process.env.E2E_SETUP_CMD ?? 'docker compose exec -T backend python -m scripts.e2e_setup';
  execSync(command, { stdio: 'inherit', cwd: '..' });
}
