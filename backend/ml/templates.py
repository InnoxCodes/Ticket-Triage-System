"""Template corpus used to synthesise the training set.

Why synthetic data at all? Real support archives are proprietary and full of
PII, and the public alternatives (20-newsgroups, generic "customer support"
scrapes) do not carry an *urgency* label at all. Generating the corpus means
the label definitions and the text are guaranteed to agree, and it makes the
whole pipeline reproducible from a seed with nothing to download.

The generator composes each ticket from independent parts:

    [opener] + [category body] + [urgency impact] + [detail] + [closer]

That composition is the important bit. The category signal lives in the body's
domain vocabulary ("invoice", "stack trace", "2FA"), while the urgency signal
lives in impact language ("production is down", "whenever you get a chance")
that is written to be **category-agnostic**. Because the two are sampled
independently, a model cannot cheat by inferring urgency from topic — it has
to learn the impact vocabulary on its own. That is exactly the behaviour we
want from a real triage system.

Two deliberate confusability choices, because a model that scores 99% on a toy
dataset tells an interviewer nothing:

  * Bug Report vs Technical Issue overlap on purpose. The split is "the
    product computed the wrong answer" vs "the infrastructure is slow or
    unreachable", which is a genuinely fuzzy line that human triagers also get
    wrong.
  * General Inquiry sits close to Feature Request, since "does it support X?"
    and "please add X" share most of their words.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Slot fillers
# ---------------------------------------------------------------------------
# Slots exist so the same sentence skeleton yields many surface forms. They
# also inject the high-cardinality literals (amounts, ids, endpoints) that the
# preprocessing entity-masking step is built to absorb.
SLOTS: dict[str, list[str]] = {
    "product_area": [
        "the dashboard", "the reports page", "the billing portal",
        "the mobile app", "the admin console", "the search bar",
        "the export tool", "the notifications panel", "the API console",
        "the settings page", "the user directory", "the audit log",
        "the integrations page", "the onboarding flow", "the webhook manager",
        "the analytics view", "the team management screen", "the invoice list",
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
    # Two distinct time slots. `duration` is a bare span that reads correctly
    # after "takes over ..." or "for about ..."; `since` is an onset phrase for
    # "this started ...". Collapsing them into one slot produces grammatical
    # nonsense like "this started three days".
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
# Category bodies
# ---------------------------------------------------------------------------
# Each entry is the topical core of a ticket. They avoid severity words almost
# entirely — severity is the urgency phrase's job. Where a body does imply some
# stakes ("we were charged twice"), the generator still samples urgency
# independently, so the model sees that body at every severity level.
CATEGORY_TEMPLATES: dict[str, list[str]] = {
    "Billing": [
        "we were charged {amount} twice this month on invoice {ref}",
        "my card was declined but the subscription still shows as active",
        "I need a copy of the receipt for {ref} for our finance team",
        "the invoice for {date} has the wrong VAT number on it",
        "we downgraded from {plan} to {plan} but were still billed the old rate",
        "can you explain the proration line item of {amount} on our last invoice",
        "our purchase order number is missing from every invoice you send",
        "I want to cancel the subscription and get a refund of {amount}",
        "we are being billed for {count} seats but only have {count} active users",
        "the payment method on file expired and I cannot update it in {product_area}",
        "we got charged {amount} after cancelling the {plan} plan last month",
        "please move our billing cycle from monthly to annual on the {plan} plan",
        "the credit note you issued for {ref} never appeared on our statement",
        "our finance team needs invoices sent to a different email address",
        "why did our bill jump from {amount} to {amount} with no plan change",
        "the refund for {ref} was approved {duration} ago but has not landed",
        "I was double charged when I retried a failed payment of {amount}",
        "we need consolidated billing across our {count} workspaces",
        "the tax rate applied to invoice {ref} looks wrong for our region",
        "can we switch the {plan} subscription to invoice-based payment terms",
        "the auto-renewal charged us {amount} without any advance notice",
        "our card on file keeps failing even though the bank confirms it is fine",
    ],
    "Bug Report": [
        "the total on {product_area} shows a different number than the export",
        "clicking save on {product_area} wipes the form and loses my input",
        "the date filter returns results outside the range I selected",
        "sorting by name in {product_area} puts uppercase entries in a random order",
        "the record count says {count} but only {count} rows actually render",
        "I get a blank white screen on {product_area} in {browser}",
        "the console throws a null reference error when I open {product_area}",
        "duplicate entries appear every time I refresh {product_area}",
        "the CSV export is missing the last column on every row",
        "editing a {role} and saving silently reverts the change",
        "the search bar ignores hyphens so no results come back for hyphenated names",
        "percentages on the summary card do not add up to 100",
        "the modal on {product_area} cannot be closed once it opens in {browser}",
        "pagination skips the first item on page two",
        "timestamps display in UTC on {product_area} but in local time everywhere else",
        "the undo button restores the wrong version of the record",
        "bulk selecting rows and applying an action only affects the first one",
        "the chart renders an empty axis when a series has zero values",
        "uploading a file over {count} MB fails silently with no error shown",
        "toggling a setting off in {product_area} turns it back on after a reload",
        "the form accepts an invalid email address and saves it without complaint",
        "archived records still show up in {product_area} by default",
        "a regression since the last release broke the filter on {product_area}",
    ],
    "Login/Access": [
        "I cannot log in, the password reset email never arrives",
        "my account is locked after a few failed attempts and will not unlock",
        "the two factor code from my authenticator is rejected every time",
        "SSO through {integration} redirects back to the login page in a loop",
        "the magic link expires before I can click it",
        "I was invited as a {role} but the invitation link says it is invalid",
        "my session expires after a couple of minutes and logs me out",
        "I get a 403 when opening {product_area} even though I am a {role}",
        "the SAML assertion is rejected with an audience mismatch",
        "I lost my phone and cannot get past the MFA prompt",
        "a {role} on our team cannot see {product_area} at all",
        "password reset says the account does not exist but I can receive your billing email",
        "we removed a user and now nobody can access {product_area}",
        "the login page rejects my correct password in {browser} but works in another browser",
        "our {count} new hires cannot accept their workspace invitations",
        "access to {product_area} disappeared after our plan changed to {plan}",
        "the account recovery flow keeps asking for a code it never sends",
        "I can log in on desktop but the mobile app rejects the same credentials",
        "role permissions reset to read-only for our whole team overnight",
        "the workspace owner left the company and we are locked out of settings",
        "enforcing MFA locked out every user who had not enrolled yet",
    ],
    "Feature Request": [
        "it would be really useful to have {feature} in {product_area}",
        "please consider adding {feature} to the roadmap",
        "any chance you could support {feature} for {plan} customers",
        "we would adopt this much faster if {feature} existed",
        "a small suggestion, {feature} would save our team a lot of clicks",
        "our team keeps asking for {feature}, is it planned",
        "could {product_area} support {feature} at some point",
        "we work around the lack of {feature} with a spreadsheet today",
        "adding {feature} would let us retire our internal tool",
        "it would be nice if {product_area} remembered my last filter",
        "we would like an API endpoint that mirrors {feature}",
        "please add {feature}, every competitor we evaluated has it",
        "is there a plan to bring {feature} to the {plan} tier",
        "a webhook for this event would let us build {feature} ourselves",
        "we need {feature} before we can roll this out to {count} people",
        "having {feature} would remove the last manual step in our process",
        "would you consider {feature} as a paid add-on",
        "an option to disable the default behaviour in {product_area} would help",
        "we would love to see {feature} integrated with {integration}",
        "could you expose {feature} through the {endpoint} endpoint",
    ],
    "General Inquiry": [
        "how do I invite a {role} to our workspace",
        "does the {plan} plan include {feature}",
        "where can I find documentation for {product_area}",
        "what is the difference between the {plan} and {plan} plans",
        "is there a guide for setting up {integration}",
        "who should I talk to about a renewal conversation",
        "what are your data retention policies for exported reports",
        "can you point me at the onboarding checklist for new teams",
        "does your API have a rate limit I should design around",
        "is {product_area} covered by your uptime commitment",
        "how long does it usually take for support to respond",
        "what is the recommended way to structure teams for {count} users",
        "do you offer training sessions for new {role} accounts",
        "is there a sandbox I can test against before going live",
        "can we get a copy of your security questionnaire responses",
        "what happens to our data if we cancel the {plan} plan",
        "is {feature} something that exists today or am I missing it",
        "which regions do you host data in",
        "how do I read the numbers shown on {product_area}",
        "are there best practices for organising {product_area} at scale",
    ],
    "Technical Issue": [
        "{product_area} takes over {duration} to load for everyone on our team",
        "the {endpoint} endpoint returns {error_code} intermittently",
        "our webhooks stopped being delivered {since}",
        "the {integration} sync has been failing with {error_code}",
        "API latency went from milliseconds to several seconds {since}",
        "we are hitting a rate limit of {count} requests and cannot complete a sync",
        "the SSL certificate on your API host looks like it is misconfigured",
        "requests from our {os} build fail with {error_code} but curl works fine",
        "the nightly export job has been timing out {since}",
        "connections to your service drop after about {duration}",
        "{product_area} is unreachable from our office network but fine on mobile data",
        "the {integration} integration disconnects itself every few hours",
        "your status page says everything is fine but we see {error_code} on {endpoint}",
        "bulk imports of {count} records stall halfway through with no error",
        "DNS resolution for your API endpoint fails from our region",
        "the websocket connection to {product_area} keeps dropping and reconnecting",
        "memory usage in our worker spikes whenever we call {endpoint}",
        "responses from {endpoint} have been returning truncated payloads",
        "the retry logic gets stuck in a loop because {endpoint} returns {error_code}",
        "throughput dropped by half {since} with no change on our side",
        "we see {error_code} errors in our logs for roughly {count} requests per minute",
    ],
}

# ---------------------------------------------------------------------------
# Urgency phrases
# ---------------------------------------------------------------------------
# Written to be topic-neutral: none of these mention invoices, logins or
# latency, so the urgency classifier is forced to learn impact vocabulary
# rather than piggy-backing on the category signal.
URGENCY_PHRASES: dict[str, list[str]] = {
    "Critical": [
        "this is completely blocking us and production is down",
        "our entire team is blocked and we are losing revenue every minute",
        "this is a total outage for all {count} of our users",
        "we need this fixed immediately, it is a severity one for us",
        "everything is broken and we cannot operate at all right now",
        "this is escalated internally and our customers are affected",
        "we have a board demo in under an hour and nothing works",
        "please treat this as urgent, we are dead in the water",
        "this has taken down our production environment",
        "our whole business is stopped until this is resolved",
        "this is an emergency, we cannot serve our own customers",
        "urgent, we are actively losing money while this is broken",
        "critical failure, every single user is affected right now",
        "we are in an active incident because of this",
        "our contract deliverable is at risk today because of this",
        "this needs someone on it right now, no workaround exists",
    ],
    "High": [
        "this is impacting several people on the team and we need it soon",
        "we have a deadline this week so a quick turnaround would help a lot",
        "this is a significant problem for us though we have a partial workaround",
        "please prioritise this, it is slowing down a lot of work",
        "a few of our {role} accounts are affected and it is getting worse",
        "we need a resolution in the next day or two",
        "this is becoming a real problem as more people hit it",
        "it is not a full outage but it is seriously disruptive",
        "we can limp along for now but this needs attention quickly",
        "this is blocking a launch we have scheduled shortly",
        "escalating this because it has been happening repeatedly",
        "our team lead flagged this as important to fix soon",
        "we are spending hours a day working around this",
        "this affects a meaningful part of our workflow every day",
        "we would really appreciate a fix before the end of the week",
    ],
    "Medium": [
        "it is annoying but we can work around it for now",
        "not blocking anything, just something we would like sorted",
        "when you have a chance, this would be good to look at",
        "it happens fairly often so it is worth fixing at some point",
        "we can live with it but it does slow us down a bit",
        "no major impact yet, flagging it before it becomes one",
        "a couple of people have mentioned it so I thought I would report it",
        "moderately inconvenient, nothing is on fire",
        "this has come up a few times now",
        "would be good to understand whether this is expected behaviour",
        "not urgent but it does affect our day to day",
        "happy to wait, just wanted it on your radar",
        "it is a recurring annoyance rather than a blocker",
        "hoping to get this resolved in the next couple of weeks",
    ],
    "Low": [
        "no rush at all, whenever you get a chance",
        "very low priority, just curious really",
        "purely a nice to have, please do not prioritise this",
        "not important, feel free to get to it whenever",
        "this is cosmetic and does not affect anything we do",
        "no hurry, just noting it down for the future",
        "completely optional from our side",
        "happy for this to sit at the bottom of the queue",
        "just a minor observation, nothing needs to change urgently",
        "for context only, no action needed soon",
        "asking out of interest rather than need",
        "whenever it fits into your roadmap is fine",
        "no deadline on this one at all",
        "minor thing, genuinely not a priority",
    ],
}

# ---------------------------------------------------------------------------
# Framing text
# ---------------------------------------------------------------------------
# Openers and closers add realistic boilerplate. Most of these words end up in
# the stopword list, which is the point: they teach the model to ignore the
# polite scaffolding that surrounds every real ticket.
OPENERS: list[str] = [
    "Hi team,", "Hello,", "Hi there,", "Good morning,", "Hey,",
    "Hi support,", "Dear support team,", "Hello support,",
    "", "", "", "",  # a good share of real tickets skip the greeting
]

CLOSERS: list[str] = [
    "Thanks in advance.", "Please advise.", "Let me know.",
    "Any help appreciated.", "Thanks!", "Looking forward to your reply.",
    "Happy to provide more detail if useful.", "Cheers.",
    "Let me know if you need screenshots.", "Thanks for your time.",
    "", "", "", "", "",
]

# Extra environment detail, appended to roughly a third of tickets. This is the
# kind of context a real reporter volunteers, and it adds vocabulary overlap
# between categories, which keeps the task honest.
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
]
