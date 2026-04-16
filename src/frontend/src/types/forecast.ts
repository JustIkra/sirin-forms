export interface DishForecast {
  dish_id: string;
  dish_name: string;
  predicted_quantity: number;
  key_factors: string[];
  price: number | null;
  prediction_method: 'ml' | 'fallback';
}

export interface DailyForecastResult {
  date: string;
  forecasts: DishForecast[];
  weather: string | null;
  is_holiday: boolean;
  notes: string | null;
  method: 'ml';
  ml_count: number;
  fallback_count: number;
  week_start: string | null;
  week_end: string | null;
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

// --- Inventory ---

export interface InventoryItem {
  product_id: string;
  product_name: string;
  stock: number;
  need: number;
  to_buy: number;
  unit: string | null;
}

export interface InventoryResponse {
  date: string;
  week_start: string;
  week_end: string;
  items: InventoryItem[];
}

// --- Pages ---

export type PageId = 'forecast' | 'inventory';
