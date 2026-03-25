import { useState } from 'react';
import Spinner from '../components/Spinner';
import ErrorMessage from '../components/ErrorMessage';
import ProcurementTable from '../components/ProcurementTable';
import ExportButtons from '../components/ExportButtons';
import { fetchProcurement, ForecastError } from '../api/forecast';
import type { ProcurementList } from '../types/forecast';

function todayMSK(): string {
  return new Date().toLocaleDateString('sv-SE', { timeZone: 'Europe/Moscow' });
}

export default function ProcurementPage() {
  const [date, setDate] = useState(todayMSK);
  const [method, setMethod] = useState<'llm' | 'ml'>('ml');
  const [data, setData] = useState<ProcurementList | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<{ message: string; status?: number } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const result = await fetchProcurement(date, method);
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

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-xl font-bold text-slate-900">Лист закупок</h2>
        <p className="text-sm text-slate-500">
          Расчёт потребности в ингредиентах на основе прогноза спроса
        </p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-4">
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">
            Дата
          </label>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">
            Метод
          </label>
          <div className="inline-flex rounded-md border border-slate-300 shadow-sm">
            <button
              type="button"
              onClick={() => setMethod('llm')}
              className={`px-4 py-2 text-sm font-medium rounded-l-md transition-colors ${
                method === 'llm'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-slate-700 hover:bg-slate-50'
              }`}
            >
              ИИ-прогноз
            </button>
            <button
              type="button"
              onClick={() => setMethod('ml')}
              className={`px-4 py-2 text-sm font-medium rounded-r-md border-l border-slate-300 transition-colors ${
                method === 'ml'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-slate-700 hover:bg-slate-50'
              }`}
            >
              ML-прогноз
            </button>
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-blue-600 px-5 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? 'Расчёт...' : 'Рассчитать закупки'}
        </button>
      </form>

      {loading && <Spinner />}

      {error && <ErrorMessage message={error.message} status={error.status} />}

      {data && !loading && (
        <div className="mt-6 space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-500">
              Период: {data.date_from} — {data.date_to} | Позиций: {data.items.length}
            </p>
            <ExportButtons date={date} method={method} type="procurement" />
          </div>
          <ProcurementTable items={data.items} />
        </div>
      )}
    </div>
  );
}
