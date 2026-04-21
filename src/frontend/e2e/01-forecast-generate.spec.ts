import { test, expect } from '@playwright/test';
import { shoot, todayMsk } from './helpers';

test('forecast: генерация недельного прогноза на сегодня', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Недельный прогноз' })).toBeVisible();
  await shoot(page, '01-forecast-initial');

  const dateInput = page.getByTestId('forecast-date');
  await dateInput.fill(todayMsk());

  await page.getByTestId('forecast-submit').click();

  // Таблица появляется когда прогноз сгенерирован
  await expect(page.getByTestId('forecast-table')).toBeVisible({ timeout: 45_000 });
  await expect(page.getByTestId('forecast-meta')).toBeVisible();

  const rowCount = await page.getByTestId('forecast-row').count();
  expect(rowCount).toBeGreaterThan(0);

  await shoot(page, '01-forecast-generated');
});
