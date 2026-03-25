import type { AccuracyHistoryResponse } from '../types/forecast';

interface Props {
  summary: AccuracyHistoryResponse['summary'];
}

function accuracyColor(value: number): string {
  if (value >= 70) return 'text-green-700';
  if (value >= 60) return 'text-blue-700';
  if (value >= 50) return 'text-amber-700';
  return 'text-red-700';
}

function accuracyBg(value: number): string {
  if (value >= 70) return 'bg-green-50 border-green-200';
  if (value >= 60) return 'bg-blue-50 border-blue-200';
  if (value >= 50) return 'bg-amber-50 border-amber-200';
  return 'bg-red-50 border-red-200';
}

function accuracyBadge(value: number): { label: string; classes: string } {
  if (value >= 70) return { label: 'Хорошо', classes: 'bg-green-100 text-green-800' };
  if (value >= 60) return { label: 'Приемлемо', classes: 'bg-blue-100 text-blue-800' };
  if (value >= 50) return { label: 'Средне', classes: 'bg-amber-100 text-amber-800' };
  return { label: 'Низкая', classes: 'bg-red-100 text-red-800' };
}

export default function AccuracySummary({ summary }: Props) {
  const mlBadge = accuracyBadge(summary.ml_avg_accuracy);
  const llmBadge = accuracyBadge(summary.llm_avg_accuracy);

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {/* ML accuracy card */}
      <div className={`rounded-lg border p-4 shadow-sm ${accuracyBg(summary.ml_avg_accuracy)}`}>
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium uppercase text-slate-500">
            ML-прогноз
          </span>
          <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${mlBadge.classes}`}>
            {mlBadge.label}
          </span>
        </div>
        <p className={`mt-2 text-3xl font-bold ${accuracyColor(summary.ml_avg_accuracy)}`}>
          {summary.ml_avg_accuracy.toFixed(1)}%
        </p>
        <p className="mt-1 text-xs text-slate-500">Средняя точность</p>
      </div>

      {/* LLM accuracy card */}
      <div className={`rounded-lg border p-4 shadow-sm ${accuracyBg(summary.llm_avg_accuracy)}`}>
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium uppercase text-slate-500">
            ИИ-прогноз
          </span>
          <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${llmBadge.classes}`}>
            {llmBadge.label}
          </span>
        </div>
        <p className={`mt-2 text-3xl font-bold ${accuracyColor(summary.llm_avg_accuracy)}`}>
          {summary.llm_avg_accuracy.toFixed(1)}%
        </p>
        <p className="mt-1 text-xs text-slate-500">Средняя точность</p>
      </div>

      {/* Days count card */}
      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <span className="text-xs font-medium uppercase text-slate-500">
          Период анализа
        </span>
        <p className="mt-2 text-3xl font-bold text-slate-900">
          {summary.days_count}
        </p>
        <p className="mt-1 text-xs text-slate-500">Дней с данными</p>
      </div>
    </div>
  );
}
