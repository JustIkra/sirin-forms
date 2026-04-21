import type { DailyForecastResult, PlanFactSummary } from '../types/forecast';

interface Props {
  result: DailyForecastResult;
  summary?: PlanFactSummary;
}

function formatRub(n: number): string {
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
}

function mapeColor(mape: number): string {
  if (mape < 10) return 'text-green-400';
  if (mape < 20) return 'text-blue-400';
  if (mape < 30) return 'text-yellow-400';
  return 'text-red-400';
}

function accuracyColor(acc: number): string {
  if (acc >= 90) return 'text-green-400';
  if (acc >= 80) return 'text-blue-400';
  if (acc >= 70) return 'text-yellow-400';
  return 'text-red-400';
}

function revDeviationColor(predicted: number, actual: number): string {
  if (predicted === 0) return 'text-slate-400';
  const pct = Math.abs((actual - predicted) / predicted) * 100;
  if (pct <= 10) return 'text-green-400';
  if (pct <= 25) return 'text-yellow-400';
  return 'text-red-400';
}

function StatCell({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="stat-cell">
      <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest">
        {label}
      </span>
      <div className="mt-2">{children}</div>
    </div>
  );
}

export default function ForecastMeta({ result, summary }: Props) {
  const revDev =
    summary && summary.total_predicted_revenue > 0
      ? (summary.total_actual_revenue - summary.total_predicted_revenue) /
        summary.total_predicted_revenue *
        100
      : 0;

  const hasRevenue = summary && summary.total_actual_revenue > 0;

  return (
    <div className="stat-grid" data-testid="forecast-meta">
      <StatCell label={result.week_start ? "Неделя" : "Дата"}>
        <p className="text-xl font-bold text-white tabular-nums">
          {result.week_start
            ? `${result.week_start.slice(5)} — ${(result.week_end ?? '').slice(5)}`
            : result.date}
        </p>
      </StatCell>

      <StatCell label="Погода">
        <p className="text-sm font-semibold text-slate-200 leading-snug">
          {result.weather ?? 'Нет данных'}
        </p>
      </StatCell>

      <StatCell label="Праздник">
        <p className={`text-xl font-bold ${result.is_holiday ? 'text-amber-400' : 'text-slate-500'}`}>
          {result.is_holiday ? 'Да' : 'Нет'}
        </p>
      </StatCell>

      <StatCell label="Блюда">
        <div className="flex items-end gap-3">
          <span className="text-xl font-bold text-white tabular-nums">{result.forecasts.length}</span>
          <span className="text-xs text-slate-400">
            ML <span className="text-blue-400 font-semibold">{result.ml_count ?? 0}</span>
            {' / '}
            Fallback <span className="text-slate-500 font-semibold">{result.fallback_count ?? 0}</span>
          </span>
        </div>
      </StatCell>

      {summary && (
        <>
          <StatCell label="MAPE / Точность">
            <div className="flex items-end gap-2">
              <span className={`text-xl font-bold tabular-nums ${mapeColor(summary.mape)}`}>
                {summary.mape}%
              </span>
              <span className="text-slate-600 text-sm">/</span>
              <span className={`text-xl font-bold tabular-nums ${accuracyColor(summary.accuracy)}`}>
                {summary.accuracy}%
              </span>
            </div>
          </StatCell>

          <StatCell label="Кол-во: план / факт">
            <p className="text-xl font-bold text-white tabular-nums">
              {summary.total_predicted}
              <span className="text-slate-600 font-normal"> / </span>
              {summary.total_actual}
            </p>
          </StatCell>

          {hasRevenue && (
            <StatCell label="Выручка: план / факт">
              <p className="text-lg font-bold text-white tabular-nums leading-tight">
                {formatRub(summary.total_predicted_revenue)}
                <span className="text-slate-600 font-normal"> / </span>
                {formatRub(summary.total_actual_revenue)} &#8381;
              </p>
              <p className={`mt-1 text-xs font-semibold tabular-nums ${revDeviationColor(summary.total_predicted_revenue, summary.total_actual_revenue)}`}>
                {revDev > 0 ? '+' : ''}
                {revDev.toFixed(1)}% отклонение
              </p>
            </StatCell>
          )}
        </>
      )}
    </div>
  );
}
