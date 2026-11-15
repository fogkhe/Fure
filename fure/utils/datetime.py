from datetime import UTC, datetime


def normalize_datetime(value: datetime) -> datetime:
    if value.utcoffset() is None:
        raise ValueError(
            "datetime must be timezone-aware",
        )

    return value.astimezone(UTC)
