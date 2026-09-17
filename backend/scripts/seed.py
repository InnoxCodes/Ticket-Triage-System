"""Populate the database with a realistic demo history.

Usage::

    python -m scripts.seed              # 80 tickets over the last 14 days
    python -m scripts.seed --n 200 --days 30
    python -m scripts.seed --reset      # wipe first

An empty dashboard demos badly — the charts have nothing to draw and the
override-rate panel reads 0%. This backfills a plausible fortnight so every
view has something real in it on first load.

Three things are modelled rather than assigned at random:

* **Arrival pattern.** Tickets cluster into working hours on weekdays, so the
  volume chart has the weekly rhythm a support queue actually has instead of
  uniform noise.
* **Status by age.** Older tickets are mostly resolved, recent ones mostly
  open, so resolution-time metrics are computable and the Kanban columns are
  not all one length.
* **Overrides.** Agents correct the model more often when it was unsure. That
  correlation is the whole point of the reliability panel — seeding overrides
  uniformly would produce a chart that says confidence is meaningless.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import delete, func, select  # noqa: E402

from app.config import settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.models import Agent, Override, Ticket, TicketStatus  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.ml.predictor import warm_up  # noqa: E402
from app.ml.taxonomy import CATEGORIES, URGENCIES, Urgency  # noqa: E402
from app.services import ticket_service  # noqa: E402
from app.services.demo_data import make_ticket  # noqa: E402

# A second agent so the override log has more than one name in it.
EXTRA_AGENTS = [
    ("jordan.blake@triageai.dev", "Jordan Blake", "triage123"),
    ("riya.kapoor@triageai.dev", "Riya Kapoor", "triage123"),
]


def _arrival_time(rng: random.Random, days: int) -> datetime:
    """Pick a creation timestamp with a realistic weekly and daily shape."""
    now = datetime.now(UTC)

    for _ in range(20):
        offset_days = rng.uniform(0, days)
        candidate = now - timedelta(days=offset_days)

        # Weekends get roughly a fifth of weekday volume.
        if candidate.weekday() >= 5 and rng.random() > 0.2:
            continue

        # Business hours, with a bimodal peak mid-morning and mid-afternoon.
        hour = round(rng.choice([rng.gauss(10.5, 2.0), rng.gauss(15.0, 2.2)]))
        if not 6 <= hour <= 21:
            continue

        return candidate.replace(
            hour=hour, minute=rng.randrange(60), second=rng.randrange(60), microsecond=0
        )

    return now - timedelta(days=rng.uniform(0, days))


def _status_for_age(age_hours: float, urgency: str, rng: random.Random) -> str:
    """Older tickets skew resolved; severe ones get picked up faster."""
    # Critical tickets are worked immediately, so they clear sooner.
    speed = {Urgency.CRITICAL: 3.0, Urgency.HIGH: 1.8, Urgency.MEDIUM: 1.0}.get(urgency, 0.7)
    progress = min(1.0, (age_hours / 72) * speed)

    roll = rng.random()
    if roll < progress * 0.85:
        return TicketStatus.RESOLVED
    if roll < progress * 0.85 + 0.22:
        return TicketStatus.IN_PROGRESS
    return TicketStatus.OPEN


def _resolution_delay(urgency: str, rng: random.Random) -> timedelta:
    """Time from creation to resolution, log-normal and urgency-scaled.

    Log-normal because support resolution times are heavily right-skewed —
    most tickets close quickly and a few drag on for days. A uniform draw
    would make the mean and median identical and hide exactly the skew the
    analytics page is meant to expose.
    """
    median_hours = {
        Urgency.CRITICAL: 1.2, Urgency.HIGH: 5.0,
        Urgency.MEDIUM: 20.0, Urgency.LOW: 52.0,
    }.get(urgency, 24.0)

    hours = rng.lognormvariate(mu=0.0, sigma=0.85) * median_hours
    return timedelta(hours=max(0.15, hours))


async def _ensure_agents(session) -> list[Agent]:
    """Create the demo agents if absent and return all of them."""
    wanted = [
        (settings.seed_agent_email, settings.seed_agent_name, settings.seed_agent_password),
        *EXTRA_AGENTS,
    ]

    for email, name, password in wanted:
        exists = (
            await session.execute(select(Agent).where(Agent.email == email))
        ).scalar_one_or_none()
        if exists is None:
            session.add(Agent(email=email, name=name, password_hash=hash_password(password)))

    await session.commit()
    return list((await session.execute(select(Agent))).scalars().all())


def _plausible_correction(field: str, current: str, rng: random.Random) -> str:
    """Pick a correction a human would actually make.

    Urgency moves one step, because an agent nudging Critical to High is
    realistic and Critical to Low is not. Category moves to any other label.
    """
    if field == "urgency":
        index = URGENCIES.index(current)
        options = [
            URGENCIES[i] for i in (index - 1, index + 1) if 0 <= i < len(URGENCIES)
        ]
        return rng.choice(options) if options else current

    return rng.choice([c for c in CATEGORIES if c != current])


async def seed(count: int, days: int, reset: bool, seed_value: int | None) -> None:
    """Create ``count`` tickets spread over the last ``days`` days."""
    rng = random.Random(seed_value)

    await init_db()
    warm_up()

    async with SessionLocal() as session:
        if reset:
            await session.execute(delete(Override))
            await session.execute(delete(Ticket))
            await session.commit()
            print("cleared existing tickets and overrides")

        agents = await _ensure_agents(session)
        print(f"agents ready: {', '.join(a.email for a in agents)}")

        existing = int((await session.execute(select(func.count(Ticket.id)))).scalar_one())
        if existing and not reset:
            print(f"{existing} tickets already present; adding {count} more")

        timestamps = sorted(_arrival_time(rng, days) for _ in range(count))
        now = datetime.now(UTC)
        override_count = 0

        for index, created_at in enumerate(timestamps, start=1):
            subject, body, email = make_ticket(rng)

            ticket = await ticket_service.create_ticket(
                session,
                subject=subject,
                body=body,
                requester_email=email,
                created_at=created_at,
            )

            age_hours = (now - created_at).total_seconds() / 3600
            status = _status_for_age(age_hours, ticket.urgency, rng)

            if status == TicketStatus.RESOLVED:
                resolved_at = created_at + _resolution_delay(ticket.urgency, rng)
                if resolved_at > now:
                    # Would resolve in the future; leave it in progress rather
                    # than writing a timestamp that has not happened yet.
                    status = TicketStatus.IN_PROGRESS
                else:
                    ticket.resolved_at = resolved_at
                    ticket.updated_at = resolved_at

            ticket.status = status

            # Agents correct the model more often when it was unsure. The
            # probability is driven by the actual confidence so the seeded
            # data reproduces the relationship the reliability panel reports,
            # rather than inventing a flat rate.
            confidence = min(ticket.ai_category_confidence, ticket.ai_urgency_confidence)
            override_probability = 0.44 if confidence < 0.45 else 0.07

            if rng.random() < override_probability:
                field = "urgency" if rng.random() < 0.62 else "category"
                current = ticket.urgency if field == "urgency" else ticket.category
                corrected = _plausible_correction(field, current, rng)

                if corrected != current:
                    agent = rng.choice(agents)
                    session.add(
                        Override(
                            ticket_id=ticket.id,
                            agent_id=agent.id,
                            field=field,
                            from_value=current,
                            to_value=corrected,
                            model_confidence=(
                                ticket.ai_urgency_confidence
                                if field == "urgency"
                                else ticket.ai_category_confidence
                            ),
                            model_version=ticket.model_version,
                            created_at=created_at + timedelta(minutes=rng.uniform(2, 90)),
                        )
                    )
                    if field == "urgency":
                        ticket.urgency = corrected
                    else:
                        ticket.category = corrected
                    override_count += 1

            if index % 20 == 0:
                await session.commit()
                print(f"  seeded {index}/{count}")

        await session.commit()

        total = int((await session.execute(select(func.count(Ticket.id)))).scalar_one())
        resolved = int(
            (
                await session.execute(
                    select(func.count(Ticket.id)).where(Ticket.status == TicketStatus.RESOLVED)
                )
            ).scalar_one()
        )
        flagged = int(
            (
                await session.execute(
                    select(func.count(Ticket.id)).where(Ticket.ai_needs_review.is_(True))
                )
            ).scalar_one()
        )

    print(
        f"\ndone: {total} tickets total  |  {resolved} resolved  |  "
        f"{flagged} flagged for review  |  {override_count} overrides logged"
    )
    print(f"login: {settings.seed_agent_email} / {settings.seed_agent_password}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed TriageAI with demo tickets.")
    parser.add_argument("--n", type=int, default=80, help="number of tickets")
    parser.add_argument("--days", type=int, default=14, help="spread over this many days")
    parser.add_argument("--reset", action="store_true", help="delete existing tickets first")
    parser.add_argument("--seed", type=int, default=7, help="random seed")
    args = parser.parse_args()

    asyncio.run(seed(args.n, args.days, args.reset, args.seed))


if __name__ == "__main__":
    main()
