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
import type { DishTrend } from '../types/forecast';

interface Props {
  growing: DishTrend[];
  declining: DishTrend[];
}

interface ChartDatum {
  name: string;
  fullName: string;
  change_pct: number;
  current_weekly_avg: number;
  prev_weekly_avg: number;
  direction: 'growing' | 'declining';
}

const COLOR_GROWING = '#22c55e';
const COLOR_DECLINING = '#ef4444';

function truncate(text: string, max: number): string {
  return text.length > max ? text.slice(0, max - 1) + '\u2026' : text;
}

export default function TrendChart({ growing, declining }: Props) {
  const data: ChartDatum[] = [
    ...growing.map((d) => ({
      name: truncate(d.dish_name, 20),
      fullName: d.dish_name,
      change_pct: d.change_pct,
      current_weekly_avg: d.current_weekly_avg,
      prev_weekly_avg: d.prev_weekly_avg,
      direction: 'growing' as const,
    })),
    ...declining.map((d) => ({
      name: truncate(d.dish_name, 20),
      fullName: d.dish_name,
      change_pct: d.change_pct,
      current_weekly_avg: d.current_weekly_avg,
      prev_weekly_avg: d.prev_weekly_avg,
      direction: 'declining' as const,
    })),
  ].sort((a, b) => a.change_pct - b.change_pct);

  const height = Math.max(300, data.length * 32);

  return (
    <div className="glass-card p-4">
      <h3 className="mb-3 text-sm font-medium text-slate-300">
        Изменение спроса, %
      </h3>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} layout="vertical" margin={{ left: 120, right: 20 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#ffffff10" />
          <XAxis type="number" tick={{ fontSize: 12, fill: '#94a3b8' }} tickFormatter={(v: number) => `${v}%`} />
          <YAxis
            type="category"
            dataKey="name"
            width={110}
            tick={{ fontSize: 12, fill: '#94a3b8' }}
          />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const d = payload[0].payload as ChartDatum;
              return (
                <div className="rounded-lg border border-white/10 bg-[#1a1a1a] px-3 py-2 text-xs shadow-xl">
                  <p className="mb-1 font-medium text-white">{d.fullName}</p>
                  <p className="text-slate-400">
                    Изменение:{' '}
                    <span
                      className={
                        d.change_pct >= 0 ? 'text-green-400' : 'text-red-400'
                      }
                    >
                      {d.change_pct > 0 ? '+' : ''}
                      {d.change_pct.toFixed(1)}%
                    </span>
                  </p>
                  <p className="text-slate-400">
                    Сред./нед текущие: {d.current_weekly_avg.toFixed(1)}
                  </p>
                  <p className="text-slate-400">
                    Сред./нед прежние: {d.prev_weekly_avg.toFixed(1)}
                  </p>
                </div>
              );
            }}
          />
          <Bar dataKey="change_pct" radius={[0, 4, 4, 0]}>
            {data.map((entry, i) => (
              <Cell
                key={i}
                fill={entry.direction === 'growing' ? COLOR_GROWING : COLOR_DECLINING}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
