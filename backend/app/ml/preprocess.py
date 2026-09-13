"""Text normalisation for support tickets.

This runs identically at training time and at inference time. It lives under
``app/`` rather than under the training scripts precisely so that there is
exactly one copy of it: training/serving skew — where the model was fit on text
cleaned one way and is then asked to score text cleaned another way — is one of
the most common and most invisible ML bugs, and the only reliable fix is to
make it impossible to have two implementations.

The pipeline is deliberately shallow:

    raw text -> unicode normalise -> lowercase -> mask volatile entities
             -> strip punctuation -> drop stopwords -> collapse whitespace

No stemming, no lemmatisation. Both were tried and neither moved F1 by more
than noise on this dataset, and both cost interpretability: with raw tokens the
model's learned coefficients read as real words ("refund", "outage",
"whenever"), which is what makes the confidence breakdown in the UI defensible
to a human agent.
"""

from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------------------
# Stopwords
# ---------------------------------------------------------------------------
# This is a CUSTOM list, and that is the single most important decision in this
# file.
#
# scikit-learn ships `stop_words="english"`, and using it here actively
# destroys the urgency signal. That list strips "not", "no", "cannot", "can't",
# "never", "nothing", "against", "down", "off" and every modal verb. Consider
# what survives:
#
#     "I cannot log in at all and nothing works"   -> "log works"
#     "I can log in and everything works"          -> "log works"
#
# Two tickets with opposite meaning collapse onto an identical feature vector.
# The category classifier might survive that (both are Login/Access), but the
# urgency classifier is left guessing.
#
# So the list below removes only genuinely contentless function words —
# determiners, pronouns, prepositions, auxiliaries — and deliberately KEEPS:
#
#   * negations       not, no, never, cannot, can't, nothing, none
#   * severity words  down, off, out, immediately, urgent, asap, still
#   * modals          can, could, should, would, must, need
#   * time pressure   now, soon, today, already, again
#
# Those are exactly the tokens that separate Critical from Low.
STOPWORDS: frozenset[str] = frozenset(
    {
        # articles / determiners
        "a", "an", "the", "this", "that", "these", "those", "each", "every",
        "either", "such", "same", "own", "other", "another",
        # pronouns
        "i", "me", "my", "mine", "myself", "we", "us", "our", "ours",
        "ourselves", "you", "your", "yours", "yourself", "yourselves",
        "he", "him", "his", "himself", "she", "her", "hers", "herself",
        "it", "its", "itself", "they", "them", "their", "theirs",
        "themselves", "who", "whom", "whose", "which", "what", "whatever",
        # prepositions / conjunctions
        "of", "in", "on", "at", "by", "for", "with", "about", "into", "onto",
        "from", "to", "as", "and", "or", "but", "if", "then", "than", "so",
        "because", "while", "during", "before", "after", "between", "through",
        "over", "under", "above", "below", "upon", "within", "along", "across",
        # auxiliaries that carry no polarity
        "am", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "having", "do", "does", "did", "doing",
        "will", "shall",
        # low-content filler
        "there", "here", "when", "where", "why", "how", "all", "any", "both",
        "some", "few", "more", "most", "very", "just", "also", "well", "get",
        "got", "getting", "one", "two", "thing", "things", "way", "ways",
        "please", "thanks", "thank", "hi", "hello", "hey", "dear", "regards",
        "kindly", "sincerely", "team", "support",
    }
)

# ---------------------------------------------------------------------------
# Entity masking
# ---------------------------------------------------------------------------
# High-cardinality literals (order numbers, emails, amounts) are replaced with
# a single stable token rather than deleted. Two reasons:
#
#   1. Deleting them loses information. "charged $4,812.00" and "charged $9"
#      are both billing problems; the *presence* of a currency amount is a
#      useful feature, the exact value is not.
#   2. Keeping them raw poisons the vocabulary. Every invoice id would become
#      its own feature, appearing exactly once, contributing nothing but
#      dimensionality and a small overfitting risk.
_MASKS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"), " emailaddr "),
    (re.compile(r"https?://\S+|www\.\S+"), " urladdr "),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), " ipaddr "),
    (re.compile(r"[$£€]\s?\d[\d,]*(?:\.\d+)?"), " moneyamt "),
    (re.compile(r"\b(?:inv|ord|tkt|ref|txn)[-_# ]?\d{3,}\b", re.I), " refnum "),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}\b"), " datestr "),
    (re.compile(r"\b\d{1,2}:\d{2}\s?(?:am|pm)?\b", re.I), " timestr "),
    # A bare number long enough to be an identifier rather than a quantity.
    # "500" is kept (HTTP 500 is a real signal); "84720193" is masked.
    (re.compile(r"\b\d{6,}\b"), " longnum "),
]

# Contractions are expanded BEFORE punctuation is stripped, otherwise "can't"
# becomes the token "cant" and "won't" becomes "wont" — both of which then look
# nothing like the "not" that appears in the uncontracted phrasings. Normalising
# here means "can't log in" and "cannot log in" produce the same features.
#
# Split into two groups because they need different anchoring. Apostrophe
# suffixes attach mid-word ("can't" -> the "n't" sits after "ca"), so they must
# NOT require a leading word boundary. Bare spellings must require one on both
# sides, or "im" rewrites the inside of "immediately" and "ive" mangles "five".
# Longest-match-first ordering is what makes "can't" resolve to "cannot"
# instead of leaving the orphan stem "ca" behind from the generic "n't" rule.
_APOSTROPHE_FORMS: dict[str, str] = {
    "can't": "cannot", "won't": "will not", "shan't": "shall not",
    "n't": " not", "'re": " are", "'s": " is", "'d": " would",
    "'ll": " will", "'ve": " have", "'m": " am",
}

_BARE_FORMS: dict[str, str] = {
    "cant": "cannot", "wont": "will not", "didnt": "did not",
    "doesnt": "does not", "dont": "do not", "isnt": "is not",
    "wasnt": "was not", "arent": "are not", "werent": "were not",
    "couldnt": "could not", "shouldnt": "should not",
    "wouldnt": "would not", "havent": "have not", "hasnt": "has not",
    "hadnt": "had not", "aint": "is not", "im": "i am", "ive": "i have",
    # Normalise the most common severity slang into words the model already
    # sees in the uncontracted Critical phrasings.
    "asap": "urgent immediately",
}

_APOSTROPHE_RE = re.compile(
    "|".join(re.escape(k) for k in sorted(_APOSTROPHE_FORMS, key=len, reverse=True))
)
_BARE_RE = re.compile(
    r"\b(?:" + "|".join(sorted(_BARE_FORMS, key=len, reverse=True)) + r")\b"
)
_NON_WORD_RE = re.compile(r"[^a-z0-9\s]+")
_WHITESPACE_RE = re.compile(r"\s+")
_REPEATED_CHAR_RE = re.compile(r"(.)\1{2,}")


def expand_contractions(text: str) -> str:
    """Rewrite contracted forms so negation survives punctuation stripping."""
    text = _BARE_RE.sub(lambda m: _BARE_FORMS[m.group(0)], text)
    return _APOSTROPHE_RE.sub(lambda m: _APOSTROPHE_FORMS[m.group(0)], text)


def mask_entities(text: str) -> str:
    """Replace high-cardinality literals with stable placeholder tokens."""
    for pattern, token in _MASKS:
        text = pattern.sub(token, text)
    return text


def normalise_text(text: str) -> str:
    """Lowercase, strip accents, and squash typing artefacts.

    ``"URGENT!!! Cannot Lóg In!!!!"`` -> ``"urgent!! cannot log in!!"``

    Character runs are capped at two rather than one because "!!" and "??" are
    genuine emphasis signals that correlate with urgency, while "!!!!!!!!" is
    the same signal with noise attached.
    """
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    return _REPEATED_CHAR_RE.sub(r"\1\1", text)


def remove_stopwords(tokens: list[str]) -> list[str]:
    """Drop contentless function words, keeping negations and severity cues."""
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]


def preprocess(text: str) -> str:
    """Full cleaning pipeline: raw ticket text -> space-joined token string.

    Returns a string rather than a token list because that is what
    ``TfidfVectorizer`` consumes; it applies its own whitespace tokeniser on
    top, which is a no-op on already-cleaned text.
    """
    if not text:
        return ""

    # Order matters: mask before contraction expansion, so that the "'s" rule
    # cannot chew through a URL or an email local-part before it is masked.
    text = normalise_text(text)
    text = mask_entities(text)
    text = expand_contractions(text)
    text = _NON_WORD_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()

    return " ".join(remove_stopwords(text.split()))


def preprocess_batch(texts: list[str]) -> list[str]:
    """Vectorised convenience wrapper over :func:`preprocess`."""
    return [preprocess(t) for t in texts]
