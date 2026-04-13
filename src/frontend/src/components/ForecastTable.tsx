import { useState, useCallback, useMemo } from 'react';
import type { DishForecast, PlanFactRecord } from '../types/forecast';

interface Props {
  forecasts: DishForecast[];
  planFact?: PlanFactRecord[];
}

type ViewMode = 'quantity' | 'revenue';
type MethodFilter = 'all' | 'ml' | 'fallback';
type SortKey = 'name' | 'forecast' | 'fact' | 'deviation' | 'factors';
type SortDir = 'asc' | 'desc';

function formatRub(n: number): string {
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
}

function deviationColor(pct: number): string {
  const abs = Math.abs(pct);
  if (abs <= 15) return 'text-green-400 bg-green-400/10';
  if (abs <= 30) return 'text-yellow-400 bg-yellow-400/10';
  return 'text-red-400 bg-red-400/10';
}

function SortIcon({ active, dir }: { active: boolean; dir: SortDir }) {
  if (!active) return <span className="inline-block ml-1 text-slate-600">{'\u25BC'}</span>;
  return (
    <span className="inline-block ml-1 text-blue-400">
      {dir === 'asc' ? '\u25B2' : '\u25BC'}
    </span>
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

export default function ForecastTable({ forecasts, planFact }: Props) {
  const [view, setView] = useState<ViewMode>('quantity');
  const [methodFilter, setMethodFilter] = useState<MethodFilter>('all');
  const [sortKey, setSortKey] = useState<SortKey>('forecast');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const hasFact = planFact && planFact.length > 0;
  const isRev = view === 'revenue';

  // Counts
  const mlCount = useMemo(() => forecasts.filter(f => f.prediction_method === 'ml').length, [forecasts]);
  const fbCount = useMemo(() => forecasts.filter(f => f.prediction_method === 'fallback').length, [forecasts]);

  // Build plan-fact lookup
  const pfMap = new Map<string, PlanFactRecord>();
  if (planFact) {
    for (const r of planFact) {
      pfMap.set(r.dish_id, r);
      pfMap.set(r.dish_name.toLowerCase(), r);
    }
  }

  // Merge forecasts with plan-fact data
  const allRows: MergedRow[] = forecasts.map((f) => {
    const pf = pfMap.get(f.dish_id) ?? pfMap.get(f.dish_name.toLowerCase()) ?? null;
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

  // Filter by method
  const rows = methodFilter === 'all'
    ? allRows
    : allRows.filter(r => r.prediction_method === methodFilter);

  const hasRevenue = rows.some((r) => r.predicted_revenue > 0 || (r.actual_revenue ?? 0) > 0);

  // Sort
  const sorted = [...rows].sort((a, b) => {
    const mul = sortDir === 'asc' ? 1 : -1;
    switch (sortKey) {
      case 'name':
        return mul * a.dish_name.localeCompare(b.dish_name, 'ru');
      case 'forecast':
        return mul * (
          (isRev ? a.predicted_revenue : a.predicted_quantity) -
          (isRev ? b.predicted_revenue : b.predicted_quantity)
        );
      case 'fact': {
        const fa = isRev ? (a.actual_revenue ?? 0) : (a.actual_quantity ?? 0);
        const fb = isRev ? (b.actual_revenue ?? 0) : (b.actual_quantity ?? 0);
        return mul * (fa - fb);
      }
      case 'deviation': {
        const da = isRev ? (a.revenue_deviation_pct ?? 0) : (a.deviation_pct ?? 0);
        const db = isRev ? (b.revenue_deviation_pct ?? 0) : (b.deviation_pct ?? 0);
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

  const thClass =
    'px-4 py-3 text-xs font-medium tracking-wider text-slate-400 uppercase cursor-pointer select-none hover:text-slate-200 transition-colors';

  const chipClass = (active: boolean) =>
    `rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
      active ? 'bg-white/10 text-white' : 'text-slate-400 hover:text-white'
    }`;

  return (
    <div className="overflow-hidden glass-card">
      {/* Filter bar */}
      <div className="flex items-center justify-between border-b border-white/[0.06] bg-white/[0.02] px-4 py-2">
        {/* Left: qty / revenue */}
        {hasRevenue && (
          <div className="flex gap-1">
            <button onClick={() => setView('quantity')} className={chipClass(view === 'quantity')}>
              Количество
            </button>
            <button onClick={() => setView('revenue')} className={chipClass(view === 'revenue')}>
              Выручка
            </button>
          </div>
        )}
        {!hasRevenue && <div />}

        {/* Right: method filter */}
        <div className="flex gap-1">
          <button onClick={() => setMethodFilter('all')} className={chipClass(methodFilter === 'all')}>
            Все ({forecasts.length})
          </button>
          <button onClick={() => setMethodFilter('ml')} className={chipClass(methodFilter === 'ml')}>
            ML ({mlCount})
          </button>
          <button onClick={() => setMethodFilter('fallback')} className={chipClass(methodFilter === 'fallback')}>
            Fallback ({fbCount})
          </button>
        </div>
      </div>

      <table className="min-w-full divide-y divide-white/[0.06]">
        <thead className="bg-white/[0.03]">
          <tr>
            <th className={`${thClass} text-left`} onClick={() => toggleSort('name')}>
              Блюдо <SortIcon active={sortKey === 'name'} dir={sortDir} />
            </th>
            <th className={`${thClass} text-right`} onClick={() => toggleSort('forecast')}>
              {hasFact ? 'Прогноз (нед.)' : isRev ? 'Выручка (нед.)' : 'Кол-во (нед.)'}{' '}
              <SortIcon active={sortKey === 'forecast'} dir={sortDir} />
            </th>
            {hasFact && (
              <>
                <th className={`${thClass} text-right`} onClick={() => toggleSort('fact')}>
                  Факт <SortIcon active={sortKey === 'fact'} dir={sortDir} />
                </th>
                <th className={`${thClass} text-right`} onClick={() => toggleSort('deviation')}>
                  Откл. <SortIcon active={sortKey === 'deviation'} dir={sortDir} />
                </th>
              </>
            )}
            <th className="px-4 py-3 text-left text-xs font-medium tracking-wider text-slate-400 uppercase">
              Факторы
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/[0.04]">
          {sorted.map((r, i) => {
            const forecastVal = isRev ? r.predicted_revenue : r.predicted_quantity;
            const factVal = isRev ? r.actual_revenue : r.actual_quantity;
            const dev = isRev ? r.revenue_deviation_pct : r.deviation_pct;
            const isFallback = r.prediction_method === 'fallback';

            return (
              <tr
                key={`${r.dish_id}-${i}`}
                className={`hover:bg-white/[0.04] transition-colors ${isFallback && methodFilter === 'all' ? 'opacity-60' : ''}`}
              >
                <td className="px-4 py-3 text-sm font-medium text-white">
                  <span className={isFallback ? 'italic' : ''}>
                    {r.dish_name}
                  </span>
                  {isFallback && methodFilter === 'all' && (
                    <span className="ml-2 inline-block rounded bg-white/[0.06] px-1.5 py-0.5 text-[10px] text-slate-500 font-normal not-italic">
                      est.
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-right text-sm tabular-nums text-white">
                  {isRev
                    ? forecastVal > 0
                      ? `${formatRub(forecastVal)} \u20BD`
                      : '\u2014'
                    : forecastVal}
                </td>
                {hasFact && (
                  <>
                    <td className="px-4 py-3 text-right text-sm tabular-nums text-white">
                      {factVal != null
                        ? isRev
                          ? `${formatRub(factVal)} \u20BD`
                          : factVal
                        : '\u2014'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {dev != null ? (
                        <span
                          className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${deviationColor(dev)}`}
                        >
                          {dev > 0 ? '+' : ''}
                          {dev}%
                        </span>
                      ) : (
                        <span className="text-sm text-slate-600">{'\u2014'}</span>
                      )}
                    </td>
                  </>
                )}
                <td className="px-4 py-3 text-sm text-slate-400">
                  {r.key_factors.join(', ')}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {sorted.length === 0 && (
        <div className="py-8 text-center text-sm text-slate-500">
          Нет блюд для выбранного фильтра
        </div>
      )}
    </div>
  );
}
