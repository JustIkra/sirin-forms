import datetime

from sqlalchemy import String, Float, Integer, Date, DateTime, Text, ForeignKey, LargeBinary, JSON
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.utils.dt import MSK


class Base(DeclarativeBase):
    pass


class WeatherRecord(Base):
    __tablename__ = "weather_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[datetime.date] = mapped_column(Date, unique=True, index=True)
    temp_min: Mapped[float] = mapped_column(Float)
    temp_max: Mapped[float] = mapped_column(Float)
    temp_avg: Mapped[float] = mapped_column(Float)
    precipitation: Mapped[float] = mapped_column(Float, default=0.0)
    weather_main: Mapped[str] = mapped_column(String(50))
    weather_description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    humidity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wind_speed: Mapped[float | None] = mapped_column(Float, nullable=True)


class ProductRecord(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    product_type: Mapped[str] = mapped_column(String(20))
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    included_in_menu: Mapped[bool] = mapped_column(default=False)

    ingredients: Mapped[list["IngredientRecord"]] = relationship(
        back_populates="product", cascade="all, delete-orphan",
    )


class IngredientRecord(Base):
    __tablename__ = "product_ingredients"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("products.id"), index=True,
    )
    ingredient_id: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(200))
    amount: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(20))

    product: Mapped["ProductRecord"] = relationship(back_populates="ingredients")


class SaleRecordDb(Base):
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[datetime.date] = mapped_column(Date, index=True)
    dish_id: Mapped[str] = mapped_column(String(50), index=True)
    dish_name: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    total: Mapped[float] = mapped_column(Float)


class ForecastRecord(Base):
    __tablename__ = "forecasts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[datetime.date] = mapped_column(Date, index=True)
    dish_id: Mapped[str] = mapped_column(String(50))
    dish_name: Mapped[str] = mapped_column(String(200))
    predicted_quantity: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    key_factors: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingredients: Mapped[str | None] = mapped_column(Text, nullable=True)
    weather: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_holiday: Mapped[bool] = mapped_column(default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    method: Mapped[str] = mapped_column(String(10), default="ml")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(tz=MSK),
    )


class DishCatalogRecord(Base):
    __tablename__ = "dish_catalog"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    canonical_name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(50), index=True)
    is_revenue: Mapped[bool] = mapped_column(default=True)
    dish_ids: Mapped[list] = mapped_column(JSON, default=list)
    total_volume: Mapped[float] = mapped_column(Float, default=0.0)
    total_revenue: Mapped[float] = mapped_column(Float, default=0.0)
    unit_cost: Mapped[float | None] = mapped_column(Float, nullable=True)


class MLModelRecord(Base):
    __tablename__ = "ml_models"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dish_id: Mapped[str] = mapped_column(String(50), index=True)
    dish_name: Mapped[str] = mapped_column(String(200))
    model_blob: Mapped[bytes] = mapped_column(LargeBinary)
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    feature_names: Mapped[list | None] = mapped_column(JSON, nullable=True)
    trained_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(tz=MSK),
    )
    samples_count: Mapped[int] = mapped_column(Integer, default=0)
    granularity: Mapped[str] = mapped_column(String(10), default="weekly")


class MenuSnapshotRecord(Base):
    """Daily snapshot of iiko menu + stop-list (Domain 1).

    Populated at 04:00 MSK before retraining. Forecast and training pipelines
    read from this table, not from live iiko. A dish missing from the snapshot
    = missing from iiko (deleted) → not forecasted and not trained.
    """

    __tablename__ = "menu_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    snapshot_date: Mapped[datetime.date] = mapped_column(Date, index=True)
    dish_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("products.id"), index=True,
    )
    included_in_menu: Mapped[bool] = mapped_column(default=False)
    in_stop_list: Mapped[bool] = mapped_column(default=False)


def create_engine(database_url: str):
    return create_async_engine(database_url, echo=False)


def create_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
