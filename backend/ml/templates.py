"""Template corpus used to synthesise the training set.

Why synthetic data at all? Real support archives are proprietary and full of
PII, and the public alternatives (20-newsgroups, generic "customer support"
scrapes) carry no *urgency* label. Generating the corpus means the label
definitions and the text are guaranteed to agree, and the whole pipeline
reproduces from a seed with nothing to download.

-------------------------------------------------------------------------
A note on the first version of this file, because the fix is the interesting
part
-------------------------------------------------------------------------
The initial design drew each ticket from a fixed pool of ~20 category
sentences and ~15 urgency sentences. Both classifiers scored **100%** on the
held-out set.

That is a broken dataset, not a good model. Because train and test are sampled
from the same small pool of skeletons, every test sentence is a near-copy of
something the model already memorised — template-level leakage. The score was
measuring the generator.

Three changes fix it, and each mirrors something true about real inboxes:

1. **Compositional urgency.** Impact language is assembled from interchangeable
   scope / consequence / demand fragments rather than picked whole, so the
   surface forms number in the thousands and a test phrase is essentially never
   one seen verbatim in training.

2. **Implicit urgency.** Roughly a third of tickets state no severity at all —
   which is how most real tickets arrive. Severity then has to be inferred from
   what the body implies ("we are all locked out" vs "where are the docs"), and
   that inference is legitimately uncertain. This is the single largest source
   of irreducible error, and it is the honest kind.

3. **Annotator disagreement.** A small share of tickets carry a neighbouring
   label, applied only across genuinely confusable pairs (Bug Report vs
   Technical Issue, adjacent urgency levels). Every hand-labelled support
   dataset has this; pretending otherwise inflates the ceiling.

Templates are grouped by *severity lean* — what the body alone implies about
urgency — so that an implicit-urgency ticket still has a defensible label.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Slot fillers
# ---------------------------------------------------------------------------
SLOTS: dict[str, list[str]] = {
    "product_area": [
        "the dashboard", "the reports page", "the billing portal",
        "the mobile app", "the admin console", "the search bar",
        "the export tool", "the notifications panel", "the API console",
        "the settings page", "the user directory", "the audit log",
        "the integrations page", "the onboarding flow", "the webhook manager",
        "the analytics view", "the team management screen", "the invoice list",
        "the project timeline", "the permissions matrix",
    ],
    "plan": [
        "Starter", "Pro", "Business", "Enterprise", "Team", "Growth",
        "Scale", "Free",
    ],
    "browser": [
        "Chrome 131", "Firefox 133", "Safari 18", "Edge 131",
        "Chrome on Android", "Safari on iOS 18", "Brave", "Chrome incognito",
    ],
    "os": [
        "macOS 15.2", "Windows 11", "Ubuntu 24.04", "iOS 18.1",
        "Android 15", "Windows 10", "Debian 12",
    ],
    "endpoint": [
        "/v2/orders", "/v1/users", "/v2/invoices", "/api/webhooks",
        "/v2/search", "/v1/exports", "/v2/events", "/v1/subscriptions",
        "/v2/reports/generate", "/api/auth/token",
    ],
    "error_code": [
        "500", "502", "503", "429", "403", "404", "504",
        "ERR_CONNECTION_RESET", "TIMEOUT_EXCEEDED", "ECONNREFUSED",
    ],
    "feature": [
        "dark mode", "bulk CSV export", "Slack notifications",
        "SSO with Okta", "a native mobile app", "custom dashboards",
        "role-based permissions", "scheduled reports", "an audit trail",
        "multi-currency support", "keyboard shortcuts", "an offline mode",
        "Jira integration", "two-way calendar sync", "webhook retries",
        "saved filters", "a bulk edit action", "PDF export",
        "granular notification settings", "a sandbox environment",
    ],
    "amount": [
        "$49", "$129.00", "$1,204.50", "$18,300", "$79", "$4,812.00",
        "$240", "$9.99", "£320", "€1,450.00",
    ],
    "count": ["3", "12", "40", "200", "1,800", "7", "25", "60", "500"],
    "duration": [
        "20 minutes", "two hours", "three days", "about an hour",
        "45 seconds", "ten minutes", "a few hours",
    ],
    "since": [
        "since yesterday", "all week", "since the last release",
        "since Tuesday", "for the last 48 hours", "since this morning",
        "for about three days", "ever since the weekend",
    ],
    "role": [
        "admin", "manager", "read-only user", "billing contact",
        "workspace owner", "guest collaborator",
    ],
    "ref": [
        "INV-99213", "ORD-44812", "TKT-10233", "REF-77120", "TXN-3391082",
        "INV-20415", "ORD-88190",
    ],
    "date": [
        "2026-08-14", "2026-09-01", "2026-07-29", "2026-08-30", "2026-09-09",
    ],
    "integration": [
        "Salesforce", "HubSpot", "Stripe", "Zapier", "QuickBooks",
        "Segment", "Snowflake", "Shopify", "NetSuite",
    ],
}

# ---------------------------------------------------------------------------
# Category bodies, grouped by severity lean
# ---------------------------------------------------------------------------
# "lean" is what the body alone implies about urgency, before any explicit
# statement of impact:
#
#   severe   — something is broken or blocked right now
#   neutral  — a real problem, no stated stakes
#   calm     — a question, a preference, a nice-to-have
#
# The lean drives the label for implicit-urgency tickets. It also keeps the
# explicit ones coherent: sampling urgency from a blend of lean and category
# prior avoids generating "I need a receipt copy. Production is down."
CATEGORY_TEMPLATES: dict[str, dict[str, list[str]]] = {
    "Billing": {
        "severe": [
            "we were charged {amount} twice this month on invoice {ref}",
            "our account was suspended for non payment even though the invoice is paid",
            "a failed payment has locked our whole workspace out of {product_area}",
            "we were billed {amount} for seats we cancelled and the card has already been debited",
            "the auto-renewal took {amount} out of our account without any notice",
            "our {plan} subscription was cancelled by mistake and service has stopped",
            "we have been double charged on every invoice since {date}",
        ],
        "neutral": [
            "my card was declined but the subscription still shows as active",
            "we downgraded from {plan} to {plan} but were still billed the old rate",
            "can you explain the proration line item of {amount} on our last invoice",
            "our purchase order number is missing from every invoice you send",
            "we are being billed for {count} seats but only have {count} active users",
            "the payment method on file expired and I cannot update it in {product_area}",
            "the credit note you issued for {ref} never appeared on our statement",
            "why did our bill jump from {amount} to {amount} with no plan change",
            "the refund for {ref} was approved {since} but has not landed",
            "I was double charged when I retried a failed payment of {amount}",
            "the tax rate applied to invoice {ref} looks wrong for our region",
            "our card on file keeps failing even though the bank confirms it is fine",
            "the invoice for {date} has the wrong VAT number on it",
            "I want to cancel the subscription and get a refund of {amount}",
        ],
        "calm": [
            "I need a copy of the receipt for {ref} for our finance team",
            "please move our billing cycle from monthly to annual on the {plan} plan",
            "our finance team needs invoices sent to a different email address",
            "we need consolidated billing across our {count} workspaces",
            "can we switch the {plan} subscription to invoice-based payment terms",
            "could you add our company registration number to future invoices",
            "I would like to update the billing address on our account",
            "can you send a statement of all charges since {date}",
        ],
    },
    "Bug Report": {
        "severe": [
            "clicking save on {product_area} wipes the form and loses my input",
            "the record count says {count} but only {count} rows actually render",
            "I get a blank white screen on {product_area} in {browser}",
            "submitting the form deletes the existing record instead of updating it",
            "the bulk action applied itself to every record rather than the selected ones",
            "data entered yesterday has disappeared from {product_area} entirely",
            "the export contains another customer's rows mixed into ours",
            "editing a {role} and saving silently reverts the change",
        ],
        "neutral": [
            "the total on {product_area} shows a different number than the export",
            "the date filter returns results outside the range I selected",
            "the console throws a null reference error when I open {product_area}",
            "duplicate entries appear every time I refresh {product_area}",
            "the CSV export is missing the last column on every row",
            "the search bar ignores hyphens so no results come back for hyphenated names",
            "percentages on the summary card do not add up to 100",
            "the modal on {product_area} cannot be closed once it opens in {browser}",
            "pagination skips the first item on page two",
            "the undo button restores the wrong version of the record",
            "bulk selecting rows and applying an action only affects the first one",
            "uploading a file over {count} MB fails silently with no error shown",
            "toggling a setting off in {product_area} turns it back on after a reload",
            "a regression since the last release broke the filter on {product_area}",
            "the form accepts an invalid email address and saves it without complaint",
        ],
        "calm": [
            "sorting by name in {product_area} puts uppercase entries in a random order",
            "timestamps display in UTC on {product_area} but in local time everywhere else",
            "the chart renders an empty axis when a series has zero values",
            "archived records still show up in {product_area} by default",
            "a tooltip on {product_area} has a typo in it",
            "the column widths on {product_area} reset every time I navigate away",
            "the loading spinner keeps spinning briefly after content has rendered",
        ],
    },
    "Login/Access": {
        "severe": [
            "I cannot log in, the password reset email never arrives",
            "my account is locked after a few failed attempts and will not unlock",
            "SSO through {integration} redirects back to the login page in a loop",
            "we removed a user and now nobody can access {product_area}",
            "our {count} new hires cannot accept their workspace invitations",
            "enforcing MFA locked out every user who had not enrolled yet",
            "the workspace owner left the company and we are locked out of settings",
            "role permissions reset to read-only for our whole team overnight",
            "the two factor code from my authenticator is rejected every time",
            "access to {product_area} disappeared after our plan changed to {plan}",
        ],
        "neutral": [
            "the magic link expires before I can click it",
            "I was invited as a {role} but the invitation link says it is invalid",
            "my session expires after a couple of minutes and logs me out",
            "I get a 403 when opening {product_area} even though I am a {role}",
            "the SAML assertion is rejected with an audience mismatch",
            "I lost my phone and cannot get past the MFA prompt",
            "a {role} on our team cannot see {product_area} at all",
            "password reset says the account does not exist but I receive your billing email",
            "the login page rejects my correct password in {browser} but works elsewhere",
            "the account recovery flow keeps asking for a code it never sends",
            "I can log in on desktop but the mobile app rejects the same credentials",
        ],
        "calm": [
            "I would like to add a second {role} to our account",
            "can we extend the session timeout for our {plan} workspace",
            "how do I rotate the API key on my account",
            "I want to switch my login email to a different address",
            "we would like to review which accounts still have admin rights",
        ],
    },
    "Feature Request": {
        "severe": [
            "we need {feature} before we can roll this out to {count} people",
            "without {feature} we cannot complete the migration we have committed to",
            "our contract renewal depends on {feature} being available",
        ],
        "neutral": [
            "we would adopt this much faster if {feature} existed",
            "our team keeps asking for {feature}, is it planned",
            "we work around the lack of {feature} with a spreadsheet today",
            "adding {feature} would let us retire our internal tool",
            "we would like an API endpoint that mirrors {feature}",
            "please add {feature}, every competitor we evaluated has it",
            "is there a plan to bring {feature} to the {plan} tier",
            "a webhook for this event would let us build {feature} ourselves",
            "having {feature} would remove the last manual step in our process",
            "could you expose {feature} through the {endpoint} endpoint",
        ],
        "calm": [
            "it would be really useful to have {feature} in {product_area}",
            "please consider adding {feature} to the roadmap",
            "any chance you could support {feature} for {plan} customers",
            "a small suggestion, {feature} would save our team a lot of clicks",
            "could {product_area} support {feature} at some point",
            "it would be nice if {product_area} remembered my last filter",
            "would you consider {feature} as a paid add-on",
            "an option to disable the default behaviour in {product_area} would help",
            "we would love to see {feature} integrated with {integration}",
            "a dark colour scheme for {product_area} would be easier on the eyes",
        ],
    },
    "General Inquiry": {
        "severe": [
            "we have a security review today and need your compliance documentation now",
            "our auditor is asking where our data is stored and we have to answer today",
        ],
        "neutral": [
            "does your API have a rate limit I should design around",
            "what happens to our data if we cancel the {plan} plan",
            "can we get a copy of your security questionnaire responses",
            "what are your data retention policies for exported reports",
            "is {product_area} covered by your uptime commitment",
            "which regions do you host data in",
            "who should I talk to about a renewal conversation",
            "what is the recommended way to structure teams for {count} users",
        ],
        "calm": [
            "how do I invite a {role} to our workspace",
            "does the {plan} plan include {feature}",
            "where can I find documentation for {product_area}",
            "what is the difference between the {plan} and {plan} plans",
            "is there a guide for setting up {integration}",
            "can you point me at the onboarding checklist for new teams",
            "how long does it usually take for support to respond",
            "do you offer training sessions for new {role} accounts",
            "is there a sandbox I can test against before going live",
            "is {feature} something that exists today or am I missing it",
            "how do I read the numbers shown on {product_area}",
            "are there best practices for organising {product_area} at scale",
        ],
    },
    "Technical Issue": {
        "severe": [
            "the {endpoint} endpoint returns {error_code} intermittently",
            "our webhooks stopped being delivered {since}",
            "the {integration} sync has been failing with {error_code}",
            "{product_area} is unreachable from our office network but fine on mobile data",
            "DNS resolution for your API endpoint fails from our region",
            "the SSL certificate on your API host looks like it is misconfigured",
            "every request to {endpoint} has returned {error_code} {since}",
            "the nightly export job has been timing out {since}",
        ],
        "neutral": [
            "{product_area} takes over {duration} to load for everyone on our team",
            "API latency went from milliseconds to several seconds {since}",
            "we are hitting a rate limit of {count} requests and cannot complete a sync",
            "requests from our {os} build fail with {error_code} but curl works fine",
            "connections to your service drop after about {duration}",
            "the {integration} integration disconnects itself every few hours",
            "your status page says everything is fine but we see {error_code} on {endpoint}",
            "bulk imports of {count} records stall halfway through with no error",
            "the websocket connection to {product_area} keeps dropping and reconnecting",
            "responses from {endpoint} have been returning truncated payloads",
            "the retry logic gets stuck in a loop because {endpoint} returns {error_code}",
            "throughput dropped by half {since} with no change on our side",
            "we see {error_code} errors in our logs for roughly {count} requests per minute",
        ],
        "calm": [
            "memory usage in our worker spikes whenever we call {endpoint}",
            "response times on {endpoint} are slightly slower than documented",
            "we occasionally see a retry warning in the logs, is that expected",
            "the API returns results in a different order between calls",
            "could you confirm the recommended timeout setting for {endpoint}",
        ],
    },
}

# ---------------------------------------------------------------------------
# Compositional urgency fragments
# ---------------------------------------------------------------------------
# Assembled rather than picked whole. Three slots — who/what is affected, what
# it costs, what the reporter wants — combine into thousands of surface forms,
# which is what stops the classifier recognising phrases verbatim from
# training. Every fragment is topic-neutral, so urgency cannot be read off the
# category.
URGENCY_FRAGMENTS: dict[str, dict[str, list[str]]] = {
    "Critical": {
        "scope": [
            "every single user is affected",
            "the entire company is blocked",
            "all {count} of our users are down",
            "nobody on the team can work at all",
            "our production environment is completely down",
            "this affects every customer we have",
            "our whole workflow has stopped dead",
            "all of our services depending on this are failing",
            "this has taken out our live environment",
            "not one person here can get anything done",
        ],
        "consequence": [
            "we are losing revenue by the minute",
            "our own customers are already complaining",
            "we are in breach of our SLA as of this morning",
            "this is costing us money every hour it continues",
            "our launch today is at risk",
            "we have an active incident open on our side",
            "our executives are asking for updates every few minutes",
            "we have had to pause operations entirely",
            "we are fielding angry calls because of this",
        ],
        "demand": [
            "we need someone on this immediately",
            "please escalate this right now",
            "this absolutely cannot wait",
            "we need an emergency fix today",
            "please treat this as a severity one incident",
            "we need a call as soon as humanly possible",
            "there is no workaround available to us at all",
            "this is urgent in the strongest sense of the word",
        ],
    },
    "High": {
        "scope": [
            "several people on the team are affected",
            "a good portion of our users hit this daily",
            "most of our {role} accounts are running into it",
            "it affects a large part of our daily workflow",
            "about {count} people have reported it internally",
            "it is spreading to more of the team as we onboard",
            "a whole department is working around this",
        ],
        "consequence": [
            "it is costing us hours every day",
            "we are falling behind on a deadline because of it",
            "our release this week is at risk",
            "we have had to build a manual workaround to cope",
            "it is getting noticeably worse week on week",
            "it is eating into time we do not have",
            "our project timeline has already slipped once",
        ],
        "demand": [
            "we would really appreciate a fix within a day or two",
            "please prioritise this above the rest of our queue",
            "we need this sorted before the end of the week",
            "flagging this as important on our side",
            "hoping for a quick turnaround if at all possible",
            "we would like an update today if you can manage it",
            "our team lead has asked me to chase this",
        ],
    },
    "Medium": {
        "scope": [
            "a couple of people have noticed it",
            "it affects one part of our workflow",
            "it shows up every now and then",
            "only a handful of us run into it",
            "it comes up maybe once a day",
        ],
        "consequence": [
            "we can work around it for now",
            "it slows us down a little",
            "nothing is actually blocked because of it",
            "we have a manual fallback that works",
            "it is more of an irritation than a problem",
            "we lose a few minutes here and there",
        ],
        "demand": [
            "worth looking at when you get a chance",
            "no particular deadline from our side",
            "would be good to have this fixed eventually",
            "just putting it on your radar",
            "happy to wait for the next release",
            "sometime in the next few weeks would be fine",
        ],
    },
    "Low": {
        "scope": [
            "it does not really affect anything we do",
            "only I have noticed it so far",
            "it is purely cosmetic",
            "nobody else has even mentioned it",
            "it is a single screen and nothing else",
        ],
        "consequence": [
            "nothing depends on this at all",
            "we are not blocked in any way",
            "this has zero impact on our work",
            "everything else works perfectly well",
            "it changes nothing about how we use the product",
        ],
        "demand": [
            "absolutely no rush on this",
            "please put it at the very bottom of the queue",
            "whenever you happen to get to it is fine",
            "genuinely not a priority for us",
            "just noting it for the record",
            "no response needed really",
            "purely for your awareness",
        ],
    },
}

# Phrases that genuinely sit between two adjacent levels. Sprinkled into both
# Medium and High so the boundary between them is blurred on purpose — a real
# triage queue has plenty of tickets two reasonable people would grade
# differently, and a model reporting clean separation there is lying.
HEDGE_PHRASES: list[str] = [
    "it is becoming a bit of a problem",
    "this is more disruptive than it probably sounds",
    "we would like this looked at reasonably soon",
    "it is affecting a few people here",
    "not critical but certainly not trivial either",
    "this keeps coming up and we are tired of it",
    "somewhere in the middle of your queue would be fair",
    "it matters to us but we are not on fire",
    "moderately important from where we sit",
]

# Connectors used to join fragments into one sentence.
CONNECTORS: list[str] = [
    " and ", " and ", " - ", ", ", ", so ", ". ", " which means ",
]

# ---------------------------------------------------------------------------
# Framing text
# ---------------------------------------------------------------------------
OPENERS: list[str] = [
    "Hi team,", "Hello,", "Hi there,", "Good morning,", "Hey,",
    "Hi support,", "Dear support team,", "Hello support,",
    "Morning,", "Hi folks,",
    "", "", "", "", "",  # plenty of real tickets skip the greeting
]

CLOSERS: list[str] = [
    "Thanks in advance.", "Please advise.", "Let me know.",
    "Any help appreciated.", "Thanks!", "Looking forward to your reply.",
    "Happy to provide more detail if useful.", "Cheers.",
    "Let me know if you need screenshots.", "Thanks for your time.",
    "Appreciate the help.", "Get back to me when you can.",
    "", "", "", "", "", "",
]

DETAILS: list[str] = [
    "I am on {browser} running {os}.",
    "This started {since}.",
    "We are on the {plan} plan.",
    "Reproduced by {count} different people here.",
    "Our workspace has about {count} users.",
    "I have already tried clearing the cache and reinstalling.",
    "Reference {ref} if that helps.",
    "It happens on {browser} as well.",
    "Screenshots attached.",
    "I checked the documentation first and could not find anything.",
    "Tried again {duration} later with the same result.",
    "Our developer confirmed the same behaviour on {os}.",
    "Ticket raised on behalf of our {role}.",
    "Logged from our {plan} workspace.",
]
