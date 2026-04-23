import { useEffect, useRef, useState } from 'react';
import type { ForecastMode } from '../types/forecast';
import { mondayOf, todayMskDate, toIso } from '../utils/date';
import DatePickerPopover from './DatePickerPopover';

interface Props {
  onSubmit: (date: string, force: boolean) => void;
  mode: ForecastMode;
  onModeChange: (mode: ForecastMode) => void;
  eyebrow?: string;
  title?: string;
  description?: string;
}

export default function ForecastForm({
  onSubmit,
  mode,
  onModeChange,
  eyebrow = 'ПРОГНОЗ СПРОСА ДЛЯ РЕСТОРАНА',
  title = 'Сначала запуск, потом прогноз',
  description = 'Выберите режим, укажите дату и запустите расчёт. После этого система раскроет таблицу по блюдам.',
}: Props) {
  const today = todayMskDate();

  // Daily: selected day. Weekly: the Monday of the selected week.
  const [selectedDay, setSelectedDay] = useState<Date>(today);
  const [selectedWeekMonday, setSelectedWeekMonday] = useState<Date>(() =>
    mondayOf(today),
  );
  const [force, setForce] = useState(false);

  // When the mode prop flips, project the current selection between modes so
  // the two stores stay in sync instead of reverting to stale "today" values.
  const prevModeRef = useRef<ForecastMode>(mode);
  useEffect(() => {
    const prev = prevModeRef.current;
    if (prev === mode) return;
    if (prev === 'daily' && mode === 'weekly') {
      setSelectedWeekMonday(mondayOf(selectedDay));
    } else if (prev === 'weekly' && mode === 'daily') {
      setSelectedDay(selectedWeekMonday);
    }
    prevModeRef.current = mode;
    // Only react to mode flips; selection values read via closure.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (mode === 'weekly') {
      onSubmit(toIso(selectedWeekMonday), force);
    } else {
      onSubmit(toIso(selectedDay), force);
    }
  };

  return (
    <form
      id="forecast-form"
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

      <DatePickerPopover
        mode={mode}
        selectedDay={selectedDay}
        selectedWeekMonday={selectedWeekMonday}
        onSelectDay={setSelectedDay}
        onSelectWeekMonday={setSelectedWeekMonday}
        label={{ daily: 'Дата прогноза', weekly: 'Неделя прогноза' }}
        testIdPrefix="forecast-date"
      />

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <InfoCell label="Результат" value="Таблица по блюдам" />
        <InfoCell label="Формат" value="Количество / выручка" />
        <InfoCell label="Выход" value="Прогноз с факторами" />
      </div>

      <label
        className={
          'flex cursor-pointer items-center justify-between gap-4 rounded-2xl bg-black/25 px-5 py-4 ' +
          'transition-colors hover:bg-black/35 ' +
          'has-[:focus-visible]:ring-1 has-[:focus-visible]:ring-accent-500/50'
        }
      >
        <span className="flex flex-col gap-0.5">
          <span className="text-sm font-medium text-cream-100">
            Пересчитать заново
          </span>
          <span className="text-xs leading-relaxed text-ink-400">
            Игнорировать кэш и запустить расчёт с нуля
          </span>
        </span>

        <input
          type="checkbox"
          checked={force}
          onChange={(e) => setForce(e.target.checked)}
          data-testid="forecast-force"
          className="sr-only"
        />
        <span
          aria-hidden
          className={
            'relative inline-block h-6 w-11 shrink-0 rounded-full transition-colors ' +
            (force
              ? 'bg-accent-500 shadow-[0_0_0_4px_rgba(72,147,255,0.12)]'
              : 'bg-white/[0.08]')
          }
        >
          <span
            className={
              'absolute top-0.5 h-5 w-5 rounded-full bg-cream-100 shadow transition-transform ' +
              (force ? 'left-0.5 translate-x-5' : 'left-0.5 translate-x-0')
            }
          />
        </span>
      </label>
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
