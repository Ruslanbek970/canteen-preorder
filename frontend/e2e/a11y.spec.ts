/// <reference lib="dom" />
import AxeBuilder from '@axe-core/playwright';
import { type Browser, type Page, expect, test } from '@playwright/test';

// SPEC 11: no WCAG 2.1 A/AA violations on the main screens, and the student flow works from
// the keyboard. Runs against the same stack and users as order-flow.spec.ts.
const PASSWORD = 'demo1234';
const CANTEEN = 'Тестовая столовая (e2e)';

async function signIn(browser: Browser, email: string, width: number): Promise<Page> {
  const context = await browser.newContext({ viewport: { width, height: 800 } });
  const page = await context.newPage();
  await page.goto('/login');
  await page.getByLabel('Почта').fill(email);
  await page.getByLabel('Пароль').fill(PASSWORD);
  await page.getByRole('button', { name: 'Войти' }).click();
  await page.waitForURL((url) => !url.pathname.startsWith('/login'));
  const skip = page.getByRole('button', { name: 'Пропустить' });
  await skip.click({ timeout: 2000 }).catch(() => undefined);
  return page;
}

async function expectNoViolations(page: Page, screen: string) {
  await page.waitForLoadState('networkidle');
  const result = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();
  const summary = result.violations.map((v) => `${v.id}: ${v.nodes.length} (${v.help})`);
  expect(summary, screen).toEqual([]);
}

test('login page', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto('/login');
  await expectNoViolations(page, '/login');
});

test('student screens at 360 px', async ({ browser }) => {
  const page = await signIn(browser, 'e2e-customer@demo.kz', 360);
  await page.goto('/menu');
  await page.getByLabel('Столовая').selectOption({ label: CANTEEN });
  await expect(page.getByRole('button', { name: 'В корзину: Плов' })).toBeVisible();
  await expectNoViolations(page, '/menu');
  for (const path of ['/cart', '/orders', '/profile', '/notifications']) {
    await page.goto(path);
    await expectNoViolations(page, path);
  }
  // Nothing scrolls sideways on a small phone.
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});

test('staff screens on a tablet', async ({ browser }) => {
  const cook = await signIn(browser, 'e2e-cook@demo.kz', 1024);
  await cook.goto('/kitchen');
  await expectNoViolations(cook, '/kitchen');
  const cashier = await signIn(browser, 'e2e-cashier@demo.kz', 1024);
  await cashier.goto('/pickup');
  await expectNoViolations(cashier, '/pickup');
});

test('keyboard: skip link, then a dish goes to the cart without a mouse', async ({ browser }) => {
  const page = await signIn(browser, 'e2e-customer@demo.kz', 360);
  await page.goto('/menu');
  await page.getByLabel('Столовая').selectOption({ label: CANTEEN });
  await expect(page.getByRole('button', { name: 'В корзину: Плов' })).toBeVisible();

  await page.locator('body').focus();
  await page.keyboard.press('Tab');
  const skip = page.getByRole('link', { name: 'Перейти к содержимому' });
  await expect(skip).toBeFocused();
  await expect(skip).toBeInViewport();

  const add = page.getByRole('button', { name: 'В корзину: Плов' });
  await add.focus();
  const outline = await add.evaluate((el) => getComputedStyle(el).outlineStyle);
  expect(outline).not.toBe('none');
  await page.keyboard.press('Enter');
  await expect(page.getByRole('link', { name: /Корзина ·/ })).toBeVisible();
});
