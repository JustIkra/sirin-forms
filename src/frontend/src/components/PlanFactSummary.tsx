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

export default function PlanFactSummaryCard({ summary }: Props) {
  return (
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
        <span className="text-xs font-medium text-slate-400 uppercase">Прогноз / Факт</span>
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
  );
}
