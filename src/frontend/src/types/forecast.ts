export interface DishForecast {
  dish_id: string;
  dish_name: string;
  predicted_quantity: number;
  confidence: number;
  key_factors: string[];
}

export interface DailyForecastResult {
  date: string;
  forecasts: DishForecast[];
  weather: string | null;
  is_holiday: boolean;
  notes: string | null;
  method: 'llm' | 'ml';
}

export interface PlanFactRecord {
  date: string;
  dish_id: string;
  dish_name: string;
  predicted_quantity: number;
  actual_quantity: number;
  deviation_pct: number;
}

export interface PlanFactSummary {
  total_predicted: number;
  total_actual: number;
  mape: number;
  accuracy: number;
  quality_rating: string;
  dish_count: number;
}

export interface PlanFactResponse {
  date: string;
  records: PlanFactRecord[];
  summary: PlanFactSummary;
}

// --- Dashboard ---

export interface MethodAccuracy {
  accuracy: number;
  mape: number;
  dish_count: number;
}

export interface AccuracyDayRecord {
  date: string;
  weekday: string;
  is_holiday: boolean;
  holiday_name: string | null;
  ml: MethodAccuracy | null;
  llm: MethodAccuracy | null;
  actual_total: number;
}

export interface AccuracyHistoryResponse {
  days: AccuracyDayRecord[];
  summary: {
    ml_avg_accuracy: number;
    llm_avg_accuracy: number;
    days_count: number;
  };
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

export type PageId = 'dashboard' | 'forecast' | 'trends' | 'procurement';
