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
        <h2 className="text-xl font-bold text-gradient">Лист закупок</h2>
        <p className="text-sm text-slate-400">
          Расчёт потребности в ингредиентах на основе прогноза спроса
        </p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-4">
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-300">
            Дата
          </label>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-white focus:border-blue-400 focus:ring-1 focus:ring-blue-400/30 focus:outline-none"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-slate-300">
            Метод
          </label>
          <div className="inline-flex rounded-md border border-white/10">
            <button
              type="button"
              onClick={() => setMethod('llm')}
              className={`px-4 py-2 text-sm font-medium rounded-l-md transition-colors ${
                method === 'llm'
                  ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/25'
                  : 'bg-white/5 text-slate-400 hover:bg-white/[0.08]'
              }`}
            >
              ИИ-прогноз
            </button>
            <button
              type="button"
              onClick={() => setMethod('ml')}
              className={`px-4 py-2 text-sm font-medium rounded-r-md border-l border-white/10 transition-colors ${
                method === 'ml'
                  ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/25'
                  : 'bg-white/5 text-slate-400 hover:bg-white/[0.08]'
              }`}
            >
              ML-прогноз
            </button>
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-gradient-to-r from-blue-600 to-blue-500 px-5 py-2 text-sm font-medium text-white shadow-lg shadow-blue-500/25 transition-colors hover:from-blue-500 hover:to-blue-400 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? 'Расчёт...' : 'Рассчитать закупки'}
        </button>
      </form>

      {loading && <Spinner />}

      {error && <ErrorMessage message={error.message} status={error.status} />}

      {data && !loading && (
        <div id="print-area-procurement" className="mt-6 space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-400">
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
