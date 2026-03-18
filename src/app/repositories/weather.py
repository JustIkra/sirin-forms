import datetime

from sqlalchemy import select

from app.db import WeatherRecord
from app.models.weather import DailyWeather
from app.repositories.base import BaseRepository


class WeatherRepository(BaseRepository[WeatherRecord]):
    model = WeatherRecord

    async def save_daily_weather(self, data: DailyWeather) -> WeatherRecord:
        existing = await self._get_by_date(data.date)
        if existing:
            existing.temp_min = data.temp_min
            existing.temp_max = data.temp_max
            existing.temp_avg = data.temp_avg
            existing.precipitation = data.precipitation
            existing.weather_main = data.weather_main
            existing.weather_description = data.weather_description
            existing.humidity = data.humidity
            existing.wind_speed = data.wind_speed
            await self._session.flush()
            return existing

        record = WeatherRecord(
            date=data.date,
            temp_min=data.temp_min,
            temp_max=data.temp_max,
            temp_avg=data.temp_avg,
            precipitation=data.precipitation,
            weather_main=data.weather_main,
            weather_description=data.weather_description,
            humidity=data.humidity,
            wind_speed=data.wind_speed,
        )
        return await self.create(record)

    async def get_weather_range(
        self, date_from: datetime.date, date_to: datetime.date,
    ) -> list[DailyWeather]:
        stmt = (
            select(WeatherRecord)
            .where(WeatherRecord.date >= date_from, WeatherRecord.date <= date_to)
            .order_by(WeatherRecord.date)
        )
        result = await self._session.execute(stmt)
        return [self._to_model(r) for r in result.scalars().all()]

    async def get_latest(self) -> DailyWeather | None:
        stmt = select(WeatherRecord).order_by(WeatherRecord.date.desc()).limit(1)
        result = await self._session.execute(stmt)
        record = result.scalar_one_or_none()
        return self._to_model(record) if record else None

    async def _get_by_date(self, date: datetime.date) -> WeatherRecord | None:
        stmt = select(WeatherRecord).where(WeatherRecord.date == date)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    def _to_model(record: WeatherRecord) -> DailyWeather:
        return DailyWeather(
            date=record.date,
            temp_min=record.temp_min,
            temp_max=record.temp_max,
            temp_avg=record.temp_avg,
            precipitation=record.precipitation,
            weather_main=record.weather_main,
            weather_description=record.weather_description,
            humidity=record.humidity,
            wind_speed=record.wind_speed,
        )
