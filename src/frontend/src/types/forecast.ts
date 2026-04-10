export interface DishForecast {
  dish_id: string;
  dish_name: string;
  predicted_quantity: number;
  key_factors: string[];
  price: number | null;
}

export interface DailyForecastResult {
  date: string;
  forecasts: DishForecast[];
  weather: string | null;
  is_holiday: boolean;
  notes: string | null;
  method: 'ml';
}

export interface PlanFactRecord {
  date: string;
  dish_id: string;
  dish_name: string;
  predicted_quantity: number;
  actual_quantity: number;
  deviation_pct: number;
  predicted_revenue: number;
  actual_revenue: number;
  revenue_deviation_pct: number;
}

export interface PlanFactSummary {
  total_predicted: number;
  total_actual: number;
  mape: number;
  accuracy: number;
  quality_rating: string;
  dish_count: number;
  total_predicted_revenue: number;
  total_actual_revenue: number;
}

export interface PlanFactResponse {
  date: string;
  records: PlanFactRecord[];
  summary: PlanFactSummary;
}

// --- Discrepancy Analysis ---

export interface DishDiscrepancyInsight {
  dish_name: string;
  predicted_quantity: number;
  actual_quantity: number;
  deviation_pct: number;
  explanation: string;
  category: string;
}

export interface DiscrepancyRecommendation {
  title: string;
  description: string;
  priority: number;
}

export interface DiscrepancyAnalysisResponse {
  date: string;
  method: string;
  overall_analysis: string;
  top_factors: string[];
  dish_insights: DishDiscrepancyInsight[];
  recommendations: DiscrepancyRecommendation[];
  accuracy_context: string;
}

// --- Trends ---

export interface DishTrend {
  dish_name: string;
  current_weekly_avg: number;
  prev_weekly_avg: number;
  change_pct: number;
  trend_direction: 'growing' | 'declining' | 'stable';
  seasonality_factor: number | null;
  weekly_data: number[];
}

export interface TrendsResponse {
  weeks: number;
  growing: DishTrend[];
  declining: DishTrend[];
}

// --- Procurement ---

export interface IngredientNeed {
  ingredient_id: string;
  ingredient_name: string;
  unit: string;
  required_amount: number;
  buffered_amount: number;
}

export interface ProcurementList {
  date_from: string;
  date_to: string;
  items: IngredientNeed[];
  generated_at: string;
}

// --- Pages ---

export type PageId = 'forecast' | 'trends' | 'procurement';
