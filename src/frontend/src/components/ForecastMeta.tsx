import type { DailyForecastResult } from '../types/forecast';

interface Props {
  result: DailyForecastResult;
}

export default function ForecastMeta({ result }: Props) {
  const avgConfidence =
    result.forecasts.length > 0
      ? result.forecasts.reduce((s, f) => s + f.confidence, 0) /
        result.forecasts.length
      : 0;

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Card label="Дата" value={result.date} />
      <Card
        label="Погода"
        value={result.weather ?? 'Нет данных'}
      />
      <Card
        label="Праздник"
        value={result.is_holiday ? 'Да' : 'Нет'}
        accent={result.is_holiday}
      />
      <Card
        label="Средняя уверенность"
        value={`${Math.round(avgConfidence * 100)}%`}
      />
      {result.notes && (
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm sm:col-span-2 lg:col-span-4">
          <span className="text-xs font-medium text-slate-500 uppercase">Заметки</span>
          <p className="mt-1 text-sm text-slate-700">{result.notes}</p>
        </div>
      )}
    </div>
  );
}

function Card({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <span className="text-xs font-medium text-slate-500 uppercase">{label}</span>
      <p
        className={`mt-1 text-lg font-semibold ${accent ? 'text-amber-600' : 'text-slate-900'}`}
      >
        {value}
      </p>
    </div>
  );
}
