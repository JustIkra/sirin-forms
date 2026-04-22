import { useState, useMemo } from 'react';
import type { ForecastMode } from '../types/forecast';

interface Props {
  onSubmit: (date: string, force: boolean) => void;
  loading: boolean;
  mode: ForecastMode;
  onModeChange: (mode: ForecastMode) => void;
  eyebrow?: string;
  title?: string;
  description?: string;
  submitLabel?: string;
}

function todayMSK(): string {
  return new Date().toLocaleDateString('sv-SE', { timeZone: 'Europe/Moscow' });
}

function getWeekRange(dateStr: string): { label: string } {
  const d = new Date(dateStr + 'T12:00:00');
  const day = d.getDay();
  const diffToMon = day === 0 ? -6 : 1 - day;
  const monday = new Date(d);
  monday.setDate(d.getDate() + diffToMon);
  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);

  const fmt = (dt: Date) =>
    dt.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' });

  return { label: `${fmt(monday)} — ${fmt(sunday)}` };
}

function formatDateRu(d: string): string {
  const [y, m, day] = d.split('-');
  return `${day}.${m}.${y}`;
}

export default function ForecastForm({
  onSubmit,
  loading,
  mode,
  onModeChange,
  eyebrow = 'ПРОГНОЗ СПРОСА ДЛЯ РЕСТОРАНА',
  title = 'Сначала запуск, потом прогноз',
  description = 'Выберите режим, укажите дату и запустите расчёт. После этого система раскроет таблицу по блюдам.',
  submitLabel,
}: Props) {
  const [date, setDate] = useState(todayMSK);
  const [force, setForce] = useState(false);

  const week = useMemo(() => getWeekRange(date), [date]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(date, force);
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-6"
      data-testid="forecast-form"
    >
      <header>
        <div className="eyebrow-light mb-3">{eyebrow}</div>
        <h3 className="text-2xl font-semibold leading-tight text-cream-100">
          {title}
        </h3>
        <p className="mt-2 max-w-md text-sm leading-relaxed text-ink-400">
          {description}
        </p>
      </header>

      <div>
        <div className="eyebrow-light mb-2">Режим прогноза</div>
        <div
          className="inline-flex gap-1 rounded-full bg-black/25 p-1"
          data-testid="mode-toggle"
        >
          {(
            [
              ['daily', 'Дневной'],
              ['weekly', 'Недельный'],
            ] as const
          ).map(([m, label]) => (
            <button
              key={m}
              type="button"
              onClick={() => onModeChange(m)}
              data-testid={`mode-${m}`}
              className={
                mode === m
                  ? 'chip chip-accent'
                  : 'chip text-ink-400 hover:text-cream-100'
              }
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div>
        <div className="eyebrow-light mb-2">
          {mode === 'daily' ? 'Дата прогноза' : 'Неделя прогноза'}
        </div>
        <div className="relative inline-flex items-center gap-4 rounded-2xl bg-black/25 px-4 py-3">
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            data-testid="forecast-date"
            className="bg-transparent text-base tabular-nums text-cream-100 outline-none [color-scheme:dark]"
          />
          <span className="hidden text-sm tabular-nums text-ink-400 md:inline" aria-hidden>
            {formatDateRu(date)}
          </span>
          {mode === 'weekly' && (
            <span className="text-xs tabular-nums text-ink-400">
              {week.label}
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <InfoCell label="Результат" value="Таблица по блюдам" />
        <InfoCell label="Формат" value="Количество / выручка" />
        <InfoCell label="Выход" value="Прогноз с факторами" />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-4 pt-2">
        <label className="flex cursor-pointer items-center gap-2 text-sm text-ink-400">
          <input
            type="checkbox"
            checked={force}
            onChange={(e) => setForce(e.target.checked)}
            data-testid="forecast-force"
            className="h-4 w-4 rounded border-ink-500 bg-black/30 accent-accent-500"
          />
          Пересчитать (force)
        </label>

        <button
          type="submit"
          disabled={loading}
          data-testid="forecast-submit"
          className="btn-accent"
        >
          {loading ? 'Расчёт...' : submitLabel ?? 'Запустить прогноз'}
        </button>
      </div>
    </form>
  );
}

function InfoCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-black/25 px-4 py-3">
      <div className="eyebrow-light mb-1">{label}</div>
      <div className="text-sm text-cream-100">{value}</div>
    </div>
  );
}
