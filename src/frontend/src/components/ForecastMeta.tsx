import type { DailyForecastResult, PlanFactSummary } from '../types/forecast';

interface Props {
  result: DailyForecastResult;
  summary?: PlanFactSummary;
}

function formatRub(n: number): string {
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
}

function formatDdMm(iso: string): string {
  // "2026-03-30" → "30.03"
  const [, mm, dd] = iso.split('-');
  return `${dd}.${mm}`;
}

function formatDdMmYyyy(iso: string): string {
  // "2026-04-15" → "15.04.2026"
  const [yyyy, mm, dd] = iso.split('-');
  return `${dd}.${mm}.${yyyy}`;
}

function revDevPct(predicted: number, actual: number): number {
  if (predicted === 0) return 0;
  return ((actual - predicted) / predicted) * 100;
}

function revDevClass(dev: number): string {
  const abs = Math.abs(dev);
  if (abs <= 10) return 'text-emerald-300';
  if (abs <= 25) return 'text-amber-300';
  return 'text-fact-red';
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

function Cell({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl bg-black/25 px-5 py-4">
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
  const showForecastRevenue = !hasSummary && result.total_revenue > 0;

  const periodLabel = result.week_start
    ? `${formatDdMm(result.week_start)} — ${formatDdMm(result.week_end ?? '')}`
    : formatDdMmYyyy(result.date);

  return (
    <div
      className="grid grid-cols-1 gap-3 md:grid-cols-3"
      data-testid="forecast-meta"
    >
      <Cell label={result.week_start ? 'Неделя' : 'Дата'}>
        <p className="text-[18px] font-semibold leading-snug tabular-nums text-cream-100">
          {periodLabel}
        </p>
      </Cell>

      <Cell label="Погода">
        <p className="text-[16px] leading-snug text-cream-100">
          {result.weather ?? 'Нет данных'}
        </p>
      </Cell>

      <Cell label="Праздник">
        <p
          className={`text-[18px] font-semibold leading-snug ${
            result.is_holiday ? 'text-amber-300' : 'text-ink-400'
          }`}
        >
          {result.is_holiday ? 'ДА' : 'НЕТ'}
        </p>
      </Cell>

      {showForecastRevenue && (
        <Cell label="Выручка (прогноз)">
          <p
            className="text-[18px] font-semibold leading-snug tabular-nums text-cream-100"
            data-testid="forecast-meta-revenue"
          >
            {formatRub(Math.round(result.total_revenue))} ₽
          </p>
        </Cell>
      )}

      {hasSummary && hasRevenue && (
        <Cell label="Выручка: план / факт">
          <p className="flex flex-wrap items-baseline gap-x-2 text-[18px] font-semibold leading-snug tabular-nums text-cream-100">
            <span>
              {formatRub(summary.total_predicted_revenue)}
              <span className="px-1 text-ink-500">/</span>
              {formatRub(summary.total_actual_revenue)} ₽
            </span>
            <span
              className={`text-[13px] font-medium tabular-nums ${revDevClass(revDev)}`}
            >
              {revDev > 0 ? '+' : ''}
              {revDev.toFixed(1)}% отклонение
            </span>
          </p>
        </Cell>
      )}

      {hasSummary && (
        <Cell label="Кол-во: план / факт">
          <p className="text-[18px] font-semibold leading-snug tabular-nums text-cream-100">
            {summary.total_predicted}
            <span className="px-1 text-ink-500">/</span>
            {summary.total_actual}
          </p>
        </Cell>
      )}

      {hasSummary && (
        <Cell label="MAPE / Точность">
          <div className="flex items-baseline gap-2">
            <span
              className={`text-[18px] font-semibold leading-snug tabular-nums ${mapeColor(summary.mape)}`}
            >
              {summary.mape}%
            </span>
            <span className="text-ink-500">/</span>
            <span
              className={`text-[18px] font-semibold leading-snug tabular-nums ${accuracyColor(summary.accuracy)}`}
            >
              {summary.accuracy}%
            </span>
          </div>
        </Cell>
      )}
    </div>
  );
}
