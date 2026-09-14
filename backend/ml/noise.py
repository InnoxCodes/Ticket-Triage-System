"""Noise injection for synthetic tickets.

Without this step the generated corpus is far too clean. Every ticket in a
category would share near-identical spelling, TF-IDF would find a handful of
perfectly separating keywords, and the model would report ~99% accuracy that
evaporates the moment a real person types "cant lgoin". Reported accuracy would
be measuring the generator, not the classifier.

The corruptions below are modelled on how people actually type in a hurry:

  * keyboard-adjacent substitutions ("billing" -> "bulling"), not random letters
  * transpositions, the single most common real typo ("the" -> "teh")
  * dropped and doubled characters
  * casing drift — all-lowercase messages, or a SHOUTED word
  * missing terminal punctuation and run-on sentences
  * the occasional dropped or repeated short word

Everything is driven by an injected ``random.Random`` so a given seed always
reproduces the same dataset.
"""

from __future__ import annotations

import random

# QWERTY neighbours. Substituting one of these is what makes a typo look like a
# slip of the finger rather than line noise, which matters because TF-IDF with
# character n-grams would otherwise learn to spot the implausible ones.
_KEYBOARD_NEIGHBOURS: dict[str, str] = {
    "a": "qwsz", "b": "vghn", "c": "xdfv", "d": "serfcx", "e": "wsdr",
    "f": "drtgvc", "g": "ftyhbv", "h": "gyujnb", "i": "ujko", "j": "huikmn",
    "k": "jiolm", "l": "kop", "m": "njk", "n": "bhjm", "o": "iklp",
    "p": "ol", "q": "wa", "r": "edft", "s": "awedxz", "t": "rfgy",
    "u": "yhji", "v": "cfgb", "w": "qase", "x": "zsdc", "y": "tghu",
    "z": "asx",
}

# Words that must never be corrupted. These carry the urgency signal, and
# mangling them would inject label noise rather than input noise — the ticket
# would still be labelled Critical while the evidence for it was destroyed.
_PROTECTED: frozenset[str] = frozenset(
    {
        "not", "no", "never", "cannot", "nothing", "none",
        "urgent", "urgently", "immediately", "critical", "emergency",
        "asap", "down", "blocked", "blocking", "outage", "broken",
        "rush", "priority", "prioritise", "prioritize",
    }
)


def _substitute(word: str, rng: random.Random) -> str:
    """Replace one character with a QWERTY neighbour."""
    i = rng.randrange(len(word))
    neighbours = _KEYBOARD_NEIGHBOURS.get(word[i].lower())
    if not neighbours:
        return word
    return word[:i] + rng.choice(neighbours) + word[i + 1 :]


def _transpose(word: str, rng: random.Random) -> str:
    """Swap two adjacent characters — the most common real-world typo."""
    if len(word) < 3:
        return word
    i = rng.randrange(len(word) - 1)
    return word[:i] + word[i + 1] + word[i] + word[i + 2 :]


def _delete(word: str, rng: random.Random) -> str:
    """Drop a single character."""
    if len(word) < 4:
        return word
    i = rng.randrange(len(word))
    return word[:i] + word[i + 1 :]


def _duplicate(word: str, rng: random.Random) -> str:
    """Hold a key slightly too long."""
    i = rng.randrange(len(word))
    return word[: i + 1] + word[i] + word[i + 1 :]


_TYPO_OPS = (_substitute, _transpose, _delete, _duplicate)


def corrupt_word(word: str, rng: random.Random) -> str:
    """Apply one random typo operation to ``word``."""
    if len(word) < 3 or word.lower() in _PROTECTED or not word.isalpha():
        return word
    return rng.choice(_TYPO_OPS)(word, rng)


def inject_typos(text: str, rng: random.Random, rate: float) -> str:
    """Corrupt approximately ``rate`` of the words in ``text``."""
    words = text.split()
    return " ".join(corrupt_word(w, rng) if rng.random() < rate else w for w in words)


def apply_casing(text: str, rng: random.Random) -> str:
    """Reproduce how casing actually varies across a support inbox."""
    roll = rng.random()

    if roll < 0.22:
        # Typed entirely in lowercase — very common from mobile.
        return text.lower()

    if roll < 0.28:
        # One word SHOUTED for emphasis. Correlates loosely with urgency in
        # real inboxes, and the preprocessing step lowercases it away, so it
        # tests that normalisation is actually happening.
        words = text.split()
        if words:
            i = rng.randrange(len(words))
            words[i] = words[i].upper()
        return " ".join(words)

    return text


def degrade_punctuation(text: str, rng: random.Random) -> str:
    """Drop terminal punctuation or pile on emphasis."""
    roll = rng.random()

    if roll < 0.18:
        # Sentence-ending punctuation simply omitted.
        return text.replace(". ", " ").rstrip(".")

    if roll < 0.26:
        # Emphatic repetition. Capped by the preprocessor's repeated-character
        # rule, which this exercises.
        return text.rstrip(".") + rng.choice(["!!", "!!!", "?!", "!!!!"])

    if roll < 0.31:
        return text.replace(",", "")

    return text


def perturb_words(text: str, rng: random.Random) -> str:
    """Occasionally drop or repeat a short word, as happens when editing."""
    words = text.split()
    if len(words) < 6:
        return text

    roll = rng.random()

    if roll < 0.07:
        candidates = [i for i, w in enumerate(words) if len(w) <= 3]
        if candidates:
            del words[rng.choice(candidates)]

    elif roll < 0.12:
        # Only repeat a bare word. Duplicating one that carries terminal
        # punctuation produces "soon. soon." which reads as a rendering bug
        # rather than a typing slip.
        candidates = [i for i, w in enumerate(words) if w.isalpha()]
        if candidates:
            i = rng.choice(candidates)
            words.insert(i, words[i])

    return " ".join(words)


def add_noise(text: str, rng: random.Random, typo_rate: float = 0.06) -> str:
    """Run the full corruption chain over one ticket.

    ``typo_rate`` is applied to only a subset of tickets so the corpus keeps a
    realistic mix of carefully written and hastily typed messages.
    """
    if rng.random() < 0.38:
        text = inject_typos(text, rng, typo_rate)

    text = perturb_words(text, rng)
    text = degrade_punctuation(text, rng)
    text = apply_casing(text, rng)

    return " ".join(text.split())
