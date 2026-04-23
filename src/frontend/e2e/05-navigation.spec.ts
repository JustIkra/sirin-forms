import { test, expect } from '@playwright/test';
import { shoot } from './helpers';

test('navigation: переключение между Остатки / Тренды / Прогноз', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByTestId('forecast-form')).toBeVisible();
  await shoot(page, '05-nav-forecast');

  await page.getByTestId('nav-inventory').click();
  await expect(page.getByText('Остатки под').first()).toBeVisible();
  await shoot(page, '05-nav-inventory');

  await page.getByTestId('nav-trends').click();
  await expect(page.getByTestId('trends-page')).toBeVisible();
  await shoot(page, '05-nav-trends');

  await page.getByTestId('nav-forecast').click();
  await expect(page.getByTestId('forecast-form')).toBeVisible();
});
