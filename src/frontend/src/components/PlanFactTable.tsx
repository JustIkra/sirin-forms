import type { PlanFactRecord } from '../types/forecast';

interface Props {
  records: PlanFactRecord[];
}

function deviationColor(pct: number): string {
  const abs = Math.abs(pct);
  if (abs <= 15) return 'text-green-700 bg-green-50';
  if (abs <= 30) return 'text-yellow-700 bg-yellow-50';
  return 'text-red-700 bg-red-50';
}

export default function PlanFactTable({ records }: Props) {
  const sorted = [...records].sort(
    (a, b) => Math.abs(b.deviation_pct) - Math.abs(a.deviation_pct),
  );

  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
      <table className="min-w-full divide-y divide-slate-200">
        <thead className="bg-slate-50">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium tracking-wider text-slate-500 uppercase">
              Блюдо
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium tracking-wider text-slate-500 uppercase">
              Прогноз
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium tracking-wider text-slate-500 uppercase">
              Факт
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium tracking-wider text-slate-500 uppercase">
              Отклонение
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {sorted.map((r) => (
            <tr key={r.dish_id} className="hover:bg-slate-50">
              <td className="px-4 py-3 text-sm font-medium text-slate-900">
                {r.dish_name}
              </td>
              <td className="px-4 py-3 text-right text-sm tabular-nums text-slate-900">
                {r.predicted_quantity}
              </td>
              <td className="px-4 py-3 text-right text-sm tabular-nums text-slate-900">
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
