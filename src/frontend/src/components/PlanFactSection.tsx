import { useEffect, useState } from 'react';
import { fetchPlanFact } from '../api/forecast';
import type { PlanFactResponse } from '../types/forecast';
import PlanFactSummaryCard from './PlanFactSummary';
import PlanFactTable from './PlanFactTable';
import PlanFactChart from './PlanFactChart';

interface Props {
  forecastDate: string;
  method: 'llm' | 'ml';
}

export default function PlanFactSection({ forecastDate, method }: Props) {
  const [data, setData] = useState<PlanFactResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const today = new Date().toISOString().slice(0, 10);
    if (forecastDate > today) {
      setData(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchPlanFact(forecastDate, method)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch(() => {
        if (!cancelled) setError('Не удалось загрузить план-факт');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [forecastDate, method]);

  if (loading) {
    return (
      <div className="mt-8">
        <h2 className="mb-4 text-xl font-bold text-slate-900">План-факт</h2>
        <div className="flex items-center justify-center py-12">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-blue-600" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mt-8">
        <h2 className="mb-4 text-xl font-bold text-slate-900">План-факт</h2>
        <p className="text-sm text-red-600">{error}</p>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="mt-8 space-y-6">
      <h2 className="text-xl font-bold text-slate-900">План-факт</h2>
      <PlanFactSummaryCard summary={data.summary} />
      <div className="grid gap-6 xl:grid-cols-2">
        <PlanFactTable records={data.records} />
        <PlanFactChart records={data.records} />
      </div>
    </div>
  );
}
