import type { PlanFactSummary as Summary } from '../types/forecast';

interface Props {
  summary: Summary;
}

function ratingColor(rating: string): string {
  if (rating === 'Отлично') return 'text-green-700 bg-green-50 border-green-200';
  if (rating === 'Хорошо') return 'text-blue-700 bg-blue-50 border-blue-200';
  if (rating === 'Удовлетворительно') return 'text-yellow-700 bg-yellow-50 border-yellow-200';
  return 'text-red-700 bg-red-50 border-red-200';
}

function mapeColor(mape: number): string {
  if (mape < 10) return 'text-green-700';
  if (mape < 20) return 'text-blue-700';
  if (mape < 30) return 'text-yellow-700';
  return 'text-red-700';
}

export default function PlanFactSummaryCard({ summary }: Props) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <span className="text-xs font-medium text-slate-500 uppercase">MAPE</span>
        <p className={`mt-1 text-lg font-semibold ${mapeColor(summary.mape)}`}>
          {summary.mape}%
        </p>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <span className="text-xs font-medium text-slate-500 uppercase">Точность</span>
        <p className="mt-1 text-lg font-semibold text-slate-900">
          {summary.accuracy}%
        </p>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <span className="text-xs font-medium text-slate-500 uppercase">Прогноз / Факт</span>
        <p className="mt-1 text-lg font-semibold text-slate-900">
          {summary.total_predicted} / {summary.total_actual}
        </p>
      </div>

      <div className={`rounded-lg border p-4 shadow-sm ${ratingColor(summary.quality_rating)}`}>
        <span className="text-xs font-medium uppercase opacity-70">Оценка</span>
        <p className="mt-1 text-lg font-semibold">
          {summary.quality_rating}
        </p>
      </div>
    </div>
  );
}
