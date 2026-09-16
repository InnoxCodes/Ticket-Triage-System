"""Aggregate statistics for the analytics dashboard.

Everything here is computed in SQL rather than by loading rows and counting
in Python. With a few hundred tickets either approach is instant; the SQL
version is the one that still works at a hundred thousand, and writing it now
costs nothing.

The override metrics are the interesting part. Offline accuracy is a snapshot
of how the model did against a test set it was tuned against. The override
rate is how often real agents disagree with it on real traffic, and it keeps
updating after deployment — it is the closest thing this system has to
production ground truth.
"""

from __future__ import annotations

import statistics
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Override, Ticket, TicketStatus
from app.ml.predictor import ModelNotTrainedError, get_model
from app.ml.taxonomy import CATEGORIES, SLA_MINUTES, STATUSES, URGENCIES, Urgency


async def _count_by(session: AsyncSession, column, ordering: list[str]) -> list[dict[str, Any]]:
    """GROUP BY one column, returned in canonical label order with zeros kept.

    Labels with no tickets are included with a count of zero. Dropping them
    would make chart colours and legend positions shift as data arrives,
    which reads as a rendering bug.
    """
    rows = await session.execute(select(column, func.count()).group_by(column))
    counts = dict(rows.all())
    return [{"label": label, "count": counts.get(label, 0)} for label in ordering]


async def _volume_over_time(session: AsyncSession, days: int) -> list[dict[str, Any]]:
    """Daily ticket counts split by urgency, with empty days filled in.

    ``func.date`` works on both SQLite and Postgres. Gaps are backfilled in
    Python because a line chart that simply omits quiet days draws a
    misleading slope between the points either side.
    """
    since = datetime.now(UTC) - timedelta(days=days - 1)
    day = func.date(Ticket.created_at)

    rows = await session.execute(
        select(
            day.label("day"),
            func.count().label("total"),
            func.sum(case((Ticket.urgency == Urgency.CRITICAL, 1), else_=0)).label("critical"),
            func.sum(case((Ticket.urgency == Urgency.HIGH, 1), else_=0)).label("high"),
            func.sum(case((Ticket.urgency == Urgency.MEDIUM, 1), else_=0)).label("medium"),
            func.sum(case((Ticket.urgency == Urgency.LOW, 1), else_=0)).label("low"),
        )
        .where(Ticket.created_at >= since)
        .group_by(day)
        .order_by(day)
    )

    by_day = {
        str(row.day): {
            "date": str(row.day),
            "total": int(row.total or 0),
            "critical": int(row.critical or 0),
            "high": int(row.high or 0),
            "medium": int(row.medium or 0),
            "low": int(row.low or 0),
        }
        for row in rows.all()
    }

    today = datetime.now(UTC).date()
    series: list[dict[str, Any]] = []
    for offset in range(days - 1, -1, -1):
        key = str(today - timedelta(days=offset))
        series.append(
            by_day.get(
                key,
                {"date": key, "total": 0, "critical": 0, "high": 0, "medium": 0, "low": 0},
            )
        )
    return series


async def _resolution_times(session: AsyncSession) -> tuple[float | None, float | None]:
    """Mean and median minutes from creation to resolution.

    Both are reported because they answer different questions. Support
    workloads are heavily right-skewed — one ticket left open over a weekend
    drags the mean into uselessness — so the median is what a team should
    actually watch, and showing only the mean would flatter or panic depending
    on the week.
    """
    rows = await session.execute(
        select(Ticket.created_at, Ticket.resolved_at).where(Ticket.resolved_at.is_not(None))
    )

    durations: list[float] = []
    for created_at, resolved_at in rows.all():
        if created_at is None or resolved_at is None:
            continue
        created = created_at if created_at.tzinfo else created_at.replace(tzinfo=UTC)
        resolved = resolved_at if resolved_at.tzinfo else resolved_at.replace(tzinfo=UTC)
        durations.append((resolved - created).total_seconds() / 60)

    if not durations:
        return None, None
    return round(statistics.fmean(durations), 1), round(statistics.median(durations), 1)


async def _sla_breaches(session: AsyncSession) -> int:
    """Tickets past their urgency's target response time.

    Built as a single CASE over the urgency-to-minutes policy so the check
    runs in the database. Pulling every ticket back to evaluate this in
    Python would be the obvious implementation and the one that stops working
    first.
    """
    now = datetime.now(UTC)
    deadline_minutes = case(
        dict(SLA_MINUTES),
        value=Ticket.urgency,
        else_=24 * 60,
    )

    # julianday() is SQLite's date arithmetic; the difference is in days, so
    # x1440 converts to minutes. Postgres would use EXTRACT(EPOCH FROM ...).
    elapsed_minutes = (func.julianday(func.coalesce(Ticket.resolved_at, now))
                       - func.julianday(Ticket.created_at)) * 1440

    result = await session.execute(
        select(func.count()).where(elapsed_minutes > deadline_minutes)
    )
    return int(result.scalar_one())


async def _override_stats(session: AsyncSession) -> dict[str, Any]:
    """How often agents disagree with the model, and on what."""
    total = int((await session.execute(select(func.count(Ticket.id)))).scalar_one())

    disagrees = (Ticket.category != Ticket.ai_category) | (
        Ticket.urgency != Ticket.ai_urgency
    )
    overridden = int(
        (await session.execute(select(func.count(Ticket.id)).where(disagrees))).scalar_one()
    )

    by_field_rows = await session.execute(
        select(Override.field, func.count()).group_by(Override.field)
    )
    by_field_counts = dict(by_field_rows.all())

    # Mean model confidence on overridden predictions vs accepted ones. If
    # agents are correcting low-confidence calls, the confidence score is
    # doing its job and the review threshold is set about right. If the two
    # numbers are equal, confidence carries no information about correctness
    # and the whole selective-routing design is unsupported.
    confidence_when_overridden = (
        await session.execute(select(func.avg(Override.model_confidence)))
    ).scalar()

    accepted_confidence = (
        await session.execute(
            select(func.avg((Ticket.ai_category_confidence + Ticket.ai_urgency_confidence) / 2))
            .where(~disagrees)
        )
    ).scalar()

    low_confidence_overrides = int(
        (
            await session.execute(
                select(func.count()).where(Override.model_confidence < 0.5)
            )
        ).scalar_one()
    )
    total_overrides = sum(by_field_counts.values())

    recent_rows = await session.execute(
        select(Override, Ticket.reference)
        .join(Ticket, Override.ticket_id == Ticket.id)
        .order_by(Override.created_at.desc())
        .limit(8)
    )
    recent = [
        {
            "reference": reference,
            "field": override.field,
            "from_value": override.from_value,
            "to_value": override.to_value,
            "model_confidence": round(override.model_confidence, 4),
            "created_at": (
                override.created_at
                if override.created_at.tzinfo
                else override.created_at.replace(tzinfo=UTC)
            ).isoformat(),
        }
        for override, reference in recent_rows.all()
    ]

    return {
        "total_tickets": total,
        "overridden_tickets": overridden,
        "override_rate": round(overridden / total, 4) if total else 0.0,
        "category_overrides": by_field_counts.get("category", 0),
        "urgency_overrides": by_field_counts.get("urgency", 0),
        "low_confidence_share": (
            round(low_confidence_overrides / total_overrides, 4) if total_overrides else 0.0
        ),
        "avg_confidence_when_overridden": round(float(confidence_when_overridden or 0), 4),
        "avg_confidence_when_accepted": round(float(accepted_confidence or 0), 4),
        "by_field": [
            {"label": field, "count": count} for field, count in sorted(by_field_counts.items())
        ],
        "recent": recent,
    }


async def summary(session: AsyncSession, *, days: int = 14) -> dict[str, Any]:
    """The single payload behind the whole analytics page."""
    status_counts = {
        label: int(
            (
                await session.execute(
                    select(func.count(Ticket.id)).where(Ticket.status == label)
                )
            ).scalar_one()
        )
        for label in STATUSES
    }

    total = int((await session.execute(select(func.count(Ticket.id)))).scalar_one())

    needs_review = int(
        (
            await session.execute(
                select(func.count(Ticket.id)).where(Ticket.ai_needs_review.is_(True))
            )
        ).scalar_one()
    )

    critical_open = int(
        (
            await session.execute(
                select(func.count(Ticket.id)).where(
                    Ticket.urgency == Urgency.CRITICAL,
                    Ticket.status != TicketStatus.RESOLVED,
                )
            )
        ).scalar_one()
    )

    avg_inference = (
        await session.execute(select(func.avg(Ticket.inference_ms)))
    ).scalar()

    avg_resolution, median_resolution = await _resolution_times(session)

    return {
        "total_tickets": total,
        "open_tickets": status_counts.get(TicketStatus.OPEN, 0),
        "in_progress_tickets": status_counts.get(TicketStatus.IN_PROGRESS, 0),
        "resolved_tickets": status_counts.get(TicketStatus.RESOLVED, 0),
        "needs_review_tickets": needs_review,
        "critical_open": critical_open,
        "sla_breached": await _sla_breaches(session),
        "avg_resolution_minutes": avg_resolution,
        "median_resolution_minutes": median_resolution,
        "avg_inference_ms": round(float(avg_inference or 0), 3),
        "volume_over_time": await _volume_over_time(session, days),
        "by_category": await _count_by(session, Ticket.category, CATEGORIES),
        "by_urgency": await _count_by(session, Ticket.urgency, URGENCIES),
        "by_status": await _count_by(session, Ticket.status, STATUSES),
        "overrides": await _override_stats(session),
    }


def model_performance() -> dict[str, Any]:
    """Offline evaluation from the last training run.

    Read straight from the artifact the training script wrote, so the figure
    the dashboard shows is provably the figure the model scored — there is no
    second, hand-maintained copy to drift.
    """
    try:
        metrics = get_model().metrics()
    except ModelNotTrainedError:
        return {}

    return {
        "generated_at": metrics.get("generated_at", "unknown"),
        "dataset": metrics.get("dataset", {}),
        "environment": metrics.get("environment", {}),
        "category": metrics.get("models", {}).get("category", {}),
        "urgency": metrics.get("models", {}).get("urgency", {}),
    }
