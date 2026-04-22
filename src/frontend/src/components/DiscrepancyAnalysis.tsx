import type { DiscrepancyAnalysisResponse } from '../types/forecast';

interface Props {
  data: DiscrepancyAnalysisResponse | null;
  loading: boolean;
  error: string | null;
  onRequestAnalysis: () => void;
}

function categoryColor(cat: string): string {
  switch (cat) {
    case 'Погода': return 'text-blue-300 bg-blue-500/15 border-blue-500/20';
    case 'Сезонность': return 'text-teal-300 bg-teal-500/15 border-teal-500/20';
    case 'Событие': return 'text-amber-300 bg-amber-500/15 border-amber-500/20';
    case 'Тренд': return 'text-purple-300 bg-purple-500/15 border-purple-500/20';
    case 'Систематическая ошибка': return 'text-fact-red bg-fact-red/15 border-fact-red/20';
    case 'Выброс': return 'text-orange-300 bg-orange-500/15 border-orange-500/20';
    case 'Недостаток данных': return 'text-ink-300 bg-ink-500/20 border-ink-500/30';
    default: return 'text-ink-300 bg-ink-500/20 border-ink-500/30';
  }
}

function priorityLabel(p: number): string {
  if (p <= 1) return 'Критично';
  if (p <= 2) return 'Высокий';
  if (p <= 3) return 'Средний';
  return 'Низкий';
}

function priorityColor(p: number): string {
  if (p <= 1) return 'text-fact-red bg-fact-red/15';
  if (p <= 2) return 'text-orange-300 bg-orange-500/15';
  if (p <= 3) return 'text-amber-300 bg-amber-500/15';
  return 'text-ink-400 bg-ink-500/15';
}

function deviationColor(pct: number): string {
  const abs = Math.abs(pct);
  if (abs <= 15) return 'text-emerald-300';
  if (abs <= 30) return 'text-amber-300';
  return 'text-fact-red';
}

const card = 'rounded-2xl bg-black/25 p-5';

export default function DiscrepancyAnalysis({ data, loading, error, onRequestAnalysis }: Props) {
  if (!data && !loading && !error) {
    return (
      <div className="flex justify-center pt-2">
        <button
          onClick={onRequestAnalysis}
          data-testid="discrepancy-trigger"
          className="flex items-center gap-2 rounded-full bg-black/25 px-5 py-3 text-sm font-medium text-cream-100 transition-all hover:bg-black/40"
        >
          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
          Анализ отклонений (ИИ)
        </button>
      </div>
    );
  }

  if (loading) {
    return (
      <div className={card}>
        <div className="flex items-center gap-3">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-white/10 border-t-accent-500" />
          <span className="text-sm text-ink-400">ИИ анализирует расхождения...</span>
        </div>
        <div className="mt-4 space-y-3">
          <div className="h-4 w-3/4 animate-pulse rounded bg-white/10" />
          <div className="h-4 w-full animate-pulse rounded bg-white/10" />
          <div className="h-4 w-5/6 animate-pulse rounded bg-white/10" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={card}>
        <p className="text-sm text-fact-red">{error}</p>
        <button
          onClick={onRequestAnalysis}
          className="mt-3 rounded-full bg-black/40 px-3 py-1.5 text-xs text-cream-100 hover:bg-black/60"
        >
          Повторить
        </button>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-4" data-testid="discrepancy-result">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-cream-100">Анализ расхождений (ИИ)</h3>
        <button
          onClick={onRequestAnalysis}
          className="rounded-full bg-black/25 px-3 py-1.5 text-xs text-ink-400 hover:bg-black/40 hover:text-cream-100"
        >
          Обновить
        </button>
      </div>

      <p className="text-sm italic text-ink-400">{data.accuracy_context}</p>

      <div className={card}>
        <h4 className="eyebrow-light mb-3">Общий анализ</h4>
        <div className="space-y-2 text-sm leading-relaxed text-cream-100">
          {data.overall_analysis.split('\n').filter(Boolean).map((p, i) => (
            <p key={i}>{p}</p>
          ))}
        </div>
      </div>

      <div className={card}>
        <h4 className="eyebrow-light mb-3">Ключевые факторы</h4>
        <div className="flex flex-wrap gap-2">
          {data.top_factors.map((f, i) => (
            <span
              key={i}
              className="rounded-full bg-white/5 px-3 py-1 text-sm text-cream-100"
            >
              {f}
            </span>
          ))}
        </div>
      </div>

      {data.dish_insights.length > 0 && (
        <div className="overflow-hidden rounded-2xl bg-black/20">
          <div className="px-5 pt-4 pb-2">
            <h4 className="eyebrow-light">Анализ по блюдам</h4>
          </div>
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/5">
                <th className="px-5 py-3 text-left text-[10px] font-semibold tracking-[0.18em] text-ink-400 uppercase">Блюдо</th>
                <th className="px-5 py-3 text-right text-[10px] font-semibold tracking-[0.18em] text-ink-400 uppercase">Откл.</th>
                <th className="px-5 py-3 text-left text-[10px] font-semibold tracking-[0.18em] text-ink-400 uppercase">Категория</th>
                <th className="px-5 py-3 text-left text-[10px] font-semibold tracking-[0.18em] text-ink-400 uppercase">Причина</th>
              </tr>
            </thead>
            <tbody>
              {data.dish_insights.map((d) => (
                <tr key={d.dish_name} className="border-b border-white/[0.04] last:border-0 hover:bg-white/[0.03]">
                  <td className="px-5 py-3 text-sm font-medium text-cream-100">{d.dish_name}</td>
                  <td className={`px-5 py-3 text-right text-sm font-medium tabular-nums ${deviationColor(d.deviation_pct)}`}>
                    {d.deviation_pct > 0 ? '+' : ''}{d.deviation_pct.toFixed(1)}%
                  </td>
                  <td className="px-5 py-3">
                    <span className={`inline-block rounded-full border px-2 py-0.5 text-xs font-medium ${categoryColor(d.category)}`}>
                      {d.category}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-sm text-ink-300">{d.explanation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data.recommendations.length > 0 && (
        <div className={card}>
          <h4 className="eyebrow-light mb-3">Рекомендации по улучшению</h4>
          <div className="space-y-3">
            {data.recommendations
              .sort((a, b) => a.priority - b.priority)
              .map((r, i) => (
                <div key={i} className="flex gap-3 rounded-xl bg-white/[0.04] p-3">
                  <span className={`mt-0.5 shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${priorityColor(r.priority)}`}>
                    {priorityLabel(r.priority)}
                  </span>
                  <div>
                    <p className="text-sm font-medium text-cream-100">{r.title}</p>
                    <p className="mt-0.5 text-sm text-ink-400">{r.description}</p>
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
