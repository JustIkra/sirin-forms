import type { DishForecast, PlanFactRecord } from '../types/forecast';

interface Props {
  forecasts: DishForecast[];
  planFact?: PlanFactRecord[];
}

function formatRub(n: number): string {
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
}

export default function ForecastTable({ forecasts, planFact }: Props) {
  const sorted = [...forecasts].sort(
    (a, b) => b.predicted_quantity - a.predicted_quantity,
  );

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
              Выручка
            </th>
            {hasFact && (
              <>
                <th className="px-4 py-3 text-right text-xs font-medium tracking-wider text-slate-400 uppercase">
                  Факт кол-во
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium tracking-wider text-slate-400 uppercase">
                  Факт выручка
                </th>
              </>
            )}
            <th className="px-4 py-3 text-left text-xs font-medium tracking-wider text-slate-400 uppercase">
              Факторы
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/[0.04]">
          {sorted.map((f) => {
            const pf = getPF(f);
            return (
              <tr key={f.dish_id} className="hover:bg-white/[0.04]">
                <td className="px-4 py-3 text-sm font-medium text-white">
                  {f.dish_name}
                </td>
                <td className="px-4 py-3 text-right text-sm tabular-nums text-white">
                  {f.predicted_quantity}
                </td>
                <td className="px-4 py-3 text-right text-sm tabular-nums text-slate-300">
                  {pf && pf.predicted_revenue > 0
                    ? `${formatRub(pf.predicted_revenue)} ₽`
                    : f.price
                      ? `${formatRub(f.predicted_quantity * f.price)} ₽`
                      : '—'}
                </td>
                {hasFact && (
                  <>
                    <td className="px-4 py-3 text-right text-sm tabular-nums text-white">
                      {pf ? pf.actual_quantity : '—'}
                    </td>
                    <td className="px-4 py-3 text-right text-sm tabular-nums text-slate-300">
                      {pf && pf.actual_revenue > 0
                        ? `${formatRub(pf.actual_revenue)} ₽`
                        : '—'}
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
