import type { InventoryResponse, InventoryScope } from '../types/forecast';
import { ForecastError } from './forecast';

const BASE_URL = import.meta.env.VITE_API_URL ?? '';

export async function fetchInventory(
  date: string,
  scope: InventoryScope = 'week',
): Promise<InventoryResponse> {
  const res = await fetch(`${BASE_URL}/api/inventory?date=${date}&scope=${scope}`);

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ForecastError(res.status, body.detail ?? 'Ошибка загрузки остатков');
  }

  return res.json();
}
