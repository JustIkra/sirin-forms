import { useState } from 'react';
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

export default function PlanFactTable({ records }: Props) {
  const [view, setView] = useState<ViewMode>('quantity');
  const hasRevenue = records.some((r) => r.actual_revenue > 0);

  const sorted = [...records].sort((a, b) =>
    view === 'revenue'
      ? Math.abs(b.revenue_deviation_pct) - Math.abs(a.revenue_deviation_pct)
      : Math.abs(b.deviation_pct) - Math.abs(a.deviation_pct),
  );

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
            <th className="px-4 py-3 text-left text-xs font-medium tracking-wider text-slate-400 uppercase">
              Блюдо
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium tracking-wider text-slate-400 uppercase">
              План
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium tracking-wider text-slate-400 uppercase">
              Факт
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium tracking-wider text-slate-400 uppercase">
              Отклонение
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/[0.04]">
          {sorted.map((r) => {
            const isRev = view === 'revenue';
            const plan = isRev ? r.predicted_revenue : r.predicted_quantity;
            const fact = isRev ? r.actual_revenue : r.actual_quantity;
            const dev = isRev ? r.revenue_deviation_pct : r.deviation_pct;
            return (
              <tr key={r.dish_id} className="hover:bg-white/[0.04]">
                <td className="px-4 py-3 text-sm font-medium text-white">
                  {r.dish_name}
                </td>
                <td className="px-4 py-3 text-right text-sm tabular-nums text-white">
                  {isRev ? `${formatRub(plan)} ₽` : plan}
                </td>
                <td className="px-4 py-3 text-right text-sm tabular-nums text-white">
                  {isRev ? `${formatRub(fact)} ₽` : fact}
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
