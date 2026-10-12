import { type Browser, type Page, expect, test } from '@playwright/test';

const PASSWORD = 'demo1234';
const CANTEEN = 'Тестовая столовая (e2e)';

async function signIn(browser: Browser, email: string, width = 1280): Promise<Page> {
  const context = await browser.newContext({ viewport: { width, height: 900 } });
  const page = await context.newPage();
  await page.goto('/login');
  await page.getByLabel('Почта').fill(email);
  await page.getByLabel('Пароль').fill(PASSWORD);
  await page.getByRole('button', { name: 'Войти' }).click();
  await page.waitForURL((url) => !url.pathname.startsWith('/login'));
  // Customers may get the one-time onboarding; skip it if it shows up.
  const skip = page.getByRole('button', { name: 'Пропустить' });
  await skip.click({ timeout: 2000 }).catch(() => undefined);
  return page;
}

test('student orders and pays, cook cooks, cashier hands over, student sees «Выдан»', async ({
  browser,
}) => {
  // 1. The customer orders, pays and sees the QR code.
  const customer = await signIn(browser, 'e2e-customer@demo.kz', 390);
  await customer.goto('/menu');
  await customer.getByLabel('Столовая').selectOption({ label: CANTEEN });
  await customer.getByRole('button', { name: 'В корзину: Плов' }).click();
  await customer.getByRole('link', { name: /Корзина ·/ }).click();
  await customer.locator('fieldset button').first().click();
  await customer.getByRole('button', { name: /Заказать за/ }).click();
  await expect(customer).toHaveURL(/\/pay\/mock\/\d+/);
  await customer.getByRole('button', { name: 'Оплатить' }).click();
  await expect(customer).toHaveURL(/\/orders\/\d+/);
  await expect(customer.getByText('Оплачен', { exact: true })).toBeVisible();
  await expect(customer.getByRole('img', { name: 'QR-код заказа' })).toBeVisible();
  const number = (await customer.getByRole('heading', { level: 1 }).textContent())?.trim() ?? '';
  expect(number).toMatch(/^A-\d{3}$/);

  // 2. The cook takes it and marks it ready.
  const cook = await signIn(browser, 'e2e-cook@demo.kz');
  await cook.goto('/kitchen');
  const card = cook.getByRole('article', { name: number });
  await card.getByRole('button', { name: 'В работу' }).click();
  await cook.getByRole('article', { name: number }).getByRole('button', { name: 'Готово' }).click();
  await expect(cook.getByRole('article', { name: number }).getByText(/Полка \d+/)).toBeVisible();

  // The customer sees «Готов» without reloading.
  await expect(customer.getByText('Готов', { exact: true })).toBeVisible();

  // 3. The cashier finds the order by its number and hands it over.
  const cashier = await signIn(browser, 'e2e-cashier@demo.kz');
  await cashier.goto('/pickup');
  await cashier.getByLabel('Номер заказа').fill(number);
  await cashier.getByRole('button', { name: 'Найти' }).click();
  await expect(cashier.getByText(number)).toBeVisible();
  await cashier.getByRole('button', { name: 'Выдать' }).click();
  await expect(cashier.getByRole('status').filter({ hasText: 'Выдан' })).toBeVisible();

  // 4. The customer sees «Выдан».
  await expect(customer.getByText('Выдан', { exact: true })).toBeVisible();
});
