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

export default function PlanFactTable({ records }: Props) {
  const sorted = [...records].sort(
    (a, b) => Math.abs(b.deviation_pct) - Math.abs(a.deviation_pct),
  );

  return (
    <div className="overflow-hidden glass-card">
      <table className="min-w-full divide-y divide-white/[0.06]">
        <thead className="bg-white/[0.03]">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium tracking-wider text-slate-400 uppercase">
              Блюдо
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium tracking-wider text-slate-400 uppercase">
              Прогноз
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
          {sorted.map((r) => (
            <tr key={r.dish_id} className="hover:bg-white/[0.04]">
              <td className="px-4 py-3 text-sm font-medium text-white">
                {r.dish_name}
              </td>
              <td className="px-4 py-3 text-right text-sm tabular-nums text-white">
                {r.predicted_quantity}
              </td>
              <td className="px-4 py-3 text-right text-sm tabular-nums text-white">
                {r.actual_quantity}
              </td>
              <td className="px-4 py-3 text-right">
                <span
                  className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${deviationColor(r.deviation_pct)}`}
                >
                  {r.deviation_pct > 0 ? '+' : ''}{r.deviation_pct}%
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
