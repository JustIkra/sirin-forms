import { useState, useCallback, useMemo } from 'react';
import type { DishForecast, PlanFactRecord } from '../types/forecast';

interface Props {
  forecasts: DishForecast[];
  planFact?: PlanFactRecord[];
  mode?: 'weekly' | 'daily';
  exportSlot?: React.ReactNode;
}

type ViewMode = 'quantity' | 'revenue';
type MethodFilter = 'all' | 'ml' | 'fallback';
type SortKey = 'name' | 'forecast' | 'fact' | 'deviation';
type SortDir = 'asc' | 'desc';

function formatRub(n: number): string {
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
}

function deviationColor(pct: number): string {
  const abs = Math.abs(pct);
  if (abs <= 15) return 'text-emerald-300';
  if (abs <= 30) return 'text-amber-300';
  return 'text-fact-red';
}

function SortIcon({ active, dir }: { active: boolean; dir: SortDir }) {
  if (!active) return <span className="ml-1 text-ink-600">▾</span>;
  return (
    <span className="ml-1 text-accent-500">{dir === 'asc' ? '▴' : '▾'}</span>
  );
}

interface MergedRow {
  dish_id: string;
  dish_name: string;
  predicted_quantity: number;
  predicted_revenue: number;
  actual_quantity: number | null;
  actual_revenue: number | null;
  deviation_pct: number | null;
  revenue_deviation_pct: number | null;
  key_factors: string[];
  prediction_method: string;
}

export default function ForecastTable({
  forecasts,
  planFact,
  mode = 'weekly',
  exportSlot,
}: Props) {
  const [view, setView] = useState<ViewMode>('quantity');
  const [methodFilter, setMethodFilter] = useState<MethodFilter>('all');
  const [sortKey, setSortKey] = useState<SortKey>('forecast');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const hasFact = planFact && planFact.length > 0;
  const isRev = view === 'revenue';

  const mlCount = useMemo(
    () => forecasts.filter((f) => f.prediction_method === 'ml').length,
    [forecasts],
  );
  const fbCount = useMemo(
    () => forecasts.filter((f) => f.prediction_method === 'fallback').length,
    [forecasts],
  );

  const pfMap = new Map<string, PlanFactRecord>();
  if (planFact) {
    for (const r of planFact) {
      pfMap.set(r.dish_id, r);
      pfMap.set(r.dish_name.toLowerCase(), r);
    }
  }

  const allRows: MergedRow[] = forecasts.map((f) => {
    const pf =
      pfMap.get(f.dish_id) ?? pfMap.get(f.dish_name.toLowerCase()) ?? null;
    const predicted_revenue =
      pf && pf.predicted_revenue > 0
        ? pf.predicted_revenue
        : f.price
          ? f.predicted_quantity * f.price
          : 0;

    return {
      dish_id: f.dish_id,
      dish_name: f.dish_name,
      predicted_quantity: f.predicted_quantity,
      predicted_revenue,
      actual_quantity: pf ? pf.actual_quantity : null,
      actual_revenue: pf ? pf.actual_revenue : null,
      deviation_pct: pf ? pf.deviation_pct : null,
      revenue_deviation_pct: pf ? pf.revenue_deviation_pct : null,
      key_factors: f.key_factors,
      prediction_method: f.prediction_method,
    };
  });

  const rows =
    methodFilter === 'all'
      ? allRows
      : allRows.filter((r) => r.prediction_method === methodFilter);

  const hasRevenue = rows.some(
    (r) => r.predicted_revenue > 0 || (r.actual_revenue ?? 0) > 0,
  );

  const sorted = [...rows].sort((a, b) => {
    const mul = sortDir === 'asc' ? 1 : -1;
    switch (sortKey) {
      case 'name':
        return mul * a.dish_name.localeCompare(b.dish_name, 'ru');
      case 'forecast':
        return (
          mul *
          ((isRev ? a.predicted_revenue : a.predicted_quantity) -
            (isRev ? b.predicted_revenue : b.predicted_quantity))
        );
      case 'fact': {
        const fa = isRev ? (a.actual_revenue ?? 0) : (a.actual_quantity ?? 0);
        const fb = isRev ? (b.actual_revenue ?? 0) : (b.actual_quantity ?? 0);
        return mul * (fa - fb);
      }
      case 'deviation': {
        const da = isRev
          ? (a.revenue_deviation_pct ?? 0)
          : (a.deviation_pct ?? 0);
        const db = isRev
          ? (b.revenue_deviation_pct ?? 0)
          : (b.deviation_pct ?? 0);
        return mul * (Math.abs(da) - Math.abs(db));
      }
      default:
        return 0;
    }
  });

  const toggleSort = useCallback((key: SortKey) => {
    setSortKey((prev) => {
      if (prev === key) {
        setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
        return prev;
      }
      setSortDir(key === 'name' ? 'asc' : 'desc');
      return key;
    });
  }, []);

  const chip = (active: boolean, extra = '') =>
    `rounded-full px-4 py-1.5 text-xs font-medium tracking-wide transition-all ${
      active
        ? 'bg-cream-100 text-ink-900 shadow-sm'
        : 'text-ink-400 hover:text-cream-100'
    } ${extra}`;

  const th =
    'px-5 py-4 text-[10px] font-semibold tracking-[0.18em] text-ink-400 uppercase cursor-pointer select-none hover:text-cream-100 transition-colors';

  return (
    <div data-testid="forecast-table-wrapper" className="space-y-4">
      {/* Top bar: filters + export */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          {hasRevenue && (
            <div className="inline-flex rounded-full bg-black/25 p-1">
              <button
                type="button"
                onClick={() => setView('quantity')}
                data-testid="view-quantity"
                className={chip(view === 'quantity')}
              >
                Количество
              </button>
              <button
                type="button"
                onClick={() => setView('revenue')}
                data-testid="view-revenue"
                className={chip(view === 'revenue')}
              >
                Выручка
              </button>
            </div>
          )}

          <div className="inline-flex rounded-full bg-black/25 p-1">
            <button
              type="button"
              onClick={() => setMethodFilter('all')}
              data-testid="filter-all"
              className={chip(methodFilter === 'all')}
            >
              Все ({forecasts.length})
            </button>
            <button
              type="button"
              onClick={() => setMethodFilter('ml')}
              data-testid="filter-ml"
              className={chip(methodFilter === 'ml')}
            >
              ML ({mlCount})
            </button>
            <button
              type="button"
              onClick={() => setMethodFilter('fallback')}
              data-testid="filter-fallback"
              className={chip(methodFilter === 'fallback')}
            >
              Fallback ({fbCount})
            </button>
          </div>
        </div>

        {exportSlot}
      </div>

      {/* Table */}
      <div
        className="overflow-hidden rounded-2xl bg-black/20"
        data-testid="forecast-table"
      >
        <table className="w-full">
          <thead>
            <tr className="border-b border-white/5">
              <th
                className={`${th} text-left`}
                data-testid="sort-name"
                onClick={() => toggleSort('name')}
              >
                Блюдо <SortIcon active={sortKey === 'name'} dir={sortDir} />
              </th>
              <th className={`${th} text-left`}>Факторы</th>
              <th
                className={`${th} text-right`}
                onClick={() => toggleSort('forecast')}
              >
                {hasFact
                  ? mode === 'daily'
                    ? 'Кол-во (прогноз)'
                    : 'Кол-во (прогноз, нед.)'
                  : isRev
                    ? 'Выручка'
                    : 'Кол-во'}{' '}
                <SortIcon active={sortKey === 'forecast'} dir={sortDir} />
              </th>
              {hasFact && (
                <>
                  <th
                    className={`${th} text-right`}
                    onClick={() => toggleSort('fact')}
                  >
                    Кол-во (факт){' '}
                    <SortIcon active={sortKey === 'fact'} dir={sortDir} />
                  </th>
                  <th
                    className={`${th} text-right`}
                    onClick={() => toggleSort('deviation')}
                  >
                    Откл.{' '}
                    <SortIcon active={sortKey === 'deviation'} dir={sortDir} />
                  </th>
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {sorted.map((r, i) => {
              const forecastVal = isRev ? r.predicted_revenue : r.predicted_quantity;
              const factVal = isRev ? r.actual_revenue : r.actual_quantity;
              const dev = isRev ? r.revenue_deviation_pct : r.deviation_pct;
              const isFallback = r.prediction_method === 'fallback';

              return (
                <tr
                  key={`${r.dish_id}-${i}`}
                  data-testid="forecast-row"
                  data-method={r.prediction_method}
                  className="border-b border-white/[0.04] transition-colors last:border-0 hover:bg-white/[0.03]"
                >
                  <td className="px-5 py-4">
                    <div className="text-sm font-medium text-cream-100">
                      {r.dish_name}
                    </div>
                    <div className="mt-1 text-xs text-ink-400">
                      {isFallback ? 'Fallback (эвристика)' : 'ML-модель (HistGBR)'}
                    </div>
                  </td>
                  <td className="px-5 py-4 text-sm text-ink-400">
                    {r.key_factors.join(', ')}
                  </td>
                  <td className="px-5 py-4 text-right text-sm tabular-nums text-cream-100">
                    {isRev
                      ? forecastVal > 0
                        ? `${formatRub(forecastVal)} ₽`
                        : '—'
                      : forecastVal}
                  </td>
                  {hasFact && (
                    <>
                      <td className="px-5 py-4 text-right text-sm tabular-nums text-cream-100">
                        {factVal != null
                          ? isRev
                            ? `${formatRub(factVal)} ₽`
                            : factVal
                          : '—'}
                      </td>
                      <td className="px-5 py-4 text-right">
                        {dev != null ? (
                          <span
                            className={`text-sm font-medium tabular-nums ${deviationColor(dev)}`}
                          >
                            {dev > 0 ? '+' : ''}
                            {dev}%
                          </span>
                        ) : (
                          <span className="text-sm text-ink-500">—</span>
                        )}
                      </td>
                    </>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>

        {sorted.length === 0 && (
          <div className="py-10 text-center text-sm text-ink-400">
            Нет блюд для выбранного фильтра
          </div>
        )}
      </div>
    </div>
  );
}
