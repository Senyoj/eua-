from typing import Dict
from fastapi import APIRouter, Depends, status
from app.models.settings import ThresholdConfig, ThresholdUpdateItem
from app.service.state_store import StateStore, get_state_store

router = APIRouter(prefix="/api/settings", tags=["Settings"])


@router.get("/thresholds", response_model=Dict[str, ThresholdConfig], status_code=status.HTTP_200_OK)
def get_thresholds(store: StateStore = Depends(get_state_store)):
    return {k: ThresholdConfig(**v) for k, v in store.thresholds.items()}


@router.put("/thresholds", response_model=Dict[str, ThresholdConfig], status_code=status.HTTP_200_OK)
def update_thresholds(
    payload: Dict[str, ThresholdUpdateItem],
    store: StateStore = Depends(get_state_store),
):
    updates = {k: v.model_dump(exclude_unset=True) for k, v in payload.items()}
    updated = store.update_thresholds(updates)
    return {k: ThresholdConfig(**v) for k, v in updated.items()}
