import { Page } from '@playwright/test';

const SCREENSHOTS_DIR = '../../reports/screenshots';

export async function shoot(page: Page, name: string): Promise<void> {
  await page.screenshot({
    path: `${SCREENSHOTS_DIR}/${name}.png`,
    fullPage: true,
  });
}

export function todayMsk(): string {
  return new Date().toLocaleDateString('sv-SE', { timeZone: 'Europe/Moscow' });
}

export function pastMondayMsk(weeksBack: number = 1): string {
  // Build MSK-local Date directly from toLocaleString parts (avoid UTC drift in toISOString)
  const mskStr = new Date().toLocaleString('en-US', { timeZone: 'Europe/Moscow' });
  const d = new Date(mskStr);
  const day = d.getDay();
  const diffToMonday = day === 0 ? -6 : 1 - day;
  d.setDate(d.getDate() + diffToMonday - 7 * weeksBack);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${dd}`;
}
