import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { createPortal } from 'react-dom';
import {
  DayPicker,
  getDefaultClassNames,
  rangeIncludesDate,
  type DateRange,
  type Modifiers,
} from 'react-day-picker';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';
import { mondayOf, sundayOf } from '../utils/date';

function formatDailyTrigger(d: Date): string {
  return format(d, 'd MMM yyyy', { locale: ru });
}

function formatWeeklyTrigger(mon: Date): string {
  const sun = sundayOf(mon);
  const left = format(mon, 'd MMM', { locale: ru });
  const right = format(sun, 'd MMM yyyy', { locale: ru });
  return `${left} – ${right}`;
}

type DatePickerMode = 'daily' | 'weekly';

// ---------- DatePickerPopover (public component) ----------

interface Props {
  mode: DatePickerMode;
  selectedDay: Date;
  selectedWeekMonday: Date;
  onSelectDay: (d: Date) => void;
  onSelectWeekMonday: (mon: Date) => void;
  /** Label shown above the trigger. Uppercased copy of the active one is used
   *  as the small eyebrow inside the pill. */
  label: { daily: string; weekly: string };
  /** Optional stable testid prefix; defaults keep parity with the forecast
   *  screen selectors. */
  testIdPrefix?: string;
}

export default function DatePickerPopover({
  mode,
  selectedDay,
  selectedWeekMonday,
  onSelectDay,
  onSelectWeekMonday,
  label,
  testIdPrefix = 'forecast-date',
}: Props) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const popoverRef = useRef<HTMLDivElement | null>(null);

  // Close popover on outside mousedown + Escape.
  useEffect(() => {
    if (!open) return;
    const onMouseDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (
        popoverRef.current &&
        !popoverRef.current.contains(t) &&
        triggerRef.current &&
        !triggerRef.current.contains(t)
      ) {
        setOpen(false);
      }
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false);
        triggerRef.current?.focus();
      }
    };
    document.addEventListener('mousedown', onMouseDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onMouseDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  const activeLabel = mode === 'weekly' ? label.weekly : label.daily;
  const triggerEyebrow = activeLabel.toLocaleUpperCase('ru-RU');
  const triggerMain =
    mode === 'weekly'
      ? formatWeeklyTrigger(selectedWeekMonday)
      : formatDailyTrigger(selectedDay);

  // Range derived from selected week Monday.
  const selectedWeek: DateRange = useMemo(
    () => ({
      from: selectedWeekMonday,
      to: sundayOf(selectedWeekMonday),
    }),
    [selectedWeekMonday],
  );

  // Weekly hover range (whole row highlight).
  const [hoveredWeek, setHoveredWeek] = useState<DateRange | null>(null);

  // Reset hover state when popover closes or mode changes.
  useEffect(() => {
    if (!open) setHoveredWeek(null);
  }, [open]);
  useEffect(() => {
    setHoveredWeek(null);
  }, [mode]);

  // Controlled calendar month. Anchor on current selection when opening.
  const viewAnchor = useMemo(
    () => (mode === 'weekly' ? selectedWeekMonday : selectedDay),
    [mode, selectedWeekMonday, selectedDay],
  );
  const [month, setMonth] = useState<Date>(viewAnchor);

  useEffect(() => {
    if (open) setMonth(viewAnchor);
    // viewAnchor read via closure on open/mode flip only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, mode]);

  const handleDayMouseEnter = (day: Date) => {
    if (mode !== 'weekly') return;
    setHoveredWeek({ from: mondayOf(day), to: sundayOf(day) });
  };
  const handleDayMouseLeave = () => {
    if (mode !== 'weekly') return;
    setHoveredWeek(null);
  };

  const handleDayClick = (day: Date, modifiers: Modifiers) => {
    if (modifiers.disabled) return;
    if (mode === 'weekly') {
      onSelectWeekMonday(mondayOf(day));
      setOpen(false);
      triggerRef.current?.focus();
    } else {
      onSelectDay(day);
      setOpen(false);
      triggerRef.current?.focus();
    }
  };

  // Default DayPicker classes + our dark overrides. The grid stretches to fill
  // the popover (w-full + table-fixed → equal-width columns), but the actual
  // day buttons stay locked at 36×36 and centered inside each cell — so range
  // backgrounds form an unbroken pill across the row while the clickable
  // targets keep their circular shape regardless of popover width.
  const dp = getDefaultClassNames();
  const classNames = {
    root: `${dp.root ?? ''} text-cream-100 font-sans p-4`,
    months: `${dp.months ?? ''}`,
    month: `${dp.month ?? ''} p-0`,
    month_caption: `${dp.month_caption ?? ''} flex h-9 items-center justify-center pb-3`,
    caption_label: `${dp.caption_label ?? ''} text-[13px] font-semibold tracking-[0.02em] text-cream-100 capitalize`,
    nav: `${dp.nav ?? ''} flex items-center gap-1`,
    button_previous: `${dp.button_previous ?? ''} inline-flex h-7 w-7 items-center justify-center rounded-md text-ink-400 transition-colors hover:bg-white/[0.06] hover:text-cream-100`,
    button_next: `${dp.button_next ?? ''} inline-flex h-7 w-7 items-center justify-center rounded-md text-ink-400 transition-colors hover:bg-white/[0.06] hover:text-cream-100`,
    chevron: `${dp.chevron ?? ''} fill-current`,
    month_grid: `${dp.month_grid ?? ''} w-full table-fixed border-separate border-spacing-0`,
    weekdays: `${dp.weekdays ?? ''}`,
    weekday: `${dp.weekday ?? ''} h-8 text-center align-middle text-[10px] font-semibold uppercase tracking-[0.18em] text-ink-500`,
    week_number_header: `${dp.week_number_header ?? ''} h-8 text-center align-middle text-[10px] font-semibold uppercase tracking-[0.18em] text-ink-500`,
    week_number: `${dp.week_number ?? ''} h-9 text-center align-middle text-[10px] font-mono text-ink-500`,
    week: `${dp.week ?? ''}`,
    day: `${dp.day ?? ''} h-9 p-0 text-center align-middle text-[13px] text-cream-100 tabular-nums`,
    day_button: `${dp.day_button ?? ''} mx-auto inline-flex h-9 w-9 items-center justify-center rounded-full bg-transparent transition-colors hover:bg-white/[0.06] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent-500`,
    today: `${dp.today ?? ''} font-bold text-accent-500`,
    selected: `${dp.selected ?? ''} rdp-sirin-selected`,
    range_start: `${dp.range_start ?? ''} rdp-sirin-range-start`,
    range_end: `${dp.range_end ?? ''} rdp-sirin-range-end`,
    range_middle: `${dp.range_middle ?? ''} rdp-sirin-range-middle`,
    outside: `${dp.outside ?? ''} text-ink-600`,
    disabled: `${dp.disabled ?? ''} opacity-30`,
  };

  const modifiers =
    mode === 'weekly'
      ? {
          hovered_week: hoveredWeek
            ? (date: Date) => rangeIncludesDate(hoveredWeek, date, false)
            : () => false,
        }
      : undefined;
  const modifiersClassNames =
    mode === 'weekly' ? { hovered_week: 'rdp-sirin-hovered-week' } : undefined;

  const dayPickerSelectionProps =
    mode === 'weekly'
      ? {
          mode: 'range' as const,
          selected: selectedWeek,
          onSelect: () => {
            /* handled via onDayClick to select whole weeks atomically */
          },
        }
      : {
          mode: 'single' as const,
          selected: selectedDay,
          onSelect: (d: Date | undefined) => {
            if (d) onSelectDay(d);
          },
        };

  // ---------- Portal positioning ----------
  const POPOVER_WIDTH = 332;
  const POPOVER_GAP = 8;
  const POPOVER_HEIGHT_FALLBACK = 360;

  const [coords, setCoords] = useState<{
    top: number;
    left: number;
    width: number;
  }>({ top: 0, left: 0, width: POPOVER_WIDTH });

  const computeCoords = () => {
    const trigger = triggerRef.current;
    if (!trigger) return;
    const rect = trigger.getBoundingClientRect();
    const width = Math.max(rect.width, POPOVER_WIDTH);
    const popoverHeight =
      popoverRef.current?.offsetHeight ?? POPOVER_HEIGHT_FALLBACK;

    const spaceBelow = window.innerHeight - rect.bottom - POPOVER_GAP;
    const spaceAbove = rect.top - POPOVER_GAP;
    const placeAbove =
      popoverHeight > spaceBelow && spaceAbove > spaceBelow;

    const top = placeAbove
      ? Math.max(8, rect.top - popoverHeight - POPOVER_GAP)
      : rect.bottom + POPOVER_GAP;

    const maxLeft = window.innerWidth - width - 8;
    const left = Math.min(Math.max(8, rect.left), Math.max(8, maxLeft));

    setCoords({ top, left, width });
  };

  useLayoutEffect(() => {
    if (!open) return;
    computeCoords();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const id = requestAnimationFrame(() => computeCoords());
    return () => cancelAnimationFrame(id);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onChange = () => computeCoords();
    window.addEventListener('resize', onChange);
    window.addEventListener('scroll', onChange, true);
    return () => {
      window.removeEventListener('resize', onChange);
      window.removeEventListener('scroll', onChange, true);
    };
  }, [open]);

  const popoverContent = (
    <div
      ref={popoverRef}
      role="dialog"
      aria-label={mode === 'weekly' ? 'Выбор недели' : 'Выбор даты'}
      data-testid={`${testIdPrefix}-popover`}
      className="fixed z-50 overflow-hidden"
      style={{
        top: coords.top,
        left: coords.left,
        width: coords.width,
        maxWidth: '92vw',
        background: 'var(--bg-panel)',
        borderRadius: '20px',
        boxShadow: 'var(--shadow-panel)',
        border: '1px solid rgba(255,255,255,0.05)',
      }}
    >
      {/* Backwards-compat alias for e2e forecast selectors. */}
      <span
        data-testid="forecast-week-popover"
        aria-hidden
        className="hidden"
      />

      {/* DayPicker calendar */}
      <div className="rdp-sirin-wrapper">
        <DayPicker
          {...dayPickerSelectionProps}
          locale={ru}
          weekStartsOn={1}
          ISOWeek
          showWeekNumber
          showOutsideDays
          month={month}
          onMonthChange={setMonth}
          defaultMonth={viewAnchor}
          classNames={classNames}
          modifiers={modifiers}
          modifiersClassNames={modifiersClassNames}
          onDayClick={handleDayClick}
          onDayMouseEnter={
            mode === 'weekly' ? handleDayMouseEnter : undefined
          }
          onDayMouseLeave={
            mode === 'weekly' ? handleDayMouseLeave : undefined
          }
        />
      </div>

      <style>{SIRIN_DP_STYLES}</style>
    </div>
  );

  return (
    <div className="relative w-full">
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={
          mode === 'weekly'
            ? `Выбрать неделю, выбрано ${triggerMain}`
            : `Выбрать дату, выбрано ${triggerMain}`
        }
        data-testid={`${testIdPrefix}-trigger`}
        className={
          'group flex w-full items-center gap-3 rounded-full bg-black/25 px-5 py-3 text-left transition-all ' +
          'hover:bg-black/35 ' +
          (open
            ? 'ring-1 ring-accent-500/60 shadow-[0_0_0_4px_rgba(72,147,255,0.08)]'
            : 'ring-1 ring-white/[0.04]')
        }
        style={{ fontFamily: 'var(--font-sans)' }}
      >
        <span
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent-500/15 text-accent-500"
          aria-hidden
        >
          <CalendarIcon />
        </span>
        <span className="flex flex-1 flex-col gap-0.5 leading-tight">
          <span
            className="text-[11px] font-semibold uppercase tracking-[0.16em] text-ink-400"
            style={{ fontFamily: 'var(--font-display)' }}
          >
            {triggerEyebrow}
          </span>
          <span
            className="text-[16px] font-semibold tabular-nums text-cream-100"
            style={{ fontFamily: 'var(--font-display)' }}
          >
            {triggerMain}
          </span>
        </span>
        <span
          className={
            'ml-1 text-ink-400 transition-transform ' +
            (open ? 'rotate-180' : 'rotate-0')
          }
          aria-hidden
        >
          <ChevronIcon />
        </span>
      </button>

      {/* Backwards-compat hidden alias so existing e2e selectors still match. */}
      <span
        data-testid="forecast-week-trigger"
        aria-hidden
        className="hidden"
      />

      {open &&
        typeof document !== 'undefined' &&
        createPortal(popoverContent, document.body)}
    </div>
  );
}

// ---------- Icons ----------

function CalendarIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  );
}

function ChevronIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

// ---------- Scoped DayPicker theme ----------

const SIRIN_DP_STYLES = `
.rdp-sirin-wrapper {
  --rdp-selected-border: 0;
  --rdp-accent-color: #4893ff;
  --rdp-accent-background-color: transparent;
  --rdp-today-color: #4893ff;
}
.rdp-sirin-wrapper td.rdp-day,
.rdp-sirin-wrapper td.rdp-selected,
.rdp-sirin-wrapper td.rdp-range_start,
.rdp-sirin-wrapper td.rdp-range_middle,
.rdp-sirin-wrapper td.rdp-range_end {
  background: transparent;
  background-image: none;
}
.rdp-sirin-wrapper button.rdp-day_button {
  border: 0;
}
.rdp-sirin-wrapper td.rdp-sirin-selected:not(.rdp-sirin-range-start):not(.rdp-sirin-range-middle):not(.rdp-sirin-range-end) > button {
  background: var(--bg-accent);
  color: #ffffff;
  font-weight: 600;
  border-radius: 999px;
  box-shadow: 0 6px 18px -10px rgba(72, 147, 255, 0.85);
}
.rdp-sirin-wrapper td.rdp-sirin-range-start,
.rdp-sirin-wrapper td.rdp-sirin-range-middle,
.rdp-sirin-wrapper td.rdp-sirin-range-end {
  background: rgba(72, 147, 255, 0.14);
}
.rdp-sirin-wrapper td.rdp-sirin-range-start {
  border-top-left-radius: 999px;
  border-bottom-left-radius: 999px;
}
.rdp-sirin-wrapper td.rdp-sirin-range-end {
  border-top-right-radius: 999px;
  border-bottom-right-radius: 999px;
}
.rdp-sirin-wrapper .rdp-sirin-range-start > button,
.rdp-sirin-wrapper .rdp-sirin-range-middle > button,
.rdp-sirin-wrapper .rdp-sirin-range-end > button {
  background: transparent;
  color: #f6f2ea;
  border: 0;
  border-radius: 0;
  box-shadow: none;
  font-weight: 500;
}
.rdp-sirin-wrapper td.rdp-sirin-range-start,
.rdp-sirin-wrapper td.rdp-sirin-range-end {
  background: rgba(72, 147, 255, 0.24);
}
.rdp-sirin-wrapper .rdp-sirin-range-start > button,
.rdp-sirin-wrapper .rdp-sirin-range-end > button {
  color: #ffffff;
  font-weight: 600;
}
.rdp-sirin-wrapper td.rdp-sirin-hovered-week {
  background: rgba(72, 147, 255, 0.07);
}
.rdp-sirin-wrapper .rdp-sirin-hovered-week > button {
  background: transparent;
  color: #f6f2ea;
  border: 0;
  border-radius: 0;
  box-shadow: none;
}
.rdp-sirin-wrapper .rdp-week > td.rdp-sirin-hovered-week:first-of-type {
  border-top-left-radius: 999px;
  border-bottom-left-radius: 999px;
}
.rdp-sirin-wrapper .rdp-week > td.rdp-sirin-hovered-week:last-of-type {
  border-top-right-radius: 999px;
  border-bottom-right-radius: 999px;
}
.rdp-sirin-wrapper td.rdp-sirin-hovered-week.rdp-sirin-range-middle {
  background: rgba(72, 147, 255, 0.18);
}
.rdp-sirin-wrapper td.rdp-sirin-hovered-week.rdp-sirin-range-start,
.rdp-sirin-wrapper td.rdp-sirin-hovered-week.rdp-sirin-range-end {
  background: rgba(72, 147, 255, 0.30);
}
.rdp-sirin-wrapper .rdp-sirin-range-start.rdp-today > button,
.rdp-sirin-wrapper .rdp-sirin-range-middle.rdp-today > button,
.rdp-sirin-wrapper .rdp-sirin-range-end.rdp-today > button {
  color: #ffffff;
}
.rdp-sirin-wrapper .rdp-day_button:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px rgba(72, 147, 255, 0.35);
}
`;

