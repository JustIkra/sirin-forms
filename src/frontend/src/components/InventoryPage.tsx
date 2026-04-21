import { useState, useMemo } from 'react';
import type { InventoryResponse } from '../types/forecast';
import { ForecastError } from '../api/forecast';
import { fetchInventory } from '../api/inventory';
import InventoryTable from './InventoryTable';
import Spinner from './Spinner';
import ErrorMessage from './ErrorMessage';

type Mode = 'day' | 'week';
type Tab = 'all' | 'to_buy';

function todayMSK(): string {
  return new Date().toLocaleDateString('sv-SE', { timeZone: 'Europe/Moscow' });
}

function formatWeekRange(start: string, end: string): string {
  const fmt = (s: string) => {
    const d = new Date(s + 'T12:00:00');
    return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' });
  };
  return `${fmt(start)} — ${fmt(end)}`;
}

export default function InventoryPage() {
  const [mode, setMode] = useState<Mode>('week');
  const [date, setDate] = useState(todayMSK);
  const [data, setData] = useState<InventoryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<{ message: string; status?: number } | null>(null);
  const [tab, setTab] = useState<Tab>('all');

  const handleLoad = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchInventory(date);
      setData(result);
    } catch (err) {
      if (err instanceof ForecastError) {
        setError({ message: err.message, status: err.status });
      } else {
        setError({ message: 'Не удалось подключиться к серверу' });
      }
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  const filteredItems = useMemo(() => {
    if (!data) return [];
    if (tab === 'to_buy') return data.items.filter((i) => i.to_buy > 0);
    return data.items;
  }, [data, tab]);

  const toBuyCount = useMemo(
    () => data?.items.filter((i) => i.to_buy > 0).length ?? 0,
    [data],
  );

  return (
    <>
      <div className="mb-6">
        <h2 className="text-xl font-bold text-gradient">Остатки и закупка</h2>
        <p className="text-sm text-slate-400">
          Складские остатки и прогноз закупки по ингредиентам
        </p>
      </div>

      {/* День / Неделя */}
      <div className="mb-5 flex gap-1 rounded-lg bg-white/[0.04] p-1 w-fit">
        {([['week', 'Неделя'], ['day', 'День']] as const).map(([m, label]) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`rounded-md px-4 py-1.5 text-sm font-medium transition-colors ${
              mode === m
                ? 'bg-white/[0.1] text-white'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {mode === 'day' && (
        <div className="glass-card p-12 text-center">
          <p className="text-lg text-slate-400">В разработке</p>
          <p className="mt-2 text-sm text-slate-500">
            Дневной режим остатков будет доступен позже
          </p>
        </div>
      )}

      {mode === 'week' && (
        <>
          {/* Форма */}
          <form
            onSubmit={(e) => { e.preventDefault(); handleLoad(); }}
            className="flex flex-wrap items-end gap-4 mb-6"
          >
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-300">
                Дата
              </label>
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                data-testid="inventory-date"
                className="rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-white focus:border-blue-400 focus:ring-1 focus:ring-blue-400/30 focus:outline-none"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              data-testid="inventory-load"
              className="rounded-md bg-gradient-to-r from-blue-600 to-blue-500 px-5 py-2 text-sm font-medium text-white shadow-lg shadow-blue-500/25 transition-colors hover:from-blue-500 hover:to-blue-400 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? 'Загрузка...' : 'Загрузить'}
            </button>
          </form>

          {loading && <Spinner />}
          {error && <ErrorMessage message={error.message} status={error.status} />}

          {data && !loading && (
            <div className="space-y-4">
              {/* Мета */}
              <div className="flex items-center gap-4 text-sm text-slate-400">
                <span>
                  Неделя: {formatWeekRange(data.week_start, data.week_end)}
                </span>
                <span>
                  Позиций: {data.items.length}
                </span>
              </div>

              {/* Табы: Все / Нужно закупить */}
              <div className="flex gap-2" data-testid="inventory-tabs">
                {([
                  ['all', `Все (${data.items.length})`],
                  ['to_buy', `Нужно закупить (${toBuyCount})`],
                ] as const).map(([t, label]) => (
                  <button
                    key={t}
                    onClick={() => setTab(t)}
                    data-testid={`inventory-tab-${t.replace('_', '-')}`}
                    className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                      tab === t
                        ? 'bg-white/[0.1] text-white'
                        : 'text-slate-400 hover:bg-white/[0.04] hover:text-white'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>

              <div data-testid="inventory-table">
                <InventoryTable
                  items={filteredItems}
                  emptyMessage={
                    tab === 'to_buy'
                      ? 'Все позиции в наличии'
                      : 'Нет данных'
                  }
                />
              </div>
            </div>
          )}
        </>
      )}
    </>
  );
}
