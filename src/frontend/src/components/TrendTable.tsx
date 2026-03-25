import type { DishTrend } from '../types/forecast';

interface Props {
  trends: DishTrend[];
}

function trendBadge(direction: DishTrend['trend_direction']): {
  label: string;
  className: string;
} {
  switch (direction) {
    case 'growing':
      return {
        label: 'рост',
        className: 'text-green-700 bg-green-50',
      };
    case 'declining':
      return {
        label: 'падение',
        className: 'text-red-700 bg-red-50',
      };
    case 'stable':
      return {
        label: 'стабильно',
        className: 'text-slate-600 bg-slate-100',
      };
  }
}

function Sparkline({ data }: { data: number[] }) {
  if (data.length < 2) return null;

  const width = 80;
  const height = 20;
  const padding = 2;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data
    .map((v, i) => {
      const x = padding + (i / (data.length - 1)) * (width - padding * 2);
      const y = height - padding - ((v - min) / range) * (height - padding * 2);
      return `${x},${y}`;
    })
    .join(' ');

  const trending = data[data.length - 1] >= data[0];
  const stroke = trending ? '#22c55e' : '#ef4444';

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="inline-block align-middle"
    >
      <polyline
        points={points}
        fill="none"
        stroke={stroke}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function TrendTable({ trends }: Props) {
  const sorted = [...trends].sort(
    (a, b) => Math.abs(b.change_pct) - Math.abs(a.change_pct),
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
              Сред./нед (текущие)
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium tracking-wider text-slate-500 uppercase">
              Сред./нед (прежние)
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium tracking-wider text-slate-500 uppercase">
              Изменение %
            </th>
            <th className="px-4 py-3 text-center text-xs font-medium tracking-wider text-slate-500 uppercase">
              Тренд
            </th>
            <th className="px-4 py-3 text-center text-xs font-medium tracking-wider text-slate-500 uppercase">
              Сезонность
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {sorted.map((t) => {
            const badge = trendBadge(t.trend_direction);
            return (
              <tr key={t.dish_name} className="hover:bg-slate-50">
                <td className="px-4 py-3 text-sm font-medium text-slate-900">
                  {t.dish_name}
                </td>
                <td className="px-4 py-3 text-right text-sm tabular-nums text-slate-900">
                  {t.current_weekly_avg.toFixed(1)}
                </td>
                <td className="px-4 py-3 text-right text-sm tabular-nums text-slate-900">
                  {t.prev_weekly_avg.toFixed(1)}
                </td>
                <td className="px-4 py-3 text-right">
                  <span
                    className={`text-sm tabular-nums font-medium ${
                      t.change_pct > 0
                        ? 'text-green-600'
                        : t.change_pct < 0
                          ? 'text-red-600'
                          : 'text-slate-600'
                    }`}
                  >
                    {t.change_pct > 0 ? '+' : ''}
                    {t.change_pct.toFixed(1)}%
                  </span>
                </td>
                <td className="px-4 py-3 text-center">
                  <span
                    className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${badge.className}`}
                  >
                    {badge.label}
                  </span>
                </td>
                <td className="px-4 py-3 text-center">
                  <Sparkline data={t.weekly_data} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
