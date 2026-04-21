import { test, expect } from '@playwright/test';
import { shoot, pastMondayMsk } from './helpers';

test('plan-fact: прошлая неделя + кнопка ИИ-анализа', async ({ page }) => {
  await page.goto('/');

  // Берём понедельник прошлой недели — полностью завершённую неделю
  const pastMonday = pastMondayMsk(1);
  await page.getByTestId('forecast-date').fill(pastMonday);
  await page.getByTestId('forecast-submit').click();

  await expect(page.getByTestId('forecast-table')).toBeVisible({ timeout: 45_000 });
  await expect(page.getByTestId('forecast-meta')).toBeVisible();

  // Кнопка анализа ИИ появляется, когда план-факт загрузился
  const trigger = page.getByTestId('discrepancy-trigger');
  await expect(trigger).toBeVisible({ timeout: 20_000 });

  await shoot(page, '03-plan-fact-loaded');
});
