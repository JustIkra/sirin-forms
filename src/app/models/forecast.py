import datetime

from pydantic import BaseModel


class DishForecast(BaseModel):
    dish_id: str
    dish_name: str
    predicted_quantity: float
    confidence: float
    key_factors: list[str] = []


class DailyForecastResult(BaseModel):
    date: datetime.date
    forecasts: list[DishForecast]
    weather: str | None = None
    is_holiday: bool = False
    notes: str | None = None
    method: str = "llm"


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


class PlanFactSummary(BaseModel):
    total_predicted: float
    total_actual: float
    mape: float
    accuracy: float
    quality_rating: str
    dish_count: int


class PlanFactResponse(BaseModel):
    date: datetime.date
    records: list[PlanFactRecord]
    summary: PlanFactSummary


class BusinessRecommendation(BaseModel):
    category: str
    title: str
    description: str
    priority: int
    based_on: list[str] = []


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
