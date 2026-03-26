import type { AccuracyHistoryResponse } from '../types/forecast';

interface Props {
  summary: AccuracyHistoryResponse['summary'];
}

function accuracyColor(value: number): string {
  if (value >= 70) return 'text-green-400';
  if (value >= 60) return 'text-blue-400';
  if (value >= 50) return 'text-amber-400';
  return 'text-red-400';
}

function accuracyBg(value: number): string {
  if (value >= 70) return 'bg-green-500/10 border-green-500/20';
  if (value >= 60) return 'bg-blue-500/10 border-blue-500/20';
  if (value >= 50) return 'bg-amber-500/10 border-amber-500/20';
  return 'bg-red-500/10 border-red-500/20';
}

function accuracyBadge(value: number): { label: string; classes: string } {
  if (value >= 70) return { label: 'Хорошо', classes: 'bg-green-500/15 text-green-400' };
  if (value >= 60) return { label: 'Приемлемо', classes: 'bg-blue-500/15 text-blue-400' };
  if (value >= 50) return { label: 'Средне', classes: 'bg-amber-500/15 text-amber-400' };
  return { label: 'Низкая', classes: 'bg-red-500/15 text-red-400' };
}

export default function AccuracySummary({ summary }: Props) {
  const mlBadge = accuracyBadge(summary.ml_avg_accuracy);
  const llmBadge = accuracyBadge(summary.llm_avg_accuracy);

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {/* ML accuracy card */}
      <div className={`rounded-xl border p-4 ${accuracyBg(summary.ml_avg_accuracy)}`}>
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium uppercase text-slate-400">
            ML-прогноз
          </span>
          <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${mlBadge.classes}`}>
            {mlBadge.label}
          </span>
        </div>
        <p className={`mt-2 text-3xl font-bold ${accuracyColor(summary.ml_avg_accuracy)}`}>
          {summary.ml_avg_accuracy.toFixed(1)}%
        </p>
        <p className="mt-1 text-xs text-slate-400">Средняя точность</p>
      </div>

      {/* LLM accuracy card */}
      <div className={`rounded-xl border p-4 ${accuracyBg(summary.llm_avg_accuracy)}`}>
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium uppercase text-slate-400">
            ИИ-прогноз
          </span>
          <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${llmBadge.classes}`}>
            {llmBadge.label}
          </span>
        </div>
        <p className={`mt-2 text-3xl font-bold ${accuracyColor(summary.llm_avg_accuracy)}`}>
          {summary.llm_avg_accuracy.toFixed(1)}%
        </p>
        <p className="mt-1 text-xs text-slate-400">Средняя точность</p>
      </div>

      {/* Days count card */}
      <div className="glass-card p-4">
        <span className="text-xs font-medium uppercase text-slate-400">
          Период анализа
        </span>
        <p className="mt-2 text-3xl font-bold text-white">
          {summary.days_count}
        </p>
        <p className="mt-1 text-xs text-slate-400">Дней с данными</p>
      </div>
    </div>
  );
}
