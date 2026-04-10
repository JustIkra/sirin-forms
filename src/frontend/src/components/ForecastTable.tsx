import { useState, useCallback } from 'react';
import type { DishForecast, PlanFactRecord } from '../types/forecast';

interface Props {
  forecasts: DishForecast[];
  planFact?: PlanFactRecord[];
}

type SortKey = 'name' | 'qty' | 'revenue' | 'fact_qty' | 'fact_revenue';
type SortDir = 'asc' | 'desc';

function formatRub(n: number): string {
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
}

function SortIcon({ active, dir }: { active: boolean; dir: SortDir }) {
  if (!active) return <span className="inline-block ml-1 text-slate-600">{'\u25BC'}</span>;
  return (
    <span className="inline-block ml-1 text-blue-400">
      {dir === 'asc' ? '\u25B2' : '\u25BC'}
    </span>
  );
}

export default function ForecastTable({ forecasts, planFact }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>('qty');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const pfMap = new Map<string, PlanFactRecord>();
  if (planFact) {
    for (const r of planFact) {
      pfMap.set(r.dish_id, r);
      pfMap.set(r.dish_name.toLowerCase(), r);
    }
  }

  const hasFact = planFact && planFact.length > 0;

  const getPF = (f: DishForecast): PlanFactRecord | null => {
    if (!hasFact) return null;
    return pfMap.get(f.dish_id) ?? pfMap.get(f.dish_name.toLowerCase()) ?? null;
  };

  const getRevenue = (f: DishForecast): number => {
    const pf = getPF(f);
    if (pf && pf.predicted_revenue > 0) return pf.predicted_revenue;
    if (f.price) return f.predicted_quantity * f.price;
    return 0;
  };

  const sorted = [...forecasts].sort((a, b) => {
    const mul = sortDir === 'asc' ? 1 : -1;
    switch (sortKey) {
      case 'name':
        return mul * a.dish_name.localeCompare(b.dish_name, 'ru');
      case 'qty':
        return mul * (a.predicted_quantity - b.predicted_quantity);
      case 'revenue':
        return mul * (getRevenue(a) - getRevenue(b));
      case 'fact_qty': {
        const pa = getPF(a)?.actual_quantity ?? 0;
        const pb = getPF(b)?.actual_quantity ?? 0;
        return mul * (pa - pb);
      }
      case 'fact_revenue': {
        const ra = getPF(a)?.actual_revenue ?? 0;
        const rb = getPF(b)?.actual_revenue ?? 0;
        return mul * (ra - rb);
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

  return (
    <div className="overflow-hidden glass-card">
      <table className="min-w-full divide-y divide-white/[0.06]">
        <thead className="bg-white/[0.03]">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium tracking-wider text-slate-400 uppercase cursor-pointer select-none hover:text-slate-200 transition-colors" onClick={() => toggleSort('name')}>
              Блюдо <SortIcon active={sortKey === 'name'} dir={sortDir} />
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium tracking-wider text-slate-400 uppercase cursor-pointer select-none hover:text-slate-200 transition-colors" onClick={() => toggleSort('qty')}>
              Кол-во <SortIcon active={sortKey === 'qty'} dir={sortDir} />
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium tracking-wider text-slate-400 uppercase cursor-pointer select-none hover:text-slate-200 transition-colors" onClick={() => toggleSort('revenue')}>
              Выручка <SortIcon active={sortKey === 'revenue'} dir={sortDir} />
            </th>
            {hasFact && (
              <>
                <th className="px-4 py-3 text-right text-xs font-medium tracking-wider text-slate-400 uppercase cursor-pointer select-none hover:text-slate-200 transition-colors" onClick={() => toggleSort('fact_qty')}>
                  Факт кол-во <SortIcon active={sortKey === 'fact_qty'} dir={sortDir} />
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium tracking-wider text-slate-400 uppercase cursor-pointer select-none hover:text-slate-200 transition-colors" onClick={() => toggleSort('fact_revenue')}>
                  Факт выручка <SortIcon active={sortKey === 'fact_revenue'} dir={sortDir} />
                </th>
              </>
            )}
            <th className="px-4 py-3 text-left text-xs font-medium tracking-wider text-slate-400 uppercase">
              Факторы
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/[0.04]">
          {sorted.map((f, i) => {
            const pf = getPF(f);
            return (
              <tr key={`${f.dish_id}-${i}`} className="hover:bg-white/[0.04]">
                <td className="px-4 py-3 text-sm font-medium text-white">
                  {f.dish_name}
                </td>
                <td className="px-4 py-3 text-right text-sm tabular-nums text-white">
                  {f.predicted_quantity}
                </td>
                <td className="px-4 py-3 text-right text-sm tabular-nums text-slate-300">
                  {pf && pf.predicted_revenue > 0
                    ? `${formatRub(pf.predicted_revenue)} \u20BD`
                    : f.price
                      ? `${formatRub(f.predicted_quantity * f.price)} \u20BD`
                      : '\u2014'}
                </td>
                {hasFact && (
                  <>
                    <td className="px-4 py-3 text-right text-sm tabular-nums text-white">
                      {pf ? pf.actual_quantity : '\u2014'}
                    </td>
                    <td className="px-4 py-3 text-right text-sm tabular-nums text-slate-300">
                      {pf
                        ? `${formatRub(pf.actual_revenue)} \u20BD`
                        : '\u2014'}
                    </td>
                  </>
                )}
                <td className="px-4 py-3 text-sm text-slate-400">
                  {f.key_factors.join(', ')}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
