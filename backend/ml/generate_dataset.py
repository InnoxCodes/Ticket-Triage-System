"""Generate the synthetic support-ticket training corpus.

Usage::

    python -m ml.generate_dataset --n 1400 --seed 42 --out data/tickets.csv

The generator is built around one lesson learned the hard way: an earlier
version of this file produced a corpus both classifiers scored **100%** on,
because train and test shared the same small pool of sentence templates. That
is template-level leakage, and the score measured the generator rather than the
model. See the module docstring in ``templates.py`` for the full write-up.

Four mechanisms keep the task honest now:

1. **Severity lean.** Every category body is tagged with what it implies about
   urgency on its own. Urgency is sampled from the lean, so a ticket never
   pairs "I need a receipt copy" with "production is down".

2. **Implicit urgency.** A third of tickets state no impact at all, exactly as
   most real tickets arrive. Severity must then be inferred from the body,
   which is genuinely uncertain — this is the dominant source of irreducible
   error and the reason the urgency score is not, and should not be, ~100%.

3. **Reporter mis-statement.** Some people call a cosmetic bug critical and
   some shrug at an outage. A small share of tickets shift one level away from
   what the body implies.

4. **Annotator disagreement.** A few per cent of labels are moved to a
   neighbouring class, and only across pairs humans actually confuse. Every
   hand-labelled dataset has this; omitting it inflates the ceiling.

Two extra columns, ``urgency_stated`` and ``label_noise``, are written
alongside the three required fields. Training ignores them; they exist so the
evaluation step can slice accuracy by "did the reporter say how bad it was",
which turns a middling headline number into an explainable one.
"""

from __future__ import annotations

import argparse
import csv
import random
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ml.taxonomy import URGENCIES  # noqa: E402
from ml.noise import add_noise  # noqa: E402
from ml.templates import (  # noqa: E402
    CATEGORY_TEMPLATES,
    CLOSERS,
    CONNECTORS,
    DETAILS,
    HEDGE_PHRASES,
    OPENERS,
    SLOTS,
    URGENCY_FRAGMENTS,
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

# How often each category produces a body of each severity lean. This is what
# makes login lockouts skew urgent and feature requests skew relaxed, without
# hardcoding urgency per category.
LEAN_WEIGHTS: dict[str, dict[str, float]] = {
    "Billing":         {"severe": 0.14, "neutral": 0.56, "calm": 0.30},
    "Bug Report":      {"severe": 0.26, "neutral": 0.55, "calm": 0.19},
    "Login/Access":    {"severe": 0.42, "neutral": 0.45, "calm": 0.13},
    "Feature Request": {"severe": 0.05, "neutral": 0.38, "calm": 0.57},
    "General Inquiry": {"severe": 0.03, "neutral": 0.32, "calm": 0.65},
    "Technical Issue": {"severe": 0.34, "neutral": 0.55, "calm": 0.11},
}

# P(urgency | lean). Deliberately overlapping: a severe body is usually
# Critical or High but not always, which is what makes implicit-urgency
# tickets legitimately hard rather than artificially hard.
LEAN_URGENCY_PRIOR: dict[str, dict[str, float]] = {
    "severe":  {"Critical": 0.46, "High": 0.38, "Medium": 0.14, "Low": 0.02},
    "neutral": {"Critical": 0.06, "High": 0.26, "Medium": 0.48, "Low": 0.20},
    "calm":    {"Critical": 0.01, "High": 0.05, "Medium": 0.28, "Low": 0.66},
}

# Category pairs that a human triager genuinely mixes up. Label noise is only
# ever applied along these edges — randomly relabelling a billing ticket as a
# login problem would be noise no model should be expected to fit, and would
# just depress the score without teaching anything.
CONFUSABLE_CATEGORIES: dict[str, list[str]] = {
    "Bug Report": ["Technical Issue"],
    "Technical Issue": ["Bug Report"],
    "Feature Request": ["General Inquiry"],
    "General Inquiry": ["Feature Request", "Billing"],
    "Billing": ["General Inquiry"],
    "Login/Access": ["Technical Issue"],
}

# Share of tickets where the reporter never states impact.
IMPLICIT_URGENCY_RATE = 0.32

# Share where the stated urgency drifts one level from what the body implies.
MISSTATEMENT_RATE = 0.12

# Share of Medium/High tickets that get a deliberately borderline phrase.
HEDGE_RATE = 0.15

# Annotator disagreement rates.
CATEGORY_LABEL_NOISE = 0.035
URGENCY_LABEL_NOISE = 0.05

_SLOT_RE = re.compile(r"\{(\w+)\}")


def fill_slots(template: str, rng: random.Random) -> str:
    """Replace every ``{slot}`` with an independently sampled filler.

    Each *occurrence* is sampled separately rather than once per slot name, so
    "we downgraded from {plan} to {plan}" yields two different plans.
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


def shift_urgency(urgency: str, rng: random.Random) -> str:
    """Move one step up or down the severity scale, clamped at the ends."""
    index = URGENCIES.index(urgency)
    step = rng.choice([-1, 1])
    return URGENCIES[max(0, min(len(URGENCIES) - 1, index + step))]


def build_urgency_phrase(urgency: str, rng: random.Random) -> str:
    """Assemble an impact statement from interchangeable fragments.

    One to three fragments are drawn from the scope / consequence / demand
    groups and joined with a random connector. With ~10 options per group the
    phrase space runs to several thousand forms per urgency level, so a test
    ticket essentially never repeats a training phrase verbatim — which is the
    entire point.
    """
    if urgency in ("Medium", "High") and rng.random() < HEDGE_RATE:
        return rng.choice(HEDGE_PHRASES)

    groups = ["scope", "consequence", "demand"]
    fragments = URGENCY_FRAGMENTS[urgency]

    count = rng.choices([1, 2, 3], weights=[0.34, 0.46, 0.20], k=1)[0]
    chosen = rng.sample(groups, count)
    chosen.sort(key=groups.index)  # keep a natural reading order

    parts = [rng.choice(fragments[group]) for group in chosen]

    phrase = parts[0]
    for part in parts[1:]:
        phrase += rng.choice(CONNECTORS) + part
    return phrase


def compose_ticket(
    category: str, urgency: str, lean: str, *, state_urgency: bool, rng: random.Random
) -> str:
    """Assemble one ticket: opener + body + optional impact + detail + closer."""
    return compose_ticket_parts(category, urgency, lean, state_urgency=state_urgency, rng=rng)[1]


def compose_ticket_parts(
    category: str, urgency: str, lean: str, *, state_urgency: bool, rng: random.Random
) -> tuple[str, str]:
    """Assemble one ticket and also return its topical core, as ``(topic, text)``.

    The demo generator uses the clean topic as a subject line. The random
    draws happen in exactly the order they always have, so the corpus produced
    from a given seed is byte-for-byte unchanged.
    """
    body = fill_slots(rng.choice(CATEGORY_TEMPLATES[category][lean]), rng)

    if state_urgency:
        impact = fill_slots(build_urgency_phrase(urgency, rng), rng)
        # Reporters lead with severity roughly a quarter of the time. Varying
        # the position stops position itself becoming a bigram feature.
        if rng.random() < 0.75:
            core = f"{body.capitalize()}. {impact.capitalize()}."
        else:
            core = f"{impact.capitalize()}. {body.capitalize()}."
    else:
        core = f"{body.capitalize()}."

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

    return body, " ".join(parts)


def apply_label_noise(rows: list[dict[str, str]], rng: random.Random) -> None:
    """Relabel a small share of rows to a neighbouring class, in place.

    Simulates the disagreement present in any hand-labelled corpus. Only
    confusable category pairs and adjacent urgency levels are touched, so the
    injected error is the kind a human would plausibly make.
    """
    for row in rows:
        noised = False

        if rng.random() < CATEGORY_LABEL_NOISE:
            alternatives = CONFUSABLE_CATEGORIES.get(row["category"])
            if alternatives:
                row["category"] = rng.choice(alternatives)
                noised = True

        if rng.random() < URGENCY_LABEL_NOISE:
            row["urgency"] = shift_urgency(row["urgency"], rng)
            noised = True

        row["label_noise"] = "true" if noised else "false"


def generate(n: int, seed: int) -> list[dict[str, str]]:
    """Produce ``n`` unique labelled tickets."""
    rng = random.Random(seed)

    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    max_attempts = n * 40
    attempts = 0

    while len(rows) < n and attempts < max_attempts:
        attempts += 1

        category = weighted_choice(CATEGORY_PRIOR, rng)
        lean = weighted_choice(LEAN_WEIGHTS[category], rng)

        # A category may have no templates at a given lean (nobody files a
        # severe feature request often); fall back to the nearest one.
        if not CATEGORY_TEMPLATES[category][lean]:
            lean = "neutral"

        urgency = weighted_choice(LEAN_URGENCY_PRIOR[lean], rng)
        if rng.random() < MISSTATEMENT_RATE:
            urgency = shift_urgency(urgency, rng)

        state_urgency = rng.random() >= IMPLICIT_URGENCY_RATE

        text = add_noise(
            compose_ticket(category, urgency, lean, state_urgency=state_urgency, rng=rng),
            rng,
        )

        key = text.lower()
        if key in seen:
            continue

        seen.add(key)
        rows.append(
            {
                "ticket_text": text,
                "category": category,
                "urgency": urgency,
                "urgency_stated": "true" if state_urgency else "false",
                "label_noise": "false",
            }
        )

    if len(rows) < n:
        raise RuntimeError(
            f"Only generated {len(rows)} unique tickets out of {n} requested after "
            f"{attempts} attempts. Add more templates or slot values."
        )

    apply_label_noise(rows, rng)
    rng.shuffle(rows)
    return rows


def summarise(rows: list[dict[str, str]]) -> str:
    """Render a human-readable breakdown of the generated corpus."""
    total = len(rows)
    categories = Counter(r["category"] for r in rows)
    urgencies = Counter(r["urgency"] for r in rows)
    lengths = [len(r["ticket_text"].split()) for r in rows]
    stated = sum(r["urgency_stated"] == "true" for r in rows)
    noised = sum(r["label_noise"] == "true" for r in rows)
    unique_words = len({w for r in rows for w in r["ticket_text"].lower().split()})

    lines = [f"Generated {total} unique tickets", "", "Category distribution:"]
    for name, count in categories.most_common():
        lines.append(f"  {name:<18} {count:>5}  ({count / total:6.1%})")

    lines += ["", "Urgency distribution:"]
    for name in URGENCIES:
        count = urgencies[name]
        lines.append(f"  {name:<18} {count:>5}  ({count / total:6.1%})")

    lines += [
        "",
        f"Urgency explicitly stated : {stated:>5}  ({stated / total:6.1%})",
        f"Labels moved by annotator : {noised:>5}  ({noised / total:6.1%})",
        f"Vocabulary size           : {unique_words:>5} distinct tokens",
        f"Ticket length (words)     : min={min(lengths)} "
        f"mean={sum(lengths) / total:.1f} max={max(lengths)}",
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
        writer = csv.DictWriter(
            fh,
            fieldnames=["ticket_text", "category", "urgency", "urgency_stated", "label_noise"],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(summarise(rows))
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
