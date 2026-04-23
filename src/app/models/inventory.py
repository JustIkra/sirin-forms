from typing import Literal

from pydantic import BaseModel, model_validator


class InventoryItem(BaseModel):
    product_id: str
    product_name: str
    stock: float
    need: float
    to_buy: float
    unit: str | None


class InventoryResponse(BaseModel):
    date: str
    scope: Literal["day", "week"] = "week"
    # period_start/end — новые поля: для scope=day равны date, для week —
    # понедельник..воскресенье. Если не переданы — берутся из week_start/week_end.
    period_start: str | None = None
    period_end: str | None = None
    # week_start/end оставлены для обратной совместимости с фронтом
    week_start: str
    week_end: str
    items: list[InventoryItem]

    @model_validator(mode="after")
    def _backfill_period(self) -> "InventoryResponse":
        if self.period_start is None:
            self.period_start = self.week_start
        if self.period_end is None:
            self.period_end = self.week_end
        return self
