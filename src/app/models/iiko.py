import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class ProductType(StrEnum):
    DISH = "dish"
    MODIFIER = "modifier"
    GOODS = "goods"
    OUTER = "outer"
    PREPARED = "prepared"
    SERVICE = "service"


class OlapReportType(StrEnum):
    SALES = "SALES"
    TRANSACTIONS = "TRANSACTIONS"
    DELIVERIES = "DELIVERIES"
    STOCK = "STOCK"


class ProductIngredient(BaseModel):
    product_id: str
    name: str
    amount: float
    unit: str


class IikoProduct(BaseModel):
    id: str
    name: str
    code: str | None = None
    product_type: ProductType
    price: float | None = None
    ingredients: list[ProductIngredient] = []


class SaleRecord(BaseModel):
    date: datetime.date
    dish_id: str
    dish_name: str
    quantity: float
    price: float
    total: float


class DailySalesTotal(BaseModel):
    date: datetime.date
    total_quantity: float
    total_revenue: float
    dish_count: int


class IikoStore(BaseModel):
    id: str
    name: str
    type: str | None = None


class IikoDepartment(BaseModel):
    id: str
    name: str
    parent_id: str | None = None


class IikoSupplier(BaseModel):
    id: str
    name: str
    code: str | None = None


class OlapV2Request(BaseModel):
    report_type: OlapReportType
    date_from: datetime.date
    date_to: datetime.date
    group_by_row_fields: list[str] = []
    group_by_col_fields: list[str] = []
    aggregate_fields: list[str] = []
    filters: dict[str, Any] = {}


class IikoOlapReport(BaseModel):
    report_type: OlapReportType
    date_from: datetime.date
    date_to: datetime.date
    data: list[dict]
