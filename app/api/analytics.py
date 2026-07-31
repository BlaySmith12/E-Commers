"""Analytics API endpoints for dashboard.

Provides:
- Visitor tracking (POST /api/analytics/visit)
- Visitor analytics (GET /api/analytics/visitors)
- Customer growth analytics (GET /api/analytics/customer-growth)
- Recent activity feed (GET /api/analytics/activity)
- Dashboard overview (GET /api/analytics/dashboard)
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.catalog import (
    User, ActivityLog, StoreVisit,
    Role, Permission,
)
from app.activity import (
    log_activity,
    record_visit,
    get_visitor_analytics,
    get_customer_growth_analytics,
    get_recent_activities,
)
from app.security import RequireViewer

router = APIRouter(prefix='/analytics', tags=['Analytics'])


# ─── Schemas ────────────────────────────────────────────────────────────────

class VisitIn(BaseModel):
    fingerprint: str
    page_url: str = "/"
    referrer: str = ""


# ─── Visitor Tracking ────────────────────────────────────────────────────────

@router.post('/visit')
async def track_visit(
    payload: VisitIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Record a storefront page visit. Called by the frontend tracking script."""
    ua = request.headers.get("user-agent", "")
    ref = request.headers.get("referer", "") or payload.referrer
    ip = request.client.host if request.client else ""
    user_id = None
    try:
        from app.security import decode_access_token
        token = request.cookies.get("access_token") or ""
        if token:
            uid = decode_access_token(token)
            if uid:
                user_id = int(uid)
    except Exception:
        pass

    visit = await record_visit(
        db=db,
        fingerprint=payload.fingerprint,
        page_url=payload.page_url,
        user_agent=ua,
        referrer=ref,
        ip_address=ip,
        user_id=user_id,
    )
    await db.commit()
    return {"status": "ok", "recorded": visit is not None}


# ─── Visitor Analytics ───────────────────────────────────────────────────────

@router.get('/visitors')
async def visitor_analytics(
    range: str = Query("7d", description="Date range: today, yesterday, 7d, 30d, month, last_month, custom"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(RequireViewer),
):
    """Get visitor analytics for the admin dashboard."""
    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if range == "today":
        start, end = today, today + timedelta(days=1)
    elif range == "yesterday":
        start, end = today - timedelta(days=1), today
    elif range == "7d":
        start, end = today - timedelta(days=7), today + timedelta(days=1)
    elif range == "30d":
        start, end = today - timedelta(days=30), today + timedelta(days=1)
    elif range == "month":
        start = today.replace(day=1)
        end = (start + timedelta(days=32)).replace(day=1)
    elif range == "last_month":
        first_this_month = today.replace(day=1)
        start = (first_this_month - timedelta(days=1)).replace(day=1)
        end = first_this_month
    elif range == "custom" and date_from and date_to:
        try:
            start = datetime.fromisoformat(date_from)
            end = datetime.fromisoformat(date_to) + timedelta(days=1)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")
    else:
        start, end = today - timedelta(days=7), today + timedelta(days=1)

    try:
        data = await get_visitor_analytics(db, start, end)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analytics query failed: {str(e)}")

    return data


# ─── Customer Growth Analytics ───────────────────────────────────────────────

@router.get('/customer-growth')
async def customer_growth(
    range: str = Query("30d"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(RequireViewer),
):
    """Get customer growth analytics for the admin dashboard."""
    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if range == "today":
        start, end = today, today + timedelta(days=1)
    elif range == "7d":
        start, end = today - timedelta(days=7), today + timedelta(days=1)
    elif range == "30d":
        start, end = today - timedelta(days=30), today + timedelta(days=1)
    elif range == "month":
        start = today.replace(day=1)
        end = (start + timedelta(days=32)).replace(day=1)
    elif range == "last_month":
        first_this_month = today.replace(day=1)
        start = (first_this_month - timedelta(days=1)).replace(day=1)
        end = first_this_month
    elif range == "year":
        start = today.replace(month=1, day=1)
        end = today + timedelta(days=1)
    elif range == "custom" and date_from and date_to:
        try:
            start = datetime.fromisoformat(date_from)
            end = datetime.fromisoformat(date_to) + timedelta(days=1)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")
    else:
        start, end = today - timedelta(days=30), today + timedelta(days=1)

    try:
        data = await get_customer_growth_analytics(db, start, end)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Growth query failed: {str(e)}")

    return data


# ─── Recent Activity Feed ────────────────────────────────────────────────────

@router.get('/activity')
async def recent_activity(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(RequireViewer),
):
    """Get recent activity feed for the admin dashboard."""
    try:
        activities = await get_recent_activities(db, limit=limit, offset=offset)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Activity query failed: {str(e)}")

    _HIDE_TYPES = {'order_created', 'payment_failed', 'order_cancelled'}
    result = []
    for a in activities:
        if a.activity_type in _HIDE_TYPES:
            continue
        result.append({
            "id": a.id,
            "activity_type": a.activity_type,
            "description": a.description,
            "entity_type": a.entity_type,
            "entity_id": a.entity_id,
            "entity_number": a.entity_number,
            "actor_name": a.actor_name,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        })
    return {"activities": result}


# ─── Dashboard Overview (combined) ──────────────────────────────────────────

@router.get('/dashboard')
async def dashboard_overview(
    range: str = Query("30d"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(RequireViewer),
):
    """Combined dashboard overview data for the admin."""
    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if range == "today":
        start, end = today, today + timedelta(days=1)
    elif range == "7d":
        start, end = today - timedelta(days=7), today + timedelta(days=1)
    elif range == "30d":
        start, end = today - timedelta(days=30), today + timedelta(days=1)
    elif range == "month":
        start = today.replace(day=1)
        end = (start + timedelta(days=32)).replace(day=1)
    elif range == "custom" and date_from and date_to:
        try:
            start = datetime.fromisoformat(date_from)
            end = datetime.fromisoformat(date_to) + timedelta(days=1)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")
    else:
        start, end = today - timedelta(days=30), today + timedelta(days=1)

    try:
        visitor_data = await get_visitor_analytics(db, start, end)
        growth_data = await get_customer_growth_analytics(db, start, end)
        activities = await get_recent_activities(db, limit=15)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dashboard query failed: {str(e)}")

    activity_list = [
        {
            "id": a.id,
            "activity_type": a.activity_type,
            "description": a.description,
            "entity_type": a.entity_type,
            "entity_id": a.entity_id,
            "entity_number": a.entity_number,
            "actor_name": a.actor_name,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in activities
    ]

    return {
        "visitors": visitor_data,
        "customer_growth": growth_data,
        "activities": activity_list,
    }
