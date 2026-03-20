import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import type { DishForecast } from '../types/forecast';

interface Props {
  forecasts: DishForecast[];
}

function barColor(confidence: number): string {
  if (confidence >= 0.7) return '#16a34a';
  if (confidence >= 0.4) return '#ca8a04';
  return '#dc2626';
}

export default function ForecastChart({ forecasts }: Props) {
  const data = [...forecasts]
    .sort((a, b) => a.predicted_quantity - b.predicted_quantity)
    .map((f) => ({
      name: f.dish_name.length > 25 ? f.dish_name.slice(0, 22) + '...' : f.dish_name,
      qty: f.predicted_quantity,
      confidence: f.confidence,
    }));

  const height = Math.max(300, data.length * 32);

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="mb-3 text-sm font-medium text-slate-700">
        Прогноз по блюдам
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
            formatter={(value) => [`${value} порций`, 'Прогноз']}
          />
          <Bar dataKey="qty" radius={[0, 4, 4, 0]}>
            {data.map((entry, i) => (
              <Cell key={i} fill={barColor(entry.confidence)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
