import { useState } from 'react';

interface Props {
  onSubmit: (date: string, force: boolean) => void;
  loading: boolean;
}

function todayMSK(): string {
  return new Date()
    .toLocaleDateString('sv-SE', { timeZone: 'Europe/Moscow' });
}

export default function ForecastForm({ onSubmit, loading }: Props) {
  const [date, setDate] = useState(todayMSK);
  const [force, setForce] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(date, force);
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-4">
      <div>
        <label className="mb-1 block text-sm font-medium text-slate-700">
          Дата прогноза
        </label>
        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
        />
      </div>
      <label className="flex items-center gap-2 text-sm text-slate-700">
        <input
          type="checkbox"
          checked={force}
          onChange={(e) => setForce(e.target.checked)}
          className="rounded border-slate-300"
        />
        Пересчитать (force)
      </label>
      <button
        type="submit"
        disabled={loading}
        className="rounded-md bg-blue-600 px-5 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading ? 'Расчёт...' : 'Запустить прогноз'}
      </button>
    </form>
  );
}
