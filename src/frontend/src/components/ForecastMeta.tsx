import type { DailyForecastResult, PlanFactSummary } from '../types/forecast';

interface Props {
  result: DailyForecastResult;
  summary?: PlanFactSummary;
}

function formatRub(n: number): string {
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
}

function mapeColor(mape: number): string {
  if (mape < 10) return 'text-emerald-300';
  if (mape < 20) return 'text-accent-500';
  if (mape < 30) return 'text-amber-300';
  return 'text-fact-red';
}

function accuracyColor(acc: number): string {
  if (acc >= 90) return 'text-emerald-300';
  if (acc >= 80) return 'text-accent-500';
  if (acc >= 70) return 'text-amber-300';
  return 'text-fact-red';
}

function revDevPct(predicted: number, actual: number): number {
  if (predicted === 0) return 0;
  return ((actual - predicted) / predicted) * 100;
}

function Cell({
  label,
  children,
  wide = false,
}: {
  label: string;
  children: React.ReactNode;
  wide?: boolean;
}) {
  return (
    <div
      className={`rounded-2xl bg-black/25 px-5 py-4 ${wide ? 'md:col-span-2' : ''}`}
    >
      <div className="eyebrow-light mb-2">{label}</div>
      <div>{children}</div>
    </div>
  );
}

export default function ForecastMeta({ result, summary }: Props) {
  const hasSummary = summary && summary.dish_count > 0;
  const hasRevenue = hasSummary && summary.total_actual_revenue > 0;
  const revDev = hasSummary
    ? revDevPct(summary.total_predicted_revenue, summary.total_actual_revenue)
    : 0;

  return (
    <div
      className="grid grid-cols-1 gap-3 md:grid-cols-3"
      data-testid="forecast-meta"
    >
      <Cell label={result.week_start ? 'Неделя' : 'Дата'}>
        <p className="text-lg font-semibold tabular-nums text-cream-100">
          {result.week_start
            ? `${result.week_start.slice(5).replace('-', '.')} — ${(result.week_end ?? '').slice(5).replace('-', '.')}`
            : result.date.split('-').reverse().join('.')}
        </p>
      </Cell>

      <Cell label="Погода">
        <p className="text-sm leading-snug text-cream-100">
          {result.weather ?? 'Нет данных'}
        </p>
      </Cell>

      <Cell label="Праздник">
        <p
          className={`text-lg font-semibold ${
            result.is_holiday ? 'text-amber-300' : 'text-ink-400'
          }`}
        >
          {result.is_holiday ? 'ДА' : 'НЕТ'}
        </p>
      </Cell>

      {hasSummary && (
        <>
          <Cell label="Кол-во: план / факт">
            <p className="text-lg font-semibold tabular-nums text-cream-100">
              {summary.total_predicted}
              <span className="px-1 text-ink-500">/</span>
              {summary.total_actual}
            </p>
          </Cell>

          <Cell label="MAPE / Точность">
            <div className="flex items-baseline gap-2">
              <span
                className={`text-lg font-semibold tabular-nums ${mapeColor(summary.mape)}`}
              >
                {summary.mape}%
              </span>
              <span className="text-ink-500">/</span>
              <span
                className={`text-lg font-semibold tabular-nums ${accuracyColor(summary.accuracy)}`}
              >
                {summary.accuracy}%
              </span>
            </div>
          </Cell>

          {hasRevenue && (
            <Cell label="Выручка: план / факт" wide>
              <p className="text-base font-semibold tabular-nums text-cream-100">
                {formatRub(summary.total_predicted_revenue)}
                <span className="px-1 text-ink-500">/</span>
                {formatRub(summary.total_actual_revenue)} ₽
              </p>
              <p
                className={`mt-1 text-xs font-medium tabular-nums ${
                  Math.abs(revDev) <= 10
                    ? 'text-emerald-300'
                    : Math.abs(revDev) <= 25
                      ? 'text-amber-300'
                      : 'text-fact-red'
                }`}
              >
                {revDev > 0 ? '+' : ''}
                {revDev.toFixed(1)}% отклонение
              </p>
            </Cell>
          )}
        </>
      )}
    </div>
  );
}
