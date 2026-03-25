import { useEffect, useState } from 'react';
import { fetchTrends, ForecastError } from '../api/forecast';
import type { TrendsResponse } from '../types/forecast';
import TrendChart from '../components/TrendChart';
import TrendTable from '../components/TrendTable';
import Spinner from '../components/Spinner';
import ErrorMessage from '../components/ErrorMessage';

export default function TrendsPage() {
  const [data, setData] = useState<TrendsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ message: string; status?: number } | null>(null);

  useEffect(() => {
    let cancelled = false;

    setLoading(true);
    setError(null);

    fetchTrends(12)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (!cancelled) {
          if (err instanceof ForecastError) {
            setError({ message: err.message, status: err.status });
          } else {
            setError({ message: 'Не удалось загрузить тренды' });
          }
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <div className="mb-6">
        <h2 className="text-xl font-bold text-slate-900">Тренды спроса</h2>
        <p className="text-sm text-slate-500">
          Анализ изменения спроса по блюдам за последние {data?.weeks ?? 12} недель
        </p>
      </div>

      {loading && <Spinner />}

      {error && <ErrorMessage message={error.message} status={error.status} />}

      {data && !loading && (
        <div className="space-y-8">
          <TrendChart growing={data.growing} declining={data.declining} />

          {data.growing.length > 0 && (
            <section>
              <h3 className="mb-3 text-lg font-semibold text-slate-900">
                Растущие блюда
              </h3>
              <TrendTable trends={data.growing} />
            </section>
          )}

          {data.declining.length > 0 && (
            <section>
              <h3 className="mb-3 text-lg font-semibold text-slate-900">
                Падающие блюда
              </h3>
              <TrendTable trends={data.declining} />
            </section>
          )}

          {data.growing.length === 0 && data.declining.length === 0 && (
            <p className="py-12 text-center text-sm text-slate-500">
              Нет данных о трендах за выбранный период
            </p>
          )}
        </div>
      )}
    </>
  );
}
