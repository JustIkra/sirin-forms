import type { DailyForecastResult } from '../types/forecast';

interface Props {
  result: DailyForecastResult;
}

export default function ForecastMeta({ result }: Props) {
  return (
    <div className="space-y-4">
      <div className="glass-card px-6 py-5">
        <div className="grid gap-6 sm:grid-cols-3">
          <div>
            <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">Дата</span>
            <p className="mt-2 text-2xl font-bold text-white tabular-nums">{result.date}</p>
          </div>

          <div>
            <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">Погода</span>
            <p className="mt-2 text-base font-semibold text-slate-200 leading-snug">
              {result.weather ?? 'Нет данных'}
            </p>
          </div>

          <div>
            <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">Праздник</span>
            <p className={`mt-2 text-2xl font-bold ${result.is_holiday ? 'text-amber-400' : 'text-slate-400'}`}>
              {result.is_holiday ? 'Да' : 'Нет'}
            </p>
          </div>
        </div>
      </div>

      {result.notes && (
        <div className="glass-card px-6 py-5">
          <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">Заметки</span>
          <p className="mt-2 text-sm text-slate-300 leading-relaxed">{result.notes}</p>
        </div>
      )}
    </div>
  );
}
