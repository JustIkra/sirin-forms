import os
from unittest.mock import patch

from app.config import Settings


def _base_env() -> dict[str, str]:
    return {
        "IIKO_SERVER_URL": "http://x",
        "IIKO_LOGIN": "a",
        "IIKO_PASSWORD": "b",
        "OPENROUTER_API_KEY": "k",
        "RESTAURANT_LAT": "55.0",
        "RESTAURANT_LON": "37.0",
    }


def test_threshold_defaults_match_spec():
    with patch.dict(os.environ, _base_env(), clear=True):
        s = Settings(_env_file=None)
    assert s.weekly_max_history_months == 36
    assert s.weekly_min_samples == 4
    assert s.weekly_min_sales_pct == 0.05
    assert s.weekly_min_accuracy == 0.0

    assert s.daily_max_history_months == 12
    assert s.daily_min_samples == 90
    assert s.daily_min_sales_pct == 0.05
    assert s.daily_min_accuracy == 10.0


def test_thresholds_overridable_from_env():
    env = _base_env() | {
        "WEEKLY_MIN_SAMPLES": "7",
        "DAILY_MIN_ACCURACY": "35.0",
    }
    with patch.dict(os.environ, env, clear=True):
        s = Settings(_env_file=None)
    assert s.weekly_min_samples == 7
    assert s.daily_min_accuracy == 35.0


def test_min_sales_pct_is_removed():
    with patch.dict(os.environ, _base_env(), clear=True):
        s = Settings(_env_file=None)
    assert not hasattr(s, "min_sales_pct")
