import type { DailyForecastResult } from '../types/forecast';

const BASE_URL = import.meta.env.VITE_API_URL ?? '';

export class ForecastError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function fetchForecast(
  date: string,
  force: boolean = false,
): Promise<DailyForecastResult> {
  const res = await fetch(`${BASE_URL}/api/forecast`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ date, force }),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ForecastError(res.status, body.detail ?? 'Ошибка сервера');
  }

  return res.json();
}
