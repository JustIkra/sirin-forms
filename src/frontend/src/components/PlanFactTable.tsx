import { useState, useCallback } from 'react';
import type { PlanFactRecord } from '../types/forecast';

interface Props {
  records: PlanFactRecord[];
}

function deviationColor(pct: number): string {
  const abs = Math.abs(pct);
  if (abs <= 15) return 'text-green-400 bg-green-500/10';
  if (abs <= 30) return 'text-yellow-400 bg-yellow-500/10';
  return 'text-red-400 bg-red-500/10';
}

function formatRub(n: number): string {
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
}

type ViewMode = 'quantity' | 'revenue';
type SortKey = 'name' | 'plan' | 'fact' | 'deviation';
type SortDir = 'asc' | 'desc';

function SortIcon({ active, dir }: { active: boolean; dir: SortDir }) {
  if (!active) return <span className="inline-block ml-1 text-slate-600">{'\u25BC'}</span>;
  return (
    <span className="inline-block ml-1 text-blue-400">
      {dir === 'asc' ? '\u25B2' : '\u25BC'}
    </span>
  );
}

export default function PlanFactTable({ records }: Props) {
  const [view, setView] = useState<ViewMode>('quantity');
  const [sortKey, setSortKey] = useState<SortKey>('deviation');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const hasRevenue = records.some((r) => r.actual_revenue > 0);

  const isRev = view === 'revenue';

  const sorted = [...records].sort((a, b) => {
    const mul = sortDir === 'asc' ? 1 : -1;
    switch (sortKey) {
      case 'name':
        return mul * a.dish_name.localeCompare(b.dish_name, 'ru');
      case 'plan':
        return mul * ((isRev ? a.predicted_revenue : a.predicted_quantity) - (isRev ? b.predicted_revenue : b.predicted_quantity));
      case 'fact':
        return mul * ((isRev ? a.actual_revenue : a.actual_quantity) - (isRev ? b.actual_revenue : b.actual_quantity));
      case 'deviation': {
        const da = isRev ? a.revenue_deviation_pct : a.deviation_pct;
        const db = isRev ? b.revenue_deviation_pct : b.deviation_pct;
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

  return (
    <div className="overflow-hidden glass-card">
      {hasRevenue && (
        <div className="flex gap-1 border-b border-white/[0.06] bg-white/[0.02] px-4 py-2">
          <button
            onClick={() => setView('quantity')}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
              view === 'quantity'
                ? 'bg-white/10 text-white'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Количество
          </button>
          <button
            onClick={() => setView('revenue')}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
              view === 'revenue'
                ? 'bg-white/10 text-white'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Выручка
          </button>
        </div>
      )}
      <table className="min-w-full divide-y divide-white/[0.06]">
        <thead className="bg-white/[0.03]">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium tracking-wider text-slate-400 uppercase cursor-pointer select-none hover:text-slate-200 transition-colors" onClick={() => toggleSort('name')}>
              Блюдо <SortIcon active={sortKey === 'name'} dir={sortDir} />
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium tracking-wider text-slate-400 uppercase cursor-pointer select-none hover:text-slate-200 transition-colors" onClick={() => toggleSort('plan')}>
              План <SortIcon active={sortKey === 'plan'} dir={sortDir} />
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium tracking-wider text-slate-400 uppercase cursor-pointer select-none hover:text-slate-200 transition-colors" onClick={() => toggleSort('fact')}>
              Факт <SortIcon active={sortKey === 'fact'} dir={sortDir} />
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium tracking-wider text-slate-400 uppercase cursor-pointer select-none hover:text-slate-200 transition-colors" onClick={() => toggleSort('deviation')}>
              Отклонение <SortIcon active={sortKey === 'deviation'} dir={sortDir} />
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/[0.04]">
          {sorted.map((r, i) => {
            const plan = isRev ? r.predicted_revenue : r.predicted_quantity;
            const fact = isRev ? r.actual_revenue : r.actual_quantity;
            const dev = isRev ? r.revenue_deviation_pct : r.deviation_pct;
            return (
              <tr key={`${r.dish_id}-${i}`} className="hover:bg-white/[0.04]">
                <td className="px-4 py-3 text-sm font-medium text-white">
                  {r.dish_name}
                </td>
                <td className="px-4 py-3 text-right text-sm tabular-nums text-white">
                  {isRev ? `${formatRub(plan)} \u20BD` : plan}
                </td>
                <td className="px-4 py-3 text-right text-sm tabular-nums text-white">
                  {isRev ? `${formatRub(fact)} \u20BD` : fact}
                </td>
                <td className="px-4 py-3 text-right">
                  <span
                    className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${deviationColor(dev)}`}
                  >
                    {dev > 0 ? '+' : ''}{dev}%
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
