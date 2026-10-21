"""The small public picture of an auction (price, leader, end time). One shape for the API and for WebSocket events."""

from datetime import UTC, datetime


def iso(moment: datetime | None) -> str | None:
    return moment.astimezone(UTC).isoformat().replace('+00:00', 'Z') if moment else None
