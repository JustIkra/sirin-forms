import datetime

MSK = datetime.timezone(datetime.timedelta(hours=3))


def now() -> datetime.datetime:
    """Current datetime in Moscow timezone."""
    return datetime.datetime.now(tz=MSK)


def today() -> datetime.date:
    """Current date in Moscow timezone."""
    return now().date()


def to_msk(dt: datetime.datetime) -> datetime.datetime:
    """Convert any aware datetime to Moscow timezone."""
    return dt.astimezone(MSK)


def start_of_day(date: datetime.date) -> datetime.datetime:
    """Return midnight of the given date in Moscow timezone."""
    return datetime.datetime.combine(date, datetime.time.min, tzinfo=MSK)


def end_of_day(date: datetime.date) -> datetime.datetime:
    """Return 23:59:59.999999 of the given date in Moscow timezone."""
    return datetime.datetime.combine(date, datetime.time.max, tzinfo=MSK)
