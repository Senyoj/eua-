from pydantic import BaseModel, Field


class FeedingScheduleResponse(BaseModel):
    next_feed_time: str
    predicted_portion_grams: int
    ml_reasoning: str
    feeder_status: str
    feed_hopper_level_percent: int = Field(ge=0, le=100)


class FeedTriggerRequest(BaseModel):
    portion_grams: int = Field(default=100, ge=10, le=500)
    triggered_by: str = "manual_app_user"


class FeedTriggerResponse(BaseModel):
    success: bool
    message: str
    dispense_id: str
    dispensed_grams: int
    timestamp: str


class FeedLockoutResponse(BaseModel):
    success: bool = False
    message: str


class FeedHistoryItem(BaseModel):
    id: str
    timestamp: str
    portion_grams: int
    trigger_type: str
    status: str
    notes: str
