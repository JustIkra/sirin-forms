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


class BusinessRecommendation(BaseModel):
    category: str
    title: str
    description: str
    priority: int
    based_on: list[str] = []
