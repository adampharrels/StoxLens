from datetime import UTC, datetime


def utcnow_naive() -> datetime:
    """Current UTC time without tzinfo, matching the naive UTC values stored in DateTime columns."""
    return datetime.now(UTC).replace(tzinfo=None)
