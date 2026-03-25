import { useState } from 'react';
import Layout from './components/Layout';
import ForecastForm from './components/ForecastForm';
import ForecastTable from './components/ForecastTable';
import ForecastChart from './components/ForecastChart';
import ForecastMeta from './components/ForecastMeta';
import PlanFactSection from './components/PlanFactSection';
import Spinner from './components/Spinner';
import ErrorMessage from './components/ErrorMessage';
import DashboardPage from './pages/DashboardPage';
import TrendsPage from './pages/TrendsPage';
import ProcurementPage from './pages/ProcurementPage';
import { fetchForecast, ForecastError } from './api/forecast';
import type { DailyForecastResult, PageId } from './types/forecast';

export default function App() {
  const [page, setPage] = useState<PageId>('forecast');
  const [result, setResult] = useState<DailyForecastResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<{ message: string; status?: number } | null>(null);
  const [method, setMethod] = useState<'llm' | 'ml'>('llm');

  const handleSubmit = async (date: string, force: boolean, m: 'llm' | 'ml') => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchForecast(date, force, m);
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
      {page === 'dashboard' && <DashboardPage />}

      {page === 'forecast' && (
        <>
          <div className="mb-6">
            <h2 className="text-xl font-bold text-slate-900">Прогнозный прогон</h2>
            <p className="text-sm text-slate-500">
              Сборка forecast packet: формирование прогноза спроса
            </p>
          </div>

          <ForecastForm
            onSubmit={handleSubmit}
            loading={loading}
            method={method}
            onMethodChange={setMethod}
          />

          {loading && <Spinner />}
          {error && <ErrorMessage message={error.message} status={error.status} />}

          {result && !loading && (
            <div className="mt-6 space-y-6">
              <ForecastMeta result={result} />
              <div className="grid gap-6 xl:grid-cols-2">
                <ForecastTable forecasts={result.forecasts} />
                <ForecastChart forecasts={result.forecasts} />
              </div>
              <PlanFactSection forecastDate={result.date} method={result.method} />
            </div>
          )}
        </>
      )}

      {page === 'trends' && <TrendsPage />}

      {page === 'procurement' && <ProcurementPage />}
    </Layout>
  );
}
