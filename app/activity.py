"""Activity logging utility for the admin dashboard.

Logs real application events (orders, payments, registrations, etc.)
to the activity_logs table so the dashboard can display them.
"""

import hashlib
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import ActivityLog, StoreVisit, User


# ─── Activity Logging ────────────────────────────────────────────────────────

async def log_activity(
    db: AsyncSession,
    activity_type: str,
    description: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    entity_number: Optional[str] = None,
    actor_name: Optional[str] = None,
    actor_id: Optional[int] = None,
    metadata: Optional[dict] = None,
) -> ActivityLog:
    """Create an activity log entry. Returns the created entry."""
    entry = ActivityLog(
        activity_type=activity_type,
        description=description,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_number=entity_number,
        actor_name=actor_name,
        actor_id=actor_id,
        metadata=metadata,
        created_at=datetime.utcnow(),
    )
    db.add(entry)
    await db.flush()
    return entry


async def get_recent_activities(
    db: AsyncSession,
    limit: int = 20,
    offset: int = 0,
    activity_type: Optional[str] = None,
) -> list[ActivityLog]:
    """Fetch recent activities ordered by newest first."""
    stmt = select(ActivityLog).order_by(ActivityLog.created_at.desc())
    if activity_type:
        stmt = stmt.where(ActivityLog.activity_type == activity_type)
    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ─── Visitor Tracking ────────────────────────────────────────────────────────

def _hash_value(value: str) -> str:
    """SHA-256 hash a value for privacy."""
    return hashlib.sha256(value.encode()).hexdigest()[:32]


def _detect_device_type(user_agent: str) -> str:
    """Simple device type detection from User-Agent."""
    ua = (user_agent or "").lower()
    if any(k in ua for k in ("mobile", "android", "iphone", "ipod")):
        return "mobile"
    if any(k in ua for k in ("ipad", "tablet")):
        return "tablet"
    return "desktop"


def _detect_browser(user_agent: str) -> str:
    ua = (user_agent or "").lower()
    if "edg/" in ua or "edge/" in ua:
        return "Edge"
    if "chrome/" in ua and "safari/" in ua:
        return "Chrome"
    if "firefox/" in ua:
        return "Firefox"
    if "safari/" in ua:
        return "Safari"
    return "Other"


def _detect_os(user_agent: str) -> str:
    ua = (user_agent or "").lower()
    if "windows" in ua:
        return "Windows"
    if "mac os" in ua or "macos" in ua:
        return "macOS"
    if "linux" in ua and "android" not in ua:
        return "Linux"
    if "android" in ua:
        return "Android"
    if any(k in ua for k in ("iphone", "ipad", "ipod")):
        return "iOS"
    return "Other"


async def record_visit(
    db: AsyncSession,
    fingerprint: str,
    page_url: str,
    user_agent: str = "",
    referrer: str = "",
    ip_address: str = "",
    user_id: Optional[int] = None,
    visited_at: Optional[datetime] = None,
) -> Optional[StoreVisit]:
    """Record a store visit.

    Prevents duplicate unique visitors within 30 minutes using the fingerprint.
    Returns the StoreVisit if recorded, None if deduplicated.
    """
    now = visited_at or datetime.utcnow()
    thirty_min_ago = now - timedelta(minutes=30)

    # Check if same fingerprint visited within last 30 minutes (for unique dedup)
    existing = await db.execute(
        select(StoreVisit).where(
            StoreVisit.visitor_fingerprint == fingerprint[:32],
            StoreVisit.visited_at >= thirty_min_ago,
        ).order_by(StoreVisit.visited_at.desc()).limit(1)
    )
    if existing.scalar_one_or_none():
        # Same session – record as return visit but not unique
        pass

    visit = StoreVisit(
        visitor_fingerprint=fingerprint[:32],
        page_url=page_url[:500] if page_url else "/",
        referrer=(referrer or "")[:500] if referrer else None,
        device_type=_detect_device_type(user_agent),
        browser=_detect_browser(user_agent),
        os=_detect_os(user_agent),
        ip_hash=_hash_value(ip_address) if ip_address else None,
        user_id=user_id,
        visited_at=now,
    )
    db.add(visit)
    await db.flush()
    return visit


async def get_visitor_analytics(
    db: AsyncSession,
    start_date: datetime,
    end_date: datetime,
) -> dict:
    """Get visitor analytics for a date range.

    Returns:
        total_visits: total page views
        unique_visitors: distinct visitor fingerprints
        daily: list of {date, total_visits, unique_visitors}
        by_device: list of {device_type, count}
        by_browser: list of {browser, count}
    """
    base = and_(
        StoreVisit.visited_at >= start_date,
        StoreVisit.visited_at < end_date,
    )

    # Total visits
    total_result = await db.execute(
        select(func.count(StoreVisit.id)).where(base)
    )
    total_visits = total_result.scalar_one() or 0

    # Unique visitors (distinct fingerprints)
    unique_result = await db.execute(
        select(func.count(func.distinct(StoreVisit.visitor_fingerprint))).where(base)
    )
    unique_visitors = unique_result.scalar_one() or 0

    # Daily breakdown
    daily_stmt = select(
        func.date(StoreVisit.visited_at).label("day"),
        func.count(StoreVisit.id).label("total"),
        func.count(func.distinct(StoreVisit.visitor_fingerprint)).label("unique"),
    ).where(base).group_by(func.date(StoreVisit.visited_at)).order_by(func.date(StoreVisit.visited_at))
    daily_result = await db.execute(daily_stmt)
    daily = [
        {"date": str(row.day), "total_visits": row.total, "unique_visitors": row.unique}
        for row in daily_result.fetchall()
    ]

    # By device
    device_stmt = select(
        StoreVisit.device_type, func.count(StoreVisit.id)
    ).where(base).group_by(StoreVisit.device_type)
    device_result = await db.execute(device_stmt)
    by_device = [{"device_type": row[0] or "Unknown", "count": row[1]} for row in device_result.fetchall()]

    # By browser
    browser_stmt = select(
        StoreVisit.browser, func.count(StoreVisit.id)
    ).where(base).group_by(StoreVisit.browser)
    browser_result = await db.execute(browser_stmt)
    by_browser = [{"browser": row[0] or "Unknown", "count": row[1]} for row in browser_result.fetchall()]

    return {
        "total_visits": total_visits,
        "unique_visitors": unique_visitors,
        "daily": daily,
        "by_device": by_device,
        "by_browser": by_browser,
    }


async def get_customer_growth_analytics(
    db: AsyncSession,
    start_date: datetime,
    end_date: datetime,
) -> dict:
    """Get customer growth analytics for a date range.

    Returns:
        new_customers: count of new registrations in period
        total_customers: total non-admin customers
        growth_pct: percentage growth vs previous equivalent period
        daily: list of {date, count}
    """
    from app.models.catalog import Role, Permission
    _admin_role_ids_subq = select(Role.id).where(
        Role.permissions.op('&')(Permission.ADMIN) > 0
    ).scalar_subquery()
    _non_admin = or_(
        User.role_id.is_(None),
        User.role_id.notin_(_admin_role_ids_subq),
    )

    base = and_(_non_admin, User.created_at >= start_date, User.created_at < end_date)

    # New customers in period
    new_result = await db.execute(
        select(func.count(User.id)).where(base)
    )
    new_customers = new_result.scalar_one() or 0

    # Total customers (all non-admin)
    total_result = await db.execute(
        select(func.count(User.id)).where(_non_admin)
    )
    total_customers = total_result.scalar_one() or 0

    # Previous period (same duration before start_date)
    period_duration = end_date - start_date
    prev_start = start_date - period_duration
    prev_end = start_date
    prev_base = and_(_non_admin, User.created_at >= prev_start, User.created_at < prev_end)
    prev_result = await db.execute(
        select(func.count(User.id)).where(prev_base)
    )
    prev_customers = prev_result.scalar_one() or 0

    # Growth percentage
    if prev_customers > 0:
        growth_pct = round(((new_customers - prev_customers) / prev_customers) * 100, 1)
    elif new_customers > 0:
        growth_pct = 100.0
    else:
        growth_pct = 0.0

    # Daily breakdown
    daily_stmt = select(
        func.date(User.created_at).label("day"),
        func.count(User.id).label("count"),
    ).where(base).group_by(func.date(User.created_at)).order_by(func.date(User.created_at))
    daily_result = await db.execute(daily_stmt)
    daily = [{"date": str(row.day), "count": row.count} for row in daily_result.fetchall()]

    return {
        "new_customers": new_customers,
        "total_customers": total_customers,
        "growth_pct": growth_pct,
        "daily": daily,
    }
