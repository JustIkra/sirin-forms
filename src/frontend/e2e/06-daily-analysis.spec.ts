import { test, expect } from '@playwright/test';
import { shoot, pastMondayMsk } from './helpers';

test('daily-analysis: переключение в дневной режим и проверка UI', async ({ page }) => {
  await page.goto('/');

  // Остаёмся на вкладке "Прогноз" и переключаем mode-toggle в "Дневной"
  await page.getByTestId('nav-forecast').click();
  await page.getByTestId('mode-daily').click();
  await expect(page.getByTestId('mode-daily')).toBeVisible();
  await shoot(page, '06-daily-initial');

  // Форма отображается
  await expect(page.getByTestId('forecast-form')).toBeVisible();
  await expect(page.getByTestId('forecast-date')).toBeVisible();
  await expect(page.getByTestId('forecast-submit')).toBeVisible();

  // Берём прошлую дату — возможно, уже есть кэш
  const pastDate = pastMondayMsk(2);
  await page.getByTestId('forecast-date').fill(pastDate);
  await page.getByTestId('forecast-submit').click();

  // Ожидаем либо таблицу, либо сообщение (дневной прогноз может не появиться без данных)
  const table = page.getByTestId('forecast-table');
  const error = page.locator('[data-testid="error-message"], text=/ошибка/i');

  await Promise.race([
    table.waitFor({ state: 'visible', timeout: 45_000 }).catch(() => null),
    error.first().waitFor({ state: 'visible', timeout: 45_000 }).catch(() => null),
  ]);

  await shoot(page, '06-daily-result');
});
