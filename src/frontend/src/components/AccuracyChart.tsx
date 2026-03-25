import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceDot,
} from 'recharts';
import type { AccuracyDayRecord } from '../types/forecast';

interface Props {
  days: AccuracyDayRecord[];
}

interface ChartRow {
  date: string;
  fullDate: string;
  ml: number | null;
  llm: number | null;
  isHoliday: boolean;
  holidayName: string | null;
}

function formatDate(iso: string): string {
  const d = new Date(iso + 'T00:00:00');
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
}

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: Array<{ value: number | null; dataKey: string; color: string; payload?: any }>;
  label?: string;
}) {
  if (!active || !payload || payload.length === 0) return null;

  const row = (payload[0]?.payload ?? {}) as ChartRow | undefined;

  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-md">
      <p className="text-sm font-medium text-slate-900">{row?.fullDate ?? label}</p>
      {row?.isHoliday && row.holidayName && (
        <p className="text-xs text-amber-600">{row.holidayName}</p>
      )}
      <div className="mt-1 space-y-0.5">
        {payload.map((entry) => (
          <p key={entry.dataKey} className="text-sm" style={{ color: entry.color }}>
            {entry.dataKey === 'ml' ? 'ML-прогноз' : 'ИИ-прогноз'}:{' '}
            {entry.value != null ? `${entry.value.toFixed(1)}%` : 'нет данных'}
          </p>
        ))}
      </div>
    </div>
  );
}

export default function AccuracyChart({ days }: Props) {
  const data: ChartRow[] = days.map((d) => ({
    date: formatDate(d.date),
    fullDate: d.date,
    ml: d.ml?.accuracy ?? null,
    llm: d.llm?.accuracy ?? null,
    isHoliday: d.is_holiday,
    holidayName: d.holiday_name,
  }));

  const holidays = data.filter((d) => d.isHoliday);

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="mb-3 text-sm font-medium text-slate-700">
        Точность прогнозов по дням
      </h3>
      <ResponsiveContainer width="100%" height={350}>
        <LineChart data={data} margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 12 }}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fontSize: 12 }}
            tickFormatter={(v: number) => `${v}%`}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            formatter={(value: string) =>
              value === 'ml' ? 'ML-прогноз' : 'ИИ-прогноз'
            }
          />
          <Line
            type="monotone"
            dataKey="ml"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={{ r: 3 }}
            activeDot={{ r: 5 }}
            connectNulls
            name="ml"
          />
          <Line
            type="monotone"
            dataKey="llm"
            stroke="#8b5cf6"
            strokeWidth={2}
            dot={{ r: 3 }}
            activeDot={{ r: 5 }}
            connectNulls
            name="llm"
          />
          {holidays.map((h) => (
            <ReferenceDot
              key={`holiday-ml-${h.fullDate}`}
              x={h.date}
              y={h.ml ?? h.llm ?? 50}
              r={6}
              fill="#f59e0b"
              stroke="#d97706"
              strokeWidth={2}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
      {holidays.length > 0 && (
        <p className="mt-2 text-xs text-slate-500">
          <span className="mr-1.5 inline-block h-2.5 w-2.5 rounded-full bg-amber-400" />
          Праздничные дни
        </p>
      )}
    </div>
  );
}
