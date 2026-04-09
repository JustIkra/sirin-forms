import type { PlanFactSummary as Summary } from '../types/forecast';

interface Props {
  summary: Summary;
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

function formatRub(n: number): string {
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 0 });
}

function revDeviationColor(predicted: number, actual: number): string {
  if (predicted === 0) return 'text-slate-400';
  const pct = Math.abs((actual - predicted) / predicted) * 100;
  if (pct <= 10) return 'text-green-400';
  if (pct <= 25) return 'text-yellow-400';
  return 'text-red-400';
}

export default function PlanFactSummaryCard({ summary }: Props) {
  const revDev = summary.total_predicted_revenue > 0
    ? ((summary.total_actual_revenue - summary.total_predicted_revenue) / summary.total_predicted_revenue * 100)
    : 0;

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {/* MAPE + Точность */}
      <div className="glass-card px-6 py-5">
        <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">MAPE / Точность</span>
        <div className="mt-3 flex items-end gap-4">
          <p className={`text-3xl font-bold tabular-nums leading-none ${mapeColor(summary.mape)}`}>
            {summary.mape}%
          </p>
          <span className="text-slate-600 text-lg">/</span>
          <p className={`text-3xl font-bold tabular-nums leading-none ${accuracyColor(summary.accuracy)}`}>
            {summary.accuracy}%
          </p>
        </div>
      </div>

      {/* Кол-во: план / факт */}
      <div className="glass-card px-6 py-5">
        <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">Кол-во: план / факт</span>
        <p className="mt-3 text-3xl font-bold text-white tabular-nums leading-none">
          {summary.total_predicted} <span className="text-slate-600 font-normal">/</span> {summary.total_actual}
        </p>
      </div>

      {/* Выручка */}
      {summary.total_actual_revenue > 0 && (
        <div className="glass-card px-6 py-5">
          <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">Выручка: план / факт</span>
          <p className="mt-3 text-2xl font-bold text-white tabular-nums leading-none">
            {formatRub(summary.total_predicted_revenue)} <span className="text-slate-600 font-normal">/</span> {formatRub(summary.total_actual_revenue)} &#8381;
          </p>
          <p className={`mt-2 text-sm font-semibold tabular-nums ${revDeviationColor(summary.total_predicted_revenue, summary.total_actual_revenue)}`}>
            {revDev > 0 ? '+' : ''}{revDev.toFixed(1)}% отклонение
          </p>
        </div>
      )}
    </div>
  );
}
