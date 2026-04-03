import { useEffect, useState } from 'react';
import type { DiscrepancyAnalysisResponse, PlanFactResponse } from '../types/forecast';
import { fetchDiscrepancyAnalysis } from '../api/forecast';
import PlanFactSummaryCard from './PlanFactSummary';
import PlanFactTable from './PlanFactTable';
import DiscrepancyAnalysis from './DiscrepancyAnalysis';

interface Props {
  data: PlanFactResponse | null;
  loading: boolean;
}

export default function PlanFactSection({ data, loading }: Props) {
  const [analysis, setAnalysis] = useState<DiscrepancyAnalysisResponse | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  useEffect(() => {
    setAnalysis(null);
    setAnalysisError(null);
  }, [data?.date]);

  const handleRequestAnalysis = async () => {
    if (!data) return;
    setAnalysisLoading(true);
    setAnalysisError(null);
    try {
      const result = await fetchDiscrepancyAnalysis(data.date);
      setAnalysis(result);
    } catch (err) {
      setAnalysisError(err instanceof Error ? err.message : 'Ошибка анализа');
    } finally {
      setAnalysisLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="mt-8">
        <h2 className="mb-4 text-xl font-bold text-white">План-факт</h2>
        <div className="flex items-center justify-center py-12">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-white/10 border-t-blue-400" />
        </div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="mt-8 space-y-6">
      <h2 className="text-xl font-bold text-white">План-факт</h2>
      <PlanFactSummaryCard summary={data.summary} />
      <PlanFactTable records={data.records} />
      <DiscrepancyAnalysis
        data={analysis}
        loading={analysisLoading}
        error={analysisError}
        onRequestAnalysis={handleRequestAnalysis}
      />
    </div>
  );
}
