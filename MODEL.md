# TriageAI — Model Card

How the two classifiers behind TriageAI were built, what they score, and why
each decision was made. Everything here is reproducible from a clean clone:

```bash
cd backend
python -m ml.generate_dataset --n 1400 --seed 42
python -m ml.train
```

---

## 1. The problem

Two predictions from one piece of free text:

| Target | Type | Classes |
|---|---|---|
| **Category** | nominal | Billing · Bug Report · Login/Access · Feature Request · General Inquiry · Technical Issue |
| **Urgency** | ordinal | Critical · High · Medium · Low |

These are modelled as **two independent classifiers over the same text**, not
one 24-class product. A single joint model would have to learn every
category × urgency combination separately and would starve the rare cells —
`Feature Request × Critical` is about 0.1% of realistic traffic. Two focused
models each train on the full dataset and learn from completely different
vocabulary: one reads topic, the other reads impact.

---

## 2. The dataset, and the mistake that shaped it

Real support archives are proprietary and full of PII, and no public corpus
carries an urgency label. The dataset is therefore generated —
`backend/ml/generate_dataset.py`, 1,400 tickets, seed 42, committed to the repo
so results reproduce byte-for-byte.

### The first version scored 100%, and that was the useful finding

The initial generator drew each ticket from a fixed pool of ~20 category
sentences and ~15 urgency sentences. Both classifiers scored **1.000 accuracy**
on the held-out set.

That is a broken dataset, not a good model. Train and test were sampled from
the same small pool of skeletons, so every test ticket was a near-copy of
something already memorised — **template-level leakage**. The score measured
the generator.

Four changes fixed it, each mirroring something true about real inboxes:

| Change | What it does | Why it is realistic |
|---|---|---|
| **Compositional urgency** | Impact phrases are assembled from interchangeable scope / consequence / demand fragments rather than picked whole | Thousands of surface forms, so a test phrase is essentially never one seen verbatim |
| **Implicit urgency (32%)** | A third of tickets state no impact at all | Most real tickets do not say how bad it is; the agent infers it |
| **Reporter mis-statement (12%)** | Stated severity drifts one level from what the body implies | People over- and under-state their own emergencies |
| **Annotator disagreement (~5%)** | Labels moved to a neighbouring class, only across genuinely confusable pairs | Every hand-labelled dataset has this |

Category bodies are tagged with a **severity lean** (`severe` / `neutral` /
`calm`) so an implicit-urgency ticket still has a defensible label, and so the
generator never pairs "I need a receipt copy" with "production is down".

Scores moved from `1.000 / 1.000` to `0.946 / 0.732`. Those are numbers that
mean something.

### Composition

| Category | Share | | Urgency | Share |
|---|---|---|---|---|
| Technical Issue | 21.9% | | Medium | 31.0% |
| Bug Report | 21.2% | | Low | 28.5% |
| Billing | 17.5% | | High | 25.9% |
| Login/Access | 14.0% | | Critical | 14.6% |
| General Inquiry | 13.9% | | | |
| Feature Request | 11.5% | | | |

1,755 distinct tokens · mean 26.6 words per ticket · 67.5% state their impact
explicitly · 7.8% carry a moved label.

Class imbalance is deliberate and is handled at training time with
`class_weight="balanced"` rather than by resampling, so no synthetic row is
duplicated across the train/test boundary.

---

## 3. Preprocessing

`backend/app/ml/preprocess.py`, applied identically at train and serve time.

```
raw text → unicode normalise → lowercase → mask volatile entities
        → expand contractions → strip punctuation → drop stopwords
```

It lives under `app/` rather than beside the training scripts specifically so
there is exactly one copy. Training/serving skew — a model fitted on text
cleaned one way, then asked to score text cleaned another — is invisible when
it happens and is best made structurally impossible.

### The custom stopword list is the most important decision here

scikit-learn's `stop_words="english"` **destroys the urgency signal.** It
strips `not`, `no`, `cannot`, `never`, `nothing`, `down`, `off` and every
modal verb. Consider what survives:

```
"I cannot log in at all and nothing works"   →  "log works"
"I can log in and everything works"          →  "log works"
```

Two tickets with opposite meaning collapse onto an identical feature vector.
The category model might survive that; the urgency model is left guessing.

The custom list removes only genuinely contentless function words and
deliberately keeps negations, severity words (`down`, `urgent`, `still`),
modals, and time pressure (`now`, `already`, `again`) — exactly the tokens
that separate Critical from Low.

### Entity masking

High-cardinality literals are replaced, not deleted: `$4,812.00` → `moneyamt`,
`INV-99213` → `refnum`, `ops@acme.io` → `emailaddr`. Deleting them loses the
signal that a currency amount was mentioned at all; keeping them raw gives
every invoice id its own single-occurrence feature, which is pure
dimensionality. `500` is deliberately **not** masked — HTTP status codes are
real signal.

### What was deliberately left out

No stemming, no lemmatisation. Both were tried; neither moved F1 beyond noise,
and both cost interpretability. With raw tokens the learned coefficients read
as real words, which is what makes the explanation panel in the UI defensible.

---

## 4. Model selection

Four candidate families, 5-fold stratified cross-validation on the training
split only. The held-out set was never touched during selection.

### Category

| Model | CV accuracy | CV macro F1 | Fit time |
|---|---|---|---|
| Majority baseline | 0.2188 | 0.0598 | 0.13s |
| Multinomial NB | 0.8955 | 0.8910 | 0.11s |
| **Linear SVM** | **0.9491** | **0.9484** | 0.10s |
| Logistic Regression | 0.9375 | 0.9370 | 0.12s |

### Urgency

| Model | CV accuracy | CV macro F1 | Fit time |
|---|---|---|---|
| Majority baseline | 0.3098 | 0.1183 | 0.09s |
| Multinomial NB | 0.7214 | 0.7108 | 0.09s |
| Linear SVM | 0.7268 | 0.7190 | 0.14s |
| **Logistic Regression** | **0.7366** | **0.7309** | 0.15s |

### Why logistic regression, when the SVM wins on category

The linear SVM is 1.2 points better on category macro F1 and 1.2 points worse
on urgency. Logistic regression is used for both anyway, for two product
reasons that outweigh a point of F1:

1. **Calibrated probabilities.** The UI shows a per-class confidence
   breakdown and the system auto-routes above a confidence threshold. Both
   need `predict_proba`. `LinearSVC` exposes only unbounded decision-function
   margins; converting those needs a `CalibratedClassifierCV` wrapper, which
   adds an inner cross-validation loop and a second layer between the
   coefficients and the output.

2. **Direct interpretability.** The score for a class is exactly
   `bias + Σ tfidf(term) × coefficient(term, class)`, so every term's
   contribution to *this specific ticket* is a signed number readable straight
   off the model. That is what powers the "flagged Critical because of
   'losing revenue' and 'production'" panel. Wrapping the model in a
   calibrator breaks that direct path.

Consistency also matters: two models with the same shape are easier to reason
about, monitor and retrain than a heterogeneous pair.

### Why not a transformer

| | TF-IDF + LogReg | Fine-tuned BERT |
|---|---|---|
| Training data needed | ~1k rows is fine | 10k+ for a reliable gain |
| Train time | **~4 seconds**, CPU | minutes–hours, GPU preferred |
| Inference | **~4 ms**, no GPU | 50–200 ms CPU |
| Artifact size | **300 KB** | 400+ MB |
| Per-prediction explanation | **built in** | needs SHAP / integrated gradients |
| Expected lift here | — | a few points at most on 1,400 rows |

The bottleneck in this dataset is not model capacity — it is that a third of
tickets contain no urgency evidence at all. No amount of parameters recovers
information that was never written down. A transformer would cost three orders
of magnitude more inference time and all of the interpretability to chase a
gain the data cannot supply.

### Hyperparameters

Grid-searched on **macro F1**, not accuracy. Accuracy is dominated by the
majority class and would happily reward a model that quietly gave up on
Critical tickets while nailing Medium ones — precisely backwards for triage.

| | Category | Urgency |
|---|---|---|
| `ngram_range` | (1, 2) | (1, 2) |
| `min_df` | 1 | 2 |
| `C` | 4.0 | 0.5 |
| Best CV macro F1 | 0.9420 | 0.7348 |

Bigrams matter most for urgency, where meaning lives in phrases — `not urgent`,
`no rush`, `production down` — whose unigrams are ambiguous or actively
misleading. The lower `C` on urgency is the search correctly asking for more
regularisation on the noisier, less separable target.

---

## 5. Results

Held-out set: 280 tickets, never seen during training or selection.

### Category — accuracy 0.9464 · macro F1 0.9500 · baseline 0.2179

| Label | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Billing | 0.942 | 1.000 | 0.970 | 49 |
| Bug Report | 0.915 | 0.915 | 0.915 | 59 |
| Login/Access | 1.000 | 1.000 | 1.000 | 39 |
| Feature Request | 1.000 | 0.909 | 0.952 | 33 |
| General Inquiry | 0.947 | 0.923 | 0.935 | 39 |
| Technical Issue | 0.919 | 0.934 | 0.927 | 61 |

```
                  Billing   Bug  Login    FR    GI    TI
  Billing              49     0      0     0     0     0
  Bug Report            0    54      0     0     0     5
  Login/Access          0     0     39     0     0     0
  Feature Request       0     1      0    30     2     0
  General Inquiry       3     0      0     0    36     0
  Technical Issue       0     4      0     0     0    57
```

**Every error is a designed-in confusion.** 9 of 15 are Bug Report ↔ Technical
Issue — the "wrong answer" vs "slow or unreachable" line that human triagers
also blur. The rest are General Inquiry ↔ Billing and Feature Request ↔
General Inquiry. There is not a single Billing→Login-style error, which is
what you want: the model's mistakes are the ones a person would make.

On the 260 test tickets whose labels were **not** touched by simulated
annotator disagreement, accuracy is **0.9846** — so nearly all remaining error
is the injected label noise, exactly as intended.

### Urgency — accuracy 0.7321 · macro F1 0.7275 · baseline 0.3107

| Label | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Critical | 0.682 | 0.732 | 0.706 | 41 |
| High | 0.662 | 0.653 | 0.657 | 72 |
| Medium | 0.721 | 0.713 | 0.717 | 87 |
| Low | 0.835 | 0.825 | 0.830 | 80 |

```
              Critical  High  Medium   Low
  Critical          30     9       0     2
  High               7    47      16     2
  Medium             6    10      62     9
  Low                1     5       8    66
```

0.7321 looks unimpressive on its own. It is the average of two very different
populations, and splitting them is the whole story:

| Slice | n | Accuracy |
|---|---|---|
| **Reporter stated their impact** | 185 | **0.9081** |
| **Impact left implicit** | 95 | 0.3895 |
| Labels free of annotator noise | 260 | 0.7538 |
| **Within one severity level** | 280 | **0.9429** |

When the ticket contains evidence, the model is right 91% of the time. When it
does not, it falls back to something near the prior — which is the *correct*
behaviour, not a failure. The information simply is not in the text.

The 0.9429 within-one-level figure matters because urgency is ordinal: a
Critical ticket scored High still lands near the top of the queue. Only 16 of
280 predictions were off by more than one level, and only 4 of those were in
the expensive direction — a genuinely severe ticket scored as less severe than
it was. `class_weight="balanced"` is what keeps that number low: over-flagging
a quiet ticket is cheap, missing a real emergency is not.

This decomposition points at the actual fix, and it is not a bigger model:
**ask reporters for impact at submission time.** That is a form-design change
worth ~50 points of accuracy on a third of the traffic.

### Selective prediction — the operating point

A triage system does not have to answer every ticket. It has to answer the
ones it is sure about and escalate the rest.

**Urgency**

| Threshold | Coverage | Accuracy on covered | Accuracy on escalated |
|---|---|---|---|
| 0.35 | 80.7% | 0.827 | 0.333 |
| 0.40 | 64.3% | 0.889 | 0.450 |
| **0.45** | **53.2%** | **0.933** | 0.504 |
| 0.50 | 40.7% | 0.930 | 0.596 |
| 0.60 | 22.9% | 0.922 | 0.676 |

**Category**

| Threshold | Coverage | Accuracy on covered |
|---|---|---|
| 0.45 | 93.2% | 0.958 |
| **0.55** | **87.5%** | **0.959** |
| 0.70 | 60.4% | 0.953 |

Shipped thresholds are **0.55 category / 0.45 urgency**. At that operating
point the system auto-routes 88% of category decisions at 96% accuracy and
53% of urgency decisions at 93%, and badges everything else for human review
in the UI. Choosing the point is a cost decision, not a modelling one — the
curve is what makes it a decision at all rather than a guess.

**A smarter-sounding rule that the data rejected.** On fresh, unseen tickets
the flat 0.45 cutoff escalates ~66% of tickets (the test split understates
this), so I tried escalating only when the model cannot tell *urgent*
(Critical/High) from *not urgent* — on the theory that Medium-vs-Low confusion
is harmless. Measured on the test split, combined with the category rule:

| Rule | Escalated | Urgent/not-urgent errors caught |
|---|---|---|
| flat urgency < 0.40 | 45.7% | 78.6% |
| **flat urgency < 0.45** | **56.1%** | **88.1%** |
| P(urgent) in 0.35–0.65 | 54.3% | 76.2% |
| P(urgent) in 0.30–0.70 | 69.3% | 88.1% |

The band rule escalates as much or more and catches fewer of the expensive
mistakes, so the flat threshold stays. The high review share is handled in the
UI instead: low-confidence predictions get a quiet dashed badge and a
"needs review" filter, not an alarm on every card.

---

## 6. What the models actually learned

Top coefficients per class, read directly off the fitted models:

| Class | Strongest terms |
|---|---|
| Billing | `moneyamt` +4.20 · `invoice` +3.05 · `payment` +2.96 · `subscription` +2.69 |
| Bug Report | `rows` +2.35 · `export` +2.14 · `form` +1.87 · `console` +1.78 |
| Login/Access | `login` +2.68 · `account` +2.60 · `access` +2.56 · `expires` +2.34 |
| Feature Request | `would` +4.39 · `could` +3.18 · `mode` +2.23 · `point` +2.14 |
| Technical Issue | `requests` +2.41 · `v2` +2.26 · `hours` +2.15 · `api` +2.04 |
| Critical | `incident` +1.03 · `need` +1.01 · `failing` +0.82 · `environment` +0.69 |
| Low | `else` +1.39 · `purely` +1.17 · `nothing` +1.00 · `not blocked` +0.88 |

Two things worth noticing. The entity mask `moneyamt` being Billing's single
strongest feature validates the masking decision — the *presence* of a currency
amount is highly predictive while the value is not. And the modal verbs
`would` / `could` dominating Feature Request confirms that keeping modals out
of the stopword list was correct; sklearn's default list would have deleted
both.

Urgency coefficients are much smaller in magnitude than category ones (≈1.0 vs
≈4.2). The model is genuinely less certain about urgency, and the numbers say
so honestly.

---

## 7. Honest limitations

- **Synthetic data.** Generated from templates, so it cannot contain the
  phrasings nobody thought to write. Real traffic would shift the vocabulary
  and the priors. The mitigations above make the task hard, not real.
- **English only**, and no multi-intent handling — a ticket that is both a
  billing dispute and a bug gets one label.
- **No temporal validation.** A production system should split by time, not
  at random, to catch vocabulary drift.
- **Static thresholds.** 0.55 / 0.45 were read off one held-out set. They
  should be re-tuned against real override rates.
- **The override log is the real evaluation.** Agent disagreement, captured on
  every correction and surfaced as "AI reliability" in the dashboard, is
  ground truth from actual users. That signal should drive retraining, and
  matters more than any number on this page.

## 8. What I would do next

1. **Change the submission form before touching the model** — one "what is the
   impact?" field addresses the 39% slice directly and is worth more than any
   architecture change.
2. **Retrain on override data** once enough corrections accumulate; they are
   real labels from real users.
3. **Add an abstain path end to end**, routing low-confidence tickets to a
   dedicated triage queue rather than just badging them.
4. **Calibration curve and Brier score** — confidence is used as a routing
   decision, so it deserves measurement as a probability, not just as a rank.
5. **Time-based validation split** once real tickets exist.
