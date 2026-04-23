import { useState, useEffect } from 'react';
import Layout from './components/Layout';
import ForecastForm from './components/ForecastForm';
import ForecastTable from './components/ForecastTable';
import ForecastMeta from './components/ForecastMeta';
import PlanFactSection from './components/PlanFactSection';
import ExportButtons from './components/ExportButtons';
import Spinner from './components/Spinner';
import ErrorMessage from './components/ErrorMessage';
import InventoryPage from './components/InventoryPage';
import TrendsPage from './components/TrendsPage';
import Hero from './components/Hero';
import DarkPanel from './components/DarkPanel';
import {
  fetchForecast,
  fetchPlanFact,
  fetchDailyForecast,
  fetchDailyPlanFact,
  ForecastError,
} from './api/forecast';
import type {
  DailyForecastResult,
  PlanFactResponse,
  PageId,
  ForecastMode,
} from './types/forecast';

export default function App() {
  const [page, setPage] = useState<PageId>('forecast');
  const [mode, setMode] = useState<ForecastMode>('weekly');

  const [weeklyResult, setWeeklyResult] = useState<DailyForecastResult | null>(null);
  const [weeklyLoading, setWeeklyLoading] = useState(false);
  const [weeklyError, setWeeklyError] = useState<{ message: string; status?: number } | null>(null);
  const [weeklyPF, setWeeklyPF] = useState<PlanFactResponse | null>(null);
  const [weeklyPFLoading, setWeeklyPFLoading] = useState(false);

  const [dailyResult, setDailyResult] = useState<DailyForecastResult | null>(null);
  const [dailyLoading, setDailyLoading] = useState(false);
  const [dailyError, setDailyError] = useState<{ message: string; status?: number } | null>(null);
  const [dailyPF, setDailyPF] = useState<PlanFactResponse | null>(null);
  const [dailyPFLoading, setDailyPFLoading] = useState(false);

  useEffect(() => {
    if (!weeklyResult) {
      setWeeklyPF(null);
      return;
    }
    const today = new Date().toISOString().slice(0, 10);
    if (weeklyResult.date > today) {
      setWeeklyPF(null);
      return;
    }
    let cancelled = false;
    setWeeklyPFLoading(true);
    fetchPlanFact(weeklyResult.date, weeklyResult.method)
      .then((data) => { if (!cancelled) setWeeklyPF(data); })
      .catch(() => { if (!cancelled) setWeeklyPF(null); })
      .finally(() => { if (!cancelled) setWeeklyPFLoading(false); });
    return () => { cancelled = true; };
  }, [weeklyResult]);

  useEffect(() => {
    if (!dailyResult) {
      setDailyPF(null);
      return;
    }
    const today = new Date().toISOString().slice(0, 10);
    if (dailyResult.date >= today) {
      setDailyPF(null);
      return;
    }
    let cancelled = false;
    setDailyPFLoading(true);
    fetchDailyPlanFact(dailyResult.date)
      .then((data) => { if (!cancelled) setDailyPF(data); })
      .catch(() => { if (!cancelled) setDailyPF(null); })
      .finally(() => { if (!cancelled) setDailyPFLoading(false); });
    return () => { cancelled = true; };
  }, [dailyResult]);

  const handleSubmit = async (date: string, force: boolean) => {
    if (mode === 'weekly') {
      setWeeklyLoading(true);
      setWeeklyError(null);
      try {
        const data = await fetchForecast(date, force, 'ml');
        setWeeklyResult(data);
      } catch (err) {
        if (err instanceof ForecastError) {
          setWeeklyError({ message: err.message, status: err.status });
        } else {
          setWeeklyError({ message: 'Не удалось подключиться к серверу' });
        }
        setWeeklyResult(null);
      } finally {
        setWeeklyLoading(false);
      }
    } else {
      setDailyLoading(true);
      setDailyError(null);
      try {
        const data = await fetchDailyForecast(date, force);
        setDailyResult(data);
      } catch (err) {
        if (err instanceof ForecastError) {
          setDailyError({ message: err.message, status: err.status });
        } else {
          setDailyError({ message: 'Не удалось подключиться к серверу' });
        }
        setDailyResult(null);
      } finally {
        setDailyLoading(false);
      }
    }
  };

  const activeResult = mode === 'weekly' ? weeklyResult : dailyResult;
  const activeLoading = mode === 'weekly' ? weeklyLoading : dailyLoading;
  const activeError = mode === 'weekly' ? weeklyError : dailyError;
  const activePF = mode === 'weekly' ? weeklyPF : dailyPF;
  const activePFLoading = mode === 'weekly' ? weeklyPFLoading : dailyPFLoading;

  return (
    <Layout activePage={page} onNavigate={setPage}>
      {page === 'forecast' && (
        <>
          <div className="grid grid-cols-1 items-stretch gap-10 pt-6 lg:grid-cols-2 lg:gap-16">
            <Hero
              eyebrow="ПРОГНОЗ СПРОСА ДЛЯ РЕСТОРАНА"
              title={
                <>
                  Прогноз спроса
                  <br />
                  по меню для
                  <br />
                  каждой смены
                </>
              }
              paragraphs={[
                'Дневной и недельный прогноз для ресторана: выбирайте режим, запускайте расчёт и получайте результат.',
                'Один экран для запуска, а ниже — таблица по блюдам, количеству и факторам спроса.',
              ]}
              secondary={
                <div>
                  <button
                    type="submit"
                    form="forecast-form"
                    disabled={activeLoading}
                    data-testid="forecast-submit"
                    className="btn-accent"
                  >
                    {activeLoading ? 'Расчёт...' : 'Запустить прогноз'}
                  </button>
                </div>
              }
            />

            <DarkPanel eyebrow="ПРОГНОЗ СПРОСА ДЛЯ РЕСТОРАНА" windowChrome>
              <ForecastForm
                onSubmit={handleSubmit}
                mode={mode}
                onModeChange={setMode}
              />
            </DarkPanel>
          </div>

          {activeLoading && <Spinner />}
          {activeError && (
            <ErrorMessage message={activeError.message} status={activeError.status} />
          )}

          {activeResult && !activeLoading && (
            <section
              id={mode === 'weekly' ? 'print-area-forecast' : 'print-area-daily'}
              className="panel mt-10 px-8 py-8 lg:px-10 lg:py-10"
            >
              <div className="eyebrow-light mb-3">РАСКРЫТЫЙ ПРОГНОЗ</div>
              <h3 className="mb-3 text-[26px] font-semibold leading-[1.15] text-cream-100">
                Прогноз по блюдам на выбранный период
              </h3>
              <p className="mb-7 max-w-xl text-[15px] leading-[1.55] text-ink-400">
                После запуска система показывает позиции меню, ожидаемое количество
                и факторы спроса, чтобы быстрее планировать закупки и работу кухни.
              </p>

              <div className="space-y-6">
                <ForecastMeta result={activeResult} summary={activePF?.summary} />
                <ForecastTable
                  forecasts={activeResult.forecasts}
                  planFact={activePF?.records}
                  mode={mode}
                  exportSlot={
                    <ExportButtons
                      date={activeResult.date}
                      method={activeResult.method}
                      type={mode === 'weekly' ? 'forecast' : 'daily'}
                    />
                  }
                />
                <PlanFactSection data={activePF} loading={activePFLoading} />
              </div>
            </section>
          )}
        </>
      )}

      {page === 'inventory' && <InventoryPage />}
      {page === 'trends' && <TrendsPage />}
    </Layout>
  );
}
