from typing import Dict, List, Literal, Optional
from pydantic import BaseModel

ParameterStatus = Literal["safe", "warning", "critical", "unknown"]


class ParameterReading(BaseModel):
    value: Optional[float] = None
    unit: str
    status: ParameterStatus
    safe_min: float
    safe_max: float


class LatestReadingsResponse(BaseModel):
    timestamp: str
    is_online: bool
    last_updated_seconds_ago: Optional[int] = None
    readings: Dict[str, ParameterReading]


class HistoryPoint(BaseModel):
    timestamp: str
    value: float


class HistoryResponse(BaseModel):
    parameter: str
    unit: str
    range: str
    safe_min: float
    safe_max: float
    points: List[HistoryPoint]


class IngestReadingsRequest(BaseModel):
    temperature: Optional[float] = None
    ph: Optional[float] = None
    turbidity: Optional[float] = None
    tds: Optional[float] = None
    dissolved_oxygen: Optional[float] = None
