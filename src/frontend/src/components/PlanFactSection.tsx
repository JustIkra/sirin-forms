import { useEffect, useState } from 'react';
import type { DiscrepancyAnalysisResponse, PlanFactResponse } from '../types/forecast';
import { fetchDiscrepancyAnalysis } from '../api/forecast';
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

  if (loading || !data) return null;

  return (
    <div className="space-y-6">
      <DiscrepancyAnalysis
        data={analysis}
        loading={analysisLoading}
        error={analysisError}
        onRequestAnalysis={handleRequestAnalysis}
      />
    </div>
  );
}
