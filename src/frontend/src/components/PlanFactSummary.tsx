import type { PlanFactSummary as Summary } from '../types/forecast';

interface Props {
  summary: Summary;
}

function ratingColor(rating: string): string {
  if (rating === 'Отлично') return 'text-green-400 bg-green-500/10 border-green-500/20';
  if (rating === 'Хорошо') return 'text-blue-400 bg-blue-500/10 border-blue-500/20';
  if (rating === 'Удовлетворительно') return 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20';
  return 'text-red-400 bg-red-500/10 border-red-500/20';
}

function mapeColor(mape: number): string {
  if (mape < 10) return 'text-green-400';
  if (mape < 20) return 'text-blue-400';
  if (mape < 30) return 'text-yellow-400';
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
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="glass-card p-4">
          <span className="text-xs font-medium text-slate-400 uppercase">MAPE</span>
          <p className={`mt-1 text-lg font-semibold ${mapeColor(summary.mape)}`}>
            {summary.mape}%
          </p>
        </div>

        <div className="glass-card p-4">
          <span className="text-xs font-medium text-slate-400 uppercase">Точность</span>
          <p className="mt-1 text-lg font-semibold text-white">
            {summary.accuracy}%
          </p>
        </div>

        <div className="glass-card p-4">
          <span className="text-xs font-medium text-slate-400 uppercase">Кол-во: план / факт</span>
          <p className="mt-1 text-lg font-semibold text-white">
            {summary.total_predicted} / {summary.total_actual}
          </p>
        </div>

        <div className={`rounded-xl border p-4 ${ratingColor(summary.quality_rating)}`}>
          <span className="text-xs font-medium uppercase opacity-70">Оценка</span>
          <p className="mt-1 text-lg font-semibold">
            {summary.quality_rating}
          </p>
        </div>
      </div>

      {summary.total_actual_revenue > 0 && (
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="glass-card p-4">
            <span className="text-xs font-medium text-slate-400 uppercase">Выручка план</span>
            <p className="mt-1 text-lg font-semibold text-white">
              {formatRub(summary.total_predicted_revenue)} ₽
            </p>
          </div>

          <div className="glass-card p-4">
            <span className="text-xs font-medium text-slate-400 uppercase">Выручка факт</span>
            <p className="mt-1 text-lg font-semibold text-white">
              {formatRub(summary.total_actual_revenue)} ₽
            </p>
          </div>

          <div className="glass-card p-4">
            <span className="text-xs font-medium text-slate-400 uppercase">Отклонение выручки</span>
            <p className={`mt-1 text-lg font-semibold ${revDeviationColor(summary.total_predicted_revenue, summary.total_actual_revenue)}`}>
              {revDev > 0 ? '+' : ''}{revDev.toFixed(1)}%
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
