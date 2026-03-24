from __future__ import annotations

from fastapi import APIRouter, Query, Request

from backend.schemas import AlertPreferences, AlertPreferencesUpdate, AlertsResponse

router = APIRouter(tags=["alerts"])

DEFAULT_USER_ID = "local"


def resolve_user_id(request: Request, user_id: str | None) -> str:
    return user_id or request.headers.get("X-User-Id") or DEFAULT_USER_ID


@router.get("/alerts", response_model=AlertsResponse)
async def get_alerts(
    request: Request,
    user_id: str | None = Query(default=None),
    symbol: str = Query(..., min_length=1),
    timeframe: str = Query(..., pattern="^(15m|1h|4h|24h)$"),
    snapshot_id: str = Query(..., min_length=3),
    signal_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> AlertsResponse:
    service = request.app.state.signal_service
    return await service.get_alerts(
        user_id=resolve_user_id(request, user_id),
        symbol=symbol,
        timeframe=timeframe,
        snapshot_id=snapshot_id,
        signal_type=signal_type,
        limit=limit,
    )


@router.get("/alerts/preferences", response_model=AlertPreferences)
async def get_alert_preferences(
    request: Request,
    user_id: str | None = Query(default=None),
) -> AlertPreferences:
    service = request.app.state.signal_service
    return await service.get_alert_preferences(resolve_user_id(request, user_id))


@router.put("/alerts/preferences", response_model=AlertPreferences)
async def update_alert_preferences(
    request: Request,
    payload: AlertPreferencesUpdate,
    user_id: str | None = Query(default=None),
) -> AlertPreferences:
    service = request.app.state.signal_service
    return await service.update_alert_preferences(resolve_user_id(request, user_id), payload)
