import type { IngredientNeed } from '../types/forecast';

interface Props {
  items: IngredientNeed[];
}

export default function ProcurementTable({ items }: Props) {
  const sorted = [...items].sort(
    (a, b) => b.buffered_amount - a.buffered_amount,
  );

  return (
    <div className="overflow-hidden glass-card">
      <table className="min-w-full divide-y divide-white/[0.06]">
        <thead className="bg-white/[0.03]">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium tracking-wider text-slate-400 uppercase">
              Ингредиент
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium tracking-wider text-slate-400 uppercase">
              Потребность (кг)
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium tracking-wider text-slate-400 uppercase">
              К закупке (кг)
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium tracking-wider text-slate-400 uppercase">
              Ед.
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/[0.04]">
          {sorted.map((item) => (
            <tr
              key={item.ingredient_id}
              className={
                item.buffered_amount > 0
                  ? 'bg-red-500/10 hover:bg-red-500/15'
                  : 'hover:bg-white/[0.04]'
              }
            >
              <td className="px-4 py-3 text-sm font-medium text-white">
                {item.ingredient_name}
              </td>
              <td className="px-4 py-3 text-right text-sm tabular-nums text-white">
                {item.required_amount.toFixed(2)}
              </td>
              <td
                className={`px-4 py-3 text-right text-sm tabular-nums font-medium ${
                  item.buffered_amount > 0 ? 'text-red-400' : 'text-white'
                }`}
              >
                {item.buffered_amount.toFixed(2)}
              </td>
              <td className="px-4 py-3 text-sm text-slate-400">
                {item.unit}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
