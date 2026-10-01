from datetime import datetime

from fastapi import HTTPException, Query

from app.models.schemas import ParameterKey, TimeRange

ZONE_ERRORS = {404: {"description": "Zone not found"}, 422: {"description": "Invalid query parameters"}}


class WindowParams:
    def __init__(self,
                 time_range: TimeRange | None = Query(None, description="Relative range ending at the zone's latest data. Default 24h."),
                 start: datetime | None = Query(None, description="Explicit ISO-8601 start (use with end)."),
                 end: datetime | None = Query(None, description="Explicit ISO-8601 end (use with start).")):
        self.time_range, self.start, self.end = time_range, start, end


def parameter_query(default: str = "pm25"):
    return Query(default, description="Parameter key: pm25, pm10, no2, ph, turbidity, dissolved_oxygen")


def raise_http(exc: Exception):
    from app.services.dashboard import BadRequest, NotFound
    if isinstance(exc, NotFound):
        raise HTTPException(404, str(exc))
    if isinstance(exc, BadRequest):
        raise HTTPException(422, str(exc))
    raise exc


__all__ = ["WindowParams", "parameter_query", "raise_http", "ZONE_ERRORS", "ParameterKey"]
