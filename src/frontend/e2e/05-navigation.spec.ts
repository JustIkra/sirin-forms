import { test, expect } from '@playwright/test';
import { shoot } from './helpers';

test('navigation: переключение между Прогноз и Остатки', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Недельный прогноз' })).toBeVisible();
  await shoot(page, '05-nav-forecast');

  await page.getByTestId('nav-inventory').click();
  await expect(page.getByRole('heading', { name: 'Остатки и закупка' })).toBeVisible();
  await shoot(page, '05-nav-inventory');

  await page.getByTestId('nav-forecast').click();
  await expect(page.getByRole('heading', { name: 'Недельный прогноз' })).toBeVisible();
  await expect(page.getByTestId('forecast-form')).toBeVisible();
});
