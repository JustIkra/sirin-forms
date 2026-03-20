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
}
