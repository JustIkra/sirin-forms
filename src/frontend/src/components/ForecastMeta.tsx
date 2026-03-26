import type { DailyForecastResult } from '../types/forecast';

interface Props {
  result: DailyForecastResult;
}

const METHOD_LABELS: Record<string, { label: string; color: string }> = {
  llm: { label: 'ИИ (LLM)', color: 'bg-purple-500/15 text-purple-400' },
  ml: { label: 'ML (статистика)', color: 'bg-emerald-500/15 text-emerald-400' },
};

export default function ForecastMeta({ result }: Props) {
  const avgConfidence =
    result.forecasts.length > 0
      ? result.forecasts.reduce((s, f) => s + f.confidence, 0) /
        result.forecasts.length
      : 0;

  const methodInfo = METHOD_LABELS[result.method] ?? METHOD_LABELS.llm;

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
      <Card label="Дата" value={result.date} />
      <div className="glass-card p-4">
        <span className="text-xs font-medium text-slate-400 uppercase">Метод</span>
        <p className="mt-1">
          <span className={`inline-block rounded-full px-3 py-1 text-sm font-semibold ${methodInfo.color}`}>
            {methodInfo.label}
          </span>
        </p>
      </div>
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
        <div className="glass-card p-4 sm:col-span-2 lg:col-span-5">
          <span className="text-xs font-medium text-slate-400 uppercase">Заметки</span>
          <p className="mt-1 text-sm text-slate-300">{result.notes}</p>
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
    <div className="glass-card p-4">
      <span className="text-xs font-medium text-slate-400 uppercase">{label}</span>
      <p
        className={`mt-1 text-lg font-semibold ${accent ? 'text-amber-400' : 'text-white'}`}
      >
        {value}
      </p>
    </div>
  );
}
