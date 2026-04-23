import { useState, useMemo } from 'react';
import type { InventoryResponse, InventoryScope } from '../types/forecast';
import { ForecastError } from '../api/forecast';
import { fetchInventory } from '../api/inventory';
import InventoryTable from './InventoryTable';
import Spinner from './Spinner';
import ErrorMessage from './ErrorMessage';
import Hero from './Hero';
import DarkPanel from './DarkPanel';
import { mondayOf, todayMskDate, toIso } from '../utils/date';
import DatePickerPopover from './DatePickerPopover';

type Tab = 'all' | 'to_buy';

function formatWeekRange(start: string, end: string): string {
  const fmt = (s: string) => {
    const d = new Date(s + 'T12:00:00');
    return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' });
  };
  return `${fmt(start)} — ${fmt(end)}`;
}

function formatDateLongRu(d: string): string {
  const date = new Date(d + 'T12:00:00');
  return date.toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
}

export default function InventoryPage() {
  const today = todayMskDate();

  const [selectedDay, setSelectedDay] = useState<Date>(today);
  const [selectedWeekMonday, setSelectedWeekMonday] = useState<Date>(() =>
    mondayOf(today),
  );
  const [scope, setScope] = useState<InventoryScope>('week');
  const [data, setData] = useState<InventoryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<{ message: string; status?: number } | null>(null);
  const [tab, setTab] = useState<Tab>('all');

  const handleScopeChange = (next: InventoryScope) => {
    if (next === scope) return;
    setScope(next);
    setData(null);
    setError(null);
  };

  const handleLoad = async () => {
    setLoading(true);
    setError(null);
    try {
      const date =
        scope === 'day' ? toIso(selectedDay) : toIso(selectedWeekMonday);
      const result = await fetchInventory(date, scope);
      setData(result);
    } catch (err) {
      if (err instanceof ForecastError) {
        setError({ message: err.message, status: err.status });
      } else {
        setError({ message: 'Не удалось подключиться к серверу' });
      }
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  const filteredItems = useMemo(() => {
    if (!data) return [];
    if (tab === 'to_buy') return data.items.filter((i) => i.to_buy > 0);
    return data.items;
  }, [data, tab]);

  const toBuyCount = useMemo(
    () => data?.items.filter((i) => i.to_buy > 0).length ?? 0,
    [data],
  );

  return (
    <>
      <div className="grid grid-cols-1 gap-10 pt-4 lg:grid-cols-2 lg:gap-16">
        <Hero
          eyebrow="ОСТАТКИ И ЗАКУПКА ДЛЯ РЕСТОРАНА"
          title={
            <>
              Остатки под
              <br />
              контролем,
              <br />
              закупка вовремя
            </>
          }
          description="Следите за складом по ключевым позициям и быстро понимайте, что заканчивается и что нужно заказать."
          secondary={
            <div>
              <button
                type="submit"
                form="inventory-form"
                disabled={loading}
                data-testid="inventory-load"
                className="btn-accent"
              >
                {loading ? 'Загрузка...' : 'Открыть остатки'}
              </button>
            </div>
          }
        />

        <DarkPanel eyebrow="ЭКРАН ОСТАТКОВ" windowChrome>
          <form
            id="inventory-form"
            onSubmit={(e) => {
              e.preventDefault();
              handleLoad();
            }}
            className="flex flex-col gap-6"
            data-testid="inventory-form"
          >
            <header>
              <div className="eyebrow-light mb-3">ОСТАТКИ И ЗАКУПКА ДЛЯ РЕСТОРАНА</div>
              <h3 className="text-2xl font-semibold leading-tight text-cream-100">
                Сначала остатки, потом закупка
              </h3>
              <p className="mt-2 max-w-md text-sm leading-relaxed text-ink-400">
                Выберите режим, укажите дату и запустите расчёт. После этого
                система покажет остатки и позиции для заказа.
              </p>
            </header>

            <div>
              <div className="eyebrow-light mb-2">Режим закупки</div>
              <div
                className="inline-flex gap-1 rounded-full bg-black/25 p-1"
                data-testid="inventory-scope-toggle"
              >
                {(
                  [
                    ['day', 'Дневной'],
                    ['week', 'Недельный'],
                  ] as const
                ).map(([s, label]) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => handleScopeChange(s)}
                    data-testid={`inventory-scope-${s}`}
                    className={
                      scope === s
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
              mode={scope === 'day' ? 'daily' : 'weekly'}
              selectedDay={selectedDay}
              selectedWeekMonday={selectedWeekMonday}
              onSelectDay={setSelectedDay}
              onSelectWeekMonday={setSelectedWeekMonday}
              label={{ daily: 'Дата закупки', weekly: 'Неделя закупки' }}
              testIdPrefix="inventory-date"
            />

            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <div className="rounded-2xl bg-black/25 px-4 py-3">
                <div className="eyebrow-light mb-1">Режим</div>
                <div className="text-sm text-cream-100">
                  {scope === 'day' ? 'День' : 'Неделя'}
                </div>
              </div>
              <div className="rounded-2xl bg-black/25 px-4 py-3">
                <div className="eyebrow-light mb-1">Результат</div>
                <div className="text-sm text-cream-100">Таблица остатков</div>
              </div>
              <div className="rounded-2xl bg-black/25 px-4 py-3">
                <div className="eyebrow-light mb-1">Выход</div>
                <div className="text-sm text-cream-100">Остатки + закупка</div>
              </div>
            </div>
          </form>
        </DarkPanel>
      </div>

      {loading && <Spinner />}
      {error && <ErrorMessage message={error.message} status={error.status} />}

      {data && !loading && (
        <section className="panel mt-10 px-8 py-8 lg:px-10 lg:py-10">
          <div className="eyebrow-light mb-2">ОСТАТКИ</div>
          <h3 className="mb-2 text-2xl font-semibold text-cream-100">
            Остатки и закупка
          </h3>
          <p className="mb-6 max-w-xl text-sm text-ink-400">
            Складские остатки и прогноз закупки по ингредиентам.
            {data.scope === 'day'
              ? ` День ${formatDateLongRu(data.period_start)}`
              : ` Неделя ${formatWeekRange(data.period_start, data.period_end)}`}
            {' '}· позиций {data.items.length}.
          </p>

          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <div
              className="inline-flex rounded-full bg-black/25 p-1"
              data-testid="inventory-tabs"
            >
              {(
                [
                  ['all', `Все (${data.items.length})`],
                  ['to_buy', `Нужно закупить (${toBuyCount})`],
                ] as const
              ).map(([t, label]) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setTab(t)}
                  data-testid={`inventory-tab-${t.replace('_', '-')}`}
                  className={`rounded-full px-4 py-1.5 text-xs font-medium tracking-wide transition-all ${
                    tab === t
                      ? 'bg-cream-100 text-ink-900 shadow-sm'
                      : 'text-ink-400 hover:text-cream-100'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div data-testid="inventory-table">
            <InventoryTable
              items={filteredItems}
              emptyMessage={tab === 'to_buy' ? 'Все позиции в наличии' : 'Нет данных'}
            />
          </div>
        </section>
      )}
    </>
  );
}
