import { useEffect, useState } from 'react';
import Spinner from '../components/Spinner';
import ErrorMessage from '../components/ErrorMessage';
import AccuracyChart from '../components/AccuracyChart';
import AccuracySummary from '../components/AccuracySummary';
import { fetchAccuracyHistory, ForecastError } from '../api/forecast';
import type { AccuracyHistoryResponse } from '../types/forecast';

export default function DashboardPage() {
  const [data, setData] = useState<AccuracyHistoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ message: string; status?: number } | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const result = await fetchAccuracyHistory(30);
        if (!cancelled) setData(result);
      } catch (err) {
        if (!cancelled) {
          if (err instanceof ForecastError) {
            setError({ message: err.message, status: err.status });
          } else {
            setError({ message: 'Не удалось загрузить данные дашборда' });
          }
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, []);

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-xl font-bold text-slate-900">Дашборд точности</h2>
        <p className="text-sm text-slate-500">
          Сравнение ML и ИИ-прогнозов за последние 30 дней
        </p>
      </div>

      {loading && <Spinner />}

      {error && <ErrorMessage message={error.message} status={error.status} />}

      {data && !loading && (
        <div className="space-y-6">
          <AccuracySummary summary={data.summary} />
          <AccuracyChart days={data.days} />
        </div>
      )}
    </div>
  );
}
