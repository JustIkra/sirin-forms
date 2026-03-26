import type { DishForecast } from '../types/forecast';

interface Props {
  forecasts: DishForecast[];
}

function confidenceColor(c: number): string {
  if (c >= 0.7) return 'text-green-400 bg-green-500/10';
  if (c >= 0.4) return 'text-yellow-400 bg-yellow-500/10';
  return 'text-red-400 bg-red-500/10';
}

export default function ForecastTable({ forecasts }: Props) {
  const sorted = [...forecasts].sort(
    (a, b) => b.predicted_quantity - a.predicted_quantity,
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
              Кол-во
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium tracking-wider text-slate-400 uppercase">
              Уверенность
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium tracking-wider text-slate-400 uppercase">
              Факторы
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/[0.04]">
          {sorted.map((f) => (
            <tr key={f.dish_id} className="hover:bg-white/[0.04]">
              <td className="px-4 py-3 text-sm font-medium text-white">
                {f.dish_name}
              </td>
              <td className="px-4 py-3 text-right text-sm tabular-nums text-white">
                {f.predicted_quantity}
              </td>
              <td className="px-4 py-3 text-right">
                <span
                  className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${confidenceColor(f.confidence)}`}
                >
                  {Math.round(f.confidence * 100)}%
                </span>
              </td>
              <td className="px-4 py-3 text-sm text-slate-400">
                {f.key_factors.join(', ')}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
