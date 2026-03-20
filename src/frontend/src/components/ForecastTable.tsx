import type { DishForecast } from '../types/forecast';

interface Props {
  forecasts: DishForecast[];
}

function confidenceColor(c: number): string {
  if (c >= 0.7) return 'text-green-700 bg-green-50';
  if (c >= 0.4) return 'text-yellow-700 bg-yellow-50';
  return 'text-red-700 bg-red-50';
}

export default function ForecastTable({ forecasts }: Props) {
  const sorted = [...forecasts].sort(
    (a, b) => b.predicted_quantity - a.predicted_quantity,
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
              Кол-во
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium tracking-wider text-slate-500 uppercase">
              Уверенность
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium tracking-wider text-slate-500 uppercase">
              Факторы
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {sorted.map((f) => (
            <tr key={f.dish_id} className="hover:bg-slate-50">
              <td className="px-4 py-3 text-sm font-medium text-slate-900">
                {f.dish_name}
              </td>
              <td className="px-4 py-3 text-right text-sm tabular-nums text-slate-900">
                {f.predicted_quantity}
              </td>
              <td className="px-4 py-3 text-right">
                <span
                  className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${confidenceColor(f.confidence)}`}
                >
                  {Math.round(f.confidence * 100)}%
                </span>
              </td>
              <td className="px-4 py-3 text-sm text-slate-600">
                {f.key_factors.join(', ')}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
