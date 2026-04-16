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
import { fetchForecast, fetchPlanFact, ForecastError } from './api/forecast';
import type { DailyForecastResult, PlanFactResponse, PageId } from './types/forecast';

export default function App() {
  const [page, setPage] = useState<PageId>('forecast');
  const [result, setResult] = useState<DailyForecastResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<{ message: string; status?: number } | null>(null);
  const [planFact, setPlanFact] = useState<PlanFactResponse | null>(null);
  const [planFactLoading, setPlanFactLoading] = useState(false);

  useEffect(() => {
    if (!result) {
      setPlanFact(null);
      return;
    }
    const today = new Date().toISOString().slice(0, 10);
    if (result.date > today) {
      setPlanFact(null);
      return;
    }
    let cancelled = false;
    setPlanFactLoading(true);
    fetchPlanFact(result.date, result.method)
      .then((data) => { if (!cancelled) setPlanFact(data); })
      .catch(() => { if (!cancelled) setPlanFact(null); })
      .finally(() => { if (!cancelled) setPlanFactLoading(false); });
    return () => { cancelled = true; };
  }, [result]);

  const handleSubmit = async (date: string, force: boolean) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchForecast(date, force, 'ml');
      setResult(data);
    } catch (err) {
      if (err instanceof ForecastError) {
        setError({ message: err.message, status: err.status });
      } else {
        setError({ message: 'Не удалось подключиться к серверу' });
      }
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout activePage={page} onNavigate={setPage}>
      {page === 'forecast' && (
        <>
          <div className="mb-6">
            <h2 className="text-xl font-bold text-gradient">Недельный прогноз</h2>
            <p className="text-sm text-slate-400">
              Прогноз спроса на неделю по блюдам
            </p>
          </div>

          <ForecastForm
            onSubmit={handleSubmit}
            loading={loading}
          />

          {loading && <Spinner />}
          {error && <ErrorMessage message={error.message} status={error.status} />}

          {result && !loading && (
            <div id="print-area-forecast" className="mt-6 space-y-6">
              <ForecastMeta result={result} summary={planFact?.summary} />
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-white">Прогноз по блюдам (неделя)</h3>
                <ExportButtons date={result.date} method={result.method} type="forecast" />
              </div>
              <ForecastTable forecasts={result.forecasts} planFact={planFact?.records} />
              <PlanFactSection data={planFact} loading={planFactLoading} />
            </div>
          )}
        </>
      )}

      {page === 'inventory' && <InventoryPage />}

    </Layout>
  );
}
