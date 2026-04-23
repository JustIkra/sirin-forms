import { endOfWeek, startOfWeek } from 'date-fns';

/** "Today" as a Date at local noon, built from MSK wall-clock date. */
export function todayMskDate(): Date {
  // 'sv-SE' gives YYYY-MM-DD; we parse at noon to dodge DST edges.
  const ymd = new Date().toLocaleDateString('sv-SE', {
    timeZone: 'Europe/Moscow',
  });
  return new Date(ymd + 'T12:00:00');
}

/** Format a Date as YYYY-MM-DD in local time. */
export function toIso(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

/** Start-of-week with Monday anchor. */
export function mondayOf(d: Date): Date {
  return startOfWeek(d, { weekStartsOn: 1 });
}

/** End-of-week with Monday anchor (Sunday). */
export function sundayOf(d: Date): Date {
  return endOfWeek(d, { weekStartsOn: 1 });
}
