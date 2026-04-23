"""Юнит-тесты для app.utils.dt — московский таймзон."""
import datetime

from app.utils.dt import MSK, end_of_day, now, start_of_day, to_msk, today


class TestMSKConstant:
    def test_msk_is_utc_plus_3(self):
        assert MSK.utcoffset(None) == datetime.timedelta(hours=3)

    def test_msk_is_fixed_offset(self):
        assert isinstance(MSK, datetime.timezone)


class TestNow:
    def test_now_returns_aware_datetime(self):
        result = now()
        assert result.tzinfo is not None

    def test_now_returns_msk_timezone(self):
        result = now()
        assert result.utcoffset() == datetime.timedelta(hours=3)

    def test_now_close_to_current_utc(self):
        """now() в MSK = utcnow() + 3 часа (с погрешностью в секунду)."""
        n = now()
        utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
        diff_seconds = abs((n - utc_now).total_seconds())
        # Оба должны указывать на один и тот же момент времени
        assert diff_seconds < 1.0


class TestToday:
    def test_today_returns_date(self):
        result = today()
        assert isinstance(result, datetime.date)

    def test_today_matches_msk_now_date(self):
        result = today()
        assert result == now().date()


class TestToMSK:
    def test_converts_utc_to_msk(self):
        utc_dt = datetime.datetime(2026, 4, 21, 9, 0, tzinfo=datetime.timezone.utc)
        result = to_msk(utc_dt)
        assert result.hour == 12  # UTC+3
        assert result.utcoffset() == datetime.timedelta(hours=3)

    def test_preserves_moment_in_time(self):
        """Конвертация не изменяет абсолютный момент времени."""
        utc_dt = datetime.datetime(2026, 4, 21, 9, 0, tzinfo=datetime.timezone.utc)
        result = to_msk(utc_dt)
        assert result.timestamp() == utc_dt.timestamp()

    def test_idempotent_for_msk_datetime(self):
        msk_dt = datetime.datetime(2026, 4, 21, 12, 0, tzinfo=MSK)
        result = to_msk(msk_dt)
        assert result == msk_dt

    def test_converts_other_offset(self):
        """Нью-Йорк (UTC-5) → MSK (+3) = +8 часов."""
        ny_tz = datetime.timezone(datetime.timedelta(hours=-5))
        ny_dt = datetime.datetime(2026, 4, 21, 10, 0, tzinfo=ny_tz)
        result = to_msk(ny_dt)
        assert result.hour == 18


class TestStartOfDay:
    def test_returns_midnight(self):
        date = datetime.date(2026, 4, 21)
        result = start_of_day(date)
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0
        assert result.microsecond == 0

    def test_has_msk_timezone(self):
        date = datetime.date(2026, 4, 21)
        result = start_of_day(date)
        assert result.utcoffset() == datetime.timedelta(hours=3)

    def test_same_date(self):
        date = datetime.date(2026, 4, 21)
        result = start_of_day(date)
        assert result.date() == date


class TestEndOfDay:
    def test_returns_end_of_day(self):
        date = datetime.date(2026, 4, 21)
        result = end_of_day(date)
        assert result.hour == 23
        assert result.minute == 59
        assert result.second == 59

    def test_has_msk_timezone(self):
        date = datetime.date(2026, 4, 21)
        result = end_of_day(date)
        assert result.utcoffset() == datetime.timedelta(hours=3)

    def test_end_is_after_start(self):
        date = datetime.date(2026, 4, 21)
        assert end_of_day(date) > start_of_day(date)

    def test_start_and_end_same_date(self):
        date = datetime.date(2026, 4, 21)
        assert start_of_day(date).date() == end_of_day(date).date() == date
