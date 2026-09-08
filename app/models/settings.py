from typing import Optional
from pydantic import BaseModel


class ThresholdConfig(BaseModel):
    min: float
    max: float
    unit: Optional[str] = None


class ThresholdUpdateItem(BaseModel):
    min: Optional[float] = None
    max: Optional[float] = None
