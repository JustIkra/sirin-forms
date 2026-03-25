import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import type { PlanFactRecord } from '../types/forecast';

interface Props {
  records: PlanFactRecord[];
}

export default function PlanFactChart({ records }: Props) {
  const data = [...records]
    .sort((a, b) => a.predicted_quantity - b.predicted_quantity)
    .map((r) => ({
      name: r.dish_name.length > 25 ? r.dish_name.slice(0, 22) + '...' : r.dish_name,
      predicted: r.predicted_quantity,
      actual: r.actual_quantity,
    }));

  const height = Math.max(300, data.length * 36);

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="mb-3 text-sm font-medium text-slate-700">
        План-факт по блюдам
      </h3>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} layout="vertical" margin={{ left: 120, right: 20 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" />
          <YAxis
            type="category"
            dataKey="name"
            width={110}
            tick={{ fontSize: 12 }}
          />
          <Tooltip
            formatter={(value, name) => [
              `${value} порций`,
              name === 'predicted' ? 'Прогноз' : 'Факт',
            ]}
          />
          <Legend
            formatter={(value: string) =>
              value === 'predicted' ? 'Прогноз' : 'Факт'
            }
          />
          <Bar dataKey="predicted" fill="#3b82f6" radius={[0, 4, 4, 0]} />
          <Bar dataKey="actual" fill="#22c55e" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
