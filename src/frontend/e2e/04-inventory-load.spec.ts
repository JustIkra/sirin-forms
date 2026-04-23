import { test, expect } from '@playwright/test';
import { shoot } from './helpers';

test('inventory: загрузка недельных остатков + фильтр "Нужно закупить"', async ({ page }) => {
  await page.goto('/');

  await page.getByTestId('nav-inventory').click();
  await expect(page.getByTestId('inventory-load')).toBeVisible();

  // Picker defaults to today's Monday (scope=week); just submit.
  await page.getByTestId('inventory-load').click();

  await expect(page.getByTestId('inventory-table')).toBeVisible({ timeout: 45_000 });
  await shoot(page, '04-inventory-all');

  await page.getByTestId('inventory-tab-to-buy').click();
  await expect(page.getByTestId('inventory-table')).toBeVisible();

  await shoot(page, '04-inventory-to-buy');
});
