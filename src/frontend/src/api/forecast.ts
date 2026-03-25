import type {
  AccuracyHistoryResponse,
  DailyForecastResult,
  PlanFactResponse,
  ProcurementList,
  TrendsResponse,
} from '../types/forecast';

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
  method: 'llm' | 'ml' = 'llm',
): Promise<DailyForecastResult> {
  const res = await fetch(`${BASE_URL}/api/forecast`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ date, force, method }),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ForecastError(res.status, body.detail ?? 'Ошибка сервера');
  }

  return res.json();
}

export async function fetchPlanFact(
  date: string,
  method: 'llm' | 'ml' = 'llm',
): Promise<PlanFactResponse | null> {
  const res = await fetch(`${BASE_URL}/api/plan-fact?date=${date}&method=${method}`);

  if (res.status === 404 || res.status === 422) {
    return null;
  }

  if (!res.ok) {
    throw new ForecastError(res.status, 'Ошибка загрузки план-факта');
  }

  return res.json();
}

export async function fetchAccuracyHistory(days = 30): Promise<AccuracyHistoryResponse> {
  const res = await fetch(`${BASE_URL}/api/accuracy-history?days=${days}`);
  if (!res.ok) throw new ForecastError(res.status, 'Ошибка загрузки истории accuracy');
  return res.json();
}

export async function fetchTrends(weeks = 12): Promise<TrendsResponse> {
  const res = await fetch(`${BASE_URL}/api/trends?weeks=${weeks}`);
  if (!res.ok) throw new ForecastError(res.status, 'Ошибка загрузки трендов');
  return res.json();
}

export async function fetchProcurement(
  date: string,
  method: 'llm' | 'ml' = 'ml',
): Promise<ProcurementList> {
  const res = await fetch(`${BASE_URL}/api/procurement`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ date, method }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ForecastError(res.status, body.detail ?? 'Ошибка закупок');
  }
  return res.json();
}

export function getExportUrl(
  date: string,
  method: string,
  type: string,
  format: string,
): string {
  return `${BASE_URL}/api/export?date=${date}&method=${method}&type=${type}&format=${format}`;
}
