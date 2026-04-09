import datetime

from pydantic import BaseModel


class DishForecast(BaseModel):
    dish_id: str
    dish_name: str
    predicted_quantity: float
    confidence: float
    key_factors: list[str] = []
    price: float | None = None


class DailyForecastResult(BaseModel):
    date: datetime.date
    forecasts: list[DishForecast]
    weather: str | None = None
    is_holiday: bool = False
    notes: str | None = None
    method: str = "ml"


class IngredientNeed(BaseModel):
    ingredient_id: str
    ingredient_name: str
    unit: str
    required_amount: float
    buffered_amount: float


class ProcurementList(BaseModel):
    date_from: datetime.date
    date_to: datetime.date
    items: list[IngredientNeed]
    generated_at: datetime.datetime


class PlanFactRecord(BaseModel):
    date: datetime.date
    dish_id: str
    dish_name: str
    predicted_quantity: float
    actual_quantity: float
    deviation_pct: float
    predicted_revenue: float = 0.0
    actual_revenue: float = 0.0
    revenue_deviation_pct: float = 0.0


class PlanFactSummary(BaseModel):
    total_predicted: float
    total_actual: float
    mape: float
    accuracy: float
    quality_rating: str
    dish_count: int
    total_predicted_revenue: float = 0.0
    total_actual_revenue: float = 0.0


class PlanFactResponse(BaseModel):
    date: datetime.date
    records: list[PlanFactRecord]
    summary: PlanFactSummary


class DishDiscrepancyInsight(BaseModel):
    dish_name: str
    predicted_quantity: float
    actual_quantity: float
    deviation_pct: float
    explanation: str
    category: str


class DiscrepancyRecommendation(BaseModel):
    title: str
    description: str
    priority: int


class DiscrepancyAnalysisResponse(BaseModel):
    date: datetime.date
    method: str
    overall_analysis: str
    top_factors: list[str]
    dish_insights: list[DishDiscrepancyInsight]
    recommendations: list[DiscrepancyRecommendation]
    accuracy_context: str


# --- Accuracy History ---

class MethodAccuracy(BaseModel):
    accuracy: float
    mape: float
    dish_count: int


class AccuracyDayRecord(BaseModel):
    date: datetime.date
    weekday: str
    is_holiday: bool
    holiday_name: str | None = None
    ml: MethodAccuracy | None = None
    llm: MethodAccuracy | None = None
    actual_total: float


class AccuracyHistorySummary(BaseModel):
    ml_avg_accuracy: float
    llm_avg_accuracy: float
    days_count: int


class AccuracyHistoryResponse(BaseModel):
    days: list[AccuracyDayRecord]
    summary: AccuracyHistorySummary


# --- Dish Trends ---

class DishTrend(BaseModel):
    dish_name: str
    current_weekly_avg: float
    prev_weekly_avg: float
    change_pct: float
    trend_direction: str  # "growing" | "declining" | "stable"
    seasonality_factor: float | None = None
    weekly_data: list[float] = []
