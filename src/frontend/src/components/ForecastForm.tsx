import { useState } from 'react';

interface Props {
  onSubmit: (date: string, force: boolean, method: 'llm' | 'ml') => void;
  loading: boolean;
  method: 'llm' | 'ml';
  onMethodChange: (method: 'llm' | 'ml') => void;
}

function todayMSK(): string {
  return new Date()
    .toLocaleDateString('sv-SE', { timeZone: 'Europe/Moscow' });
}

export default function ForecastForm({ onSubmit, loading, method, onMethodChange }: Props) {
  const [date, setDate] = useState(todayMSK);
  const [force, setForce] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(date, force, method);
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-4">
      <div>
        <label className="mb-1 block text-sm font-medium text-slate-300">
          Дата прогноза
        </label>
        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-white focus:border-blue-400 focus:ring-1 focus:ring-blue-400/30 focus:outline-none"
        />
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium text-slate-300">
          Метод
        </label>
        <div className="inline-flex rounded-md border border-white/10">
          <button
            type="button"
            onClick={() => onMethodChange('llm')}
            className={`px-4 py-2 text-sm font-medium rounded-l-md transition-colors ${
              method === 'llm'
                ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/25'
                : 'bg-white/5 text-slate-400 hover:bg-white/[0.08]'
            }`}
          >
            ИИ-прогноз
          </button>
          <button
            type="button"
            onClick={() => onMethodChange('ml')}
            className={`px-4 py-2 text-sm font-medium rounded-r-md border-l border-white/10 transition-colors ${
              method === 'ml'
                ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/25'
                : 'bg-white/5 text-slate-400 hover:bg-white/[0.08]'
            }`}
          >
            ML-прогноз
          </button>
        </div>
      </div>

      <label className="flex items-center gap-2 text-sm text-slate-300">
        <input
          type="checkbox"
          checked={force}
          onChange={(e) => setForce(e.target.checked)}
          className="rounded border-white/10 bg-white/5 text-white"
        />
        Пересчитать (force)
      </label>
      <button
        type="submit"
        disabled={loading}
        className="rounded-md bg-gradient-to-r from-blue-600 to-blue-500 px-5 py-2 text-sm font-medium text-white shadow-lg shadow-blue-500/25 transition-colors hover:from-blue-500 hover:to-blue-400 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading ? 'Расчёт...' : 'Запустить прогноз'}
      </button>
    </form>
  );
}
