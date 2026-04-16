from pydantic import BaseModel


class InventoryItem(BaseModel):
    product_id: str
    product_name: str
    stock: float
    need: float
    to_buy: float
    unit: str | None


class InventoryResponse(BaseModel):
    date: str
    week_start: str
    week_end: str
    items: list[InventoryItem]
