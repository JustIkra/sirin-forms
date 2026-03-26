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
        className: 'text-green-400 bg-green-500/10',
      };
    case 'declining':
      return {
        label: 'падение',
        className: 'text-red-400 bg-red-500/10',
      };
    case 'stable':
      return {
        label: 'стабильно',
        className: 'text-slate-400 bg-white/[0.06]',
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
    <div className="overflow-hidden glass-card">
      <table className="min-w-full divide-y divide-white/[0.06]">
        <thead className="bg-white/[0.03]">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium tracking-wider text-slate-400 uppercase">
              Блюдо
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium tracking-wider text-slate-400 uppercase">
              Сред./нед (текущие)
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium tracking-wider text-slate-400 uppercase">
              Сред./нед (прежние)
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium tracking-wider text-slate-400 uppercase">
              Изменение %
            </th>
            <th className="px-4 py-3 text-center text-xs font-medium tracking-wider text-slate-400 uppercase">
              Тренд
            </th>
            <th className="px-4 py-3 text-center text-xs font-medium tracking-wider text-slate-400 uppercase">
              Сезонность
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/[0.04]">
          {sorted.map((t) => {
            const badge = trendBadge(t.trend_direction);
            return (
              <tr key={t.dish_name} className="hover:bg-white/[0.04]">
                <td className="px-4 py-3 text-sm font-medium text-white">
                  {t.dish_name}
                </td>
                <td className="px-4 py-3 text-right text-sm tabular-nums text-white">
                  {t.current_weekly_avg.toFixed(1)}
                </td>
                <td className="px-4 py-3 text-right text-sm tabular-nums text-white">
                  {t.prev_weekly_avg.toFixed(1)}
                </td>
                <td className="px-4 py-3 text-right">
                  <span
                    className={`text-sm tabular-nums font-medium ${
                      t.change_pct > 0
                        ? 'text-green-400'
                        : t.change_pct < 0
                          ? 'text-red-400'
                          : 'text-slate-400'
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
