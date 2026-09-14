"""Generate the synthetic support-ticket training corpus.

Usage::

    python -m ml.generate_dataset --n 1400 --seed 42 --out data/tickets.csv

Design notes worth being able to defend:

**Non-uniform priors.** Categories are not sampled evenly, and urgency is
sampled *conditional on category*. Feature requests are almost never Critical;
login failures very often are. A uniform sample would be easier to fit and
would teach the model a prior that is wrong in production. The imbalance this
creates is then handled at training time with ``class_weight="balanced"``
rather than by resampling, so no synthetic rows are duplicated into the
validation split.

**Independent composition.** Category body and urgency phrase are drawn from
separate pools and joined. The urgency pool is deliberately topic-neutral, so
the urgency model cannot shortcut by reading the topic.

**Deduplication.** Slot collisions can produce identical strings. Exact
duplicates are dropped before writing, because a duplicate that lands on both
sides of the train/test split leaks the answer and inflates the reported score.
"""

from __future__ import annotations

import argparse
import csv
import random
import re
import sys
from pathlib import Path

# Allow `python ml/generate_dataset.py` as well as `python -m ml.generate_dataset`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ml.noise import add_noise  # noqa: E402
from ml.templates import (  # noqa: E402
    CATEGORY_TEMPLATES,
    CLOSERS,
    DETAILS,
    OPENERS,
    SLOTS,
    URGENCY_PHRASES,
)

# Share of the corpus per category. Roughly mirrors the mix a mid-size B2B SaaS
# support desk actually sees: technical noise and bugs dominate, feature
# requests are a long tail.
CATEGORY_PRIOR: dict[str, float] = {
    "Technical Issue": 0.22,
    "Bug Report": 0.20,
    "Billing": 0.18,
    "Login/Access": 0.16,
    "General Inquiry": 0.13,
    "Feature Request": 0.11,
}

# P(urgency | category). This is the part that makes the dataset feel real.
# Nobody files a Critical feature request; almost everybody locked out of their
# account thinks it is at least High.
URGENCY_PRIOR: dict[str, dict[str, float]] = {
    "Billing":          {"Critical": 0.08, "High": 0.27, "Medium": 0.42, "Low": 0.23},
    "Bug Report":       {"Critical": 0.18, "High": 0.34, "Medium": 0.34, "Low": 0.14},
    "Login/Access":     {"Critical": 0.26, "High": 0.38, "Medium": 0.26, "Low": 0.10},
    "Feature Request":  {"Critical": 0.01, "High": 0.07, "Medium": 0.34, "Low": 0.58},
    "General Inquiry":  {"Critical": 0.01, "High": 0.06, "Medium": 0.33, "Low": 0.60},
    "Technical Issue":  {"Critical": 0.22, "High": 0.36, "Medium": 0.29, "Low": 0.13},
}

_SLOT_RE = re.compile(r"\{(\w+)\}")


def fill_slots(template: str, rng: random.Random) -> str:
    """Replace every ``{slot}`` with an independently sampled filler.

    Each *occurrence* is sampled separately rather than once per slot name, so
    "we downgraded from {plan} to {plan}" yields two different plans. A repeat
    of the previous value for the same slot is rejected once, which is enough
    to avoid nonsense like "from Pro to Pro" without biasing the distribution
    in any way that matters.
    """
    last_seen: dict[str, str] = {}

    def _replace(match: re.Match[str]) -> str:
        name = match.group(1)
        options = SLOTS.get(name)
        if not options:
            return match.group(0)

        value = rng.choice(options)
        if value == last_seen.get(name) and len(options) > 1:
            value = rng.choice([o for o in options if o != value])

        last_seen[name] = value
        return value

    return _SLOT_RE.sub(_replace, template)


def weighted_choice(weights: dict[str, float], rng: random.Random) -> str:
    """Sample a key from ``weights`` proportionally to its value."""
    keys = list(weights)
    return rng.choices(keys, weights=[weights[k] for k in keys], k=1)[0]


def compose_ticket(category: str, urgency: str, rng: random.Random) -> str:
    """Assemble one ticket: opener + body + impact + detail + closer.

    The impact phrase is placed after the body about three quarters of the
    time and before it otherwise. Real reporters lead with severity roughly
    that often, and varying the position stops position itself becoming a
    feature of the bigram vectoriser.
    """
    body = fill_slots(rng.choice(CATEGORY_TEMPLATES[category]), rng)
    impact = fill_slots(rng.choice(URGENCY_PHRASES[urgency]), rng)

    if rng.random() < 0.75:
        core = f"{body.capitalize()}. {impact.capitalize()}."
    else:
        core = f"{impact.capitalize()}. {body.capitalize()}."

    parts: list[str] = []

    opener = rng.choice(OPENERS)
    if opener:
        parts.append(opener)

    parts.append(core)

    if rng.random() < 0.34:
        parts.append(fill_slots(rng.choice(DETAILS), rng))

    closer = rng.choice(CLOSERS)
    if closer:
        parts.append(closer)

    return " ".join(parts)


def generate(n: int, seed: int) -> list[dict[str, str]]:
    """Produce ``n`` unique labelled tickets."""
    rng = random.Random(seed)

    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    # Cap the attempts so an over-large `n` fails loudly instead of spinning
    # forever once the template space is exhausted.
    max_attempts = n * 40
    attempts = 0

    while len(rows) < n and attempts < max_attempts:
        attempts += 1

        category = weighted_choice(CATEGORY_PRIOR, rng)
        urgency = weighted_choice(URGENCY_PRIOR[category], rng)

        text = add_noise(compose_ticket(category, urgency, rng), rng)

        key = text.lower()
        if key in seen:
            continue

        seen.add(key)
        rows.append({"ticket_text": text, "category": category, "urgency": urgency})

    if len(rows) < n:
        raise RuntimeError(
            f"Could only generate {len(rows)} unique tickets out of {n} requested "
            f"after {attempts} attempts. Add more templates or slot values."
        )

    rng.shuffle(rows)
    return rows


def summarise(rows: list[dict[str, str]]) -> str:
    """Render a human-readable breakdown of the generated corpus."""
    from collections import Counter

    categories = Counter(r["category"] for r in rows)
    urgencies = Counter(r["urgency"] for r in rows)
    lengths = [len(r["ticket_text"].split()) for r in rows]

    lines = [f"Generated {len(rows)} unique tickets", "", "Category distribution:"]
    for name, count in categories.most_common():
        lines.append(f"  {name:<18} {count:>5}  ({count / len(rows):6.1%})")

    lines += ["", "Urgency distribution:"]
    for name, count in urgencies.most_common():
        lines.append(f"  {name:<18} {count:>5}  ({count / len(rows):6.1%})")

    lines += [
        "",
        f"Ticket length (words): min={min(lengths)} "
        f"mean={sum(lengths) / len(lengths):.1f} max={max(lengths)}",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic support tickets.")
    parser.add_argument("--n", type=int, default=1400, help="number of tickets")
    parser.add_argument("--seed", type=int, default=42, help="random seed")
    parser.add_argument(
        "--out", type=Path, default=Path("data/tickets.csv"), help="output CSV path"
    )
    args = parser.parse_args()

    rows = generate(args.n, args.seed)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["ticket_text", "category", "urgency"])
        writer.writeheader()
        writer.writerows(rows)

    print(summarise(rows))
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
