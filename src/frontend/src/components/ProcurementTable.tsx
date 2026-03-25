import type { IngredientNeed } from '../types/forecast';

interface Props {
  items: IngredientNeed[];
}

export default function ProcurementTable({ items }: Props) {
  const sorted = [...items].sort(
    (a, b) => b.buffered_amount - a.buffered_amount,
  );

  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
      <table className="min-w-full divide-y divide-slate-200">
        <thead className="bg-slate-50">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium tracking-wider text-slate-500 uppercase">
              Ингредиент
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium tracking-wider text-slate-500 uppercase">
              Потребность (кг)
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium tracking-wider text-slate-500 uppercase">
              К закупке (кг)
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium tracking-wider text-slate-500 uppercase">
              Ед.
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {sorted.map((item) => (
            <tr
              key={item.ingredient_id}
              className={
                item.buffered_amount > 0
                  ? 'bg-red-50 hover:bg-red-100'
                  : 'hover:bg-slate-50'
              }
            >
              <td className="px-4 py-3 text-sm font-medium text-slate-900">
                {item.ingredient_name}
              </td>
              <td className="px-4 py-3 text-right text-sm tabular-nums text-slate-900">
                {item.required_amount.toFixed(2)}
              </td>
              <td
                className={`px-4 py-3 text-right text-sm tabular-nums font-medium ${
                  item.buffered_amount > 0 ? 'text-red-700' : 'text-slate-900'
                }`}
              >
                {item.buffered_amount.toFixed(2)}
              </td>
              <td className="px-4 py-3 text-sm text-slate-600">
                {item.unit}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
