import { useState, useMemo } from 'react';

interface Props {
  onSubmit: (date: string, force: boolean) => void;
  loading: boolean;
}

function todayMSK(): string {
  return new Date()
    .toLocaleDateString('sv-SE', { timeZone: 'Europe/Moscow' });
}

function getWeekRange(dateStr: string): { start: string; end: string; label: string } {
  const d = new Date(dateStr + 'T12:00:00');
  const day = d.getDay();
  const diffToMon = day === 0 ? -6 : 1 - day;
  const monday = new Date(d);
  monday.setDate(d.getDate() + diffToMon);
  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);

  const fmt = (dt: Date) => dt.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' });
  const iso = (dt: Date) => dt.toISOString().slice(0, 10);

  return {
    start: iso(monday),
    end: iso(sunday),
    label: `${fmt(monday)} — ${fmt(sunday)}`,
  };
}

export default function ForecastForm({ onSubmit, loading }: Props) {
  const [date, setDate] = useState(todayMSK);
  const [force, setForce] = useState(false);

  const week = useMemo(() => getWeekRange(date), [date]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(date, force);
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-4">
      <div>
        <label className="mb-1 block text-sm font-medium text-slate-300">
          Неделя прогноза
        </label>
        <div className="flex items-center gap-3">
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-white focus:border-blue-400 focus:ring-1 focus:ring-blue-400/30 focus:outline-none"
          />
          <span className="text-xs text-slate-400 tabular-nums">
            {week.label}
          </span>
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
