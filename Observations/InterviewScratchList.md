# Interview Scratch List — Stakeholder Interviews (Stage 1)

Source: `Reference/05_Datasets/Stakeholder_Interviews.docx`
Feeds: Stage 1 Discovery Workbook, Section 1 (interviews, disagreements, what nobody said)

---

## 1. Claims that can be checked against the ticket data

| # | Claim | Who | Field(s) to check | Result |
|---|---|---|---|---|
| C1 | FCR is 42% (benchmark 65%) | Marcus | `history.first_contact_resolution` | |
| C2 | 500+ tickets per week | Marcus | `received_at` date range ÷ count | |
| C3 | ~70% are repeat questions an agent has already answered | Sofia | `labels.intent` concentration (top-N share) | |
| C4 | Common topics: password lockouts, rate limits, invoice increases, deployment rollbacks | Sofia / Marcus | `labels.intent` distribution | |
| C5 | ~Half of escalations were resolvable at tier one | Daniel | `history.escalated` = true AND (`labels.answerable_from_docs` = true OR `labels.expected_route` = auto_respond) | |
| C6 | Non-fluent tickets have the worst CSAT | Sofia | `csat_rating`, `repeat_contact`, FCR split by `language_fluency` | |
| C7 | Mondays are the worst day | Sofia | weekday of `received_at` | |
| C8 | Escalations cost ~4x and anger customers more than waiting | Marcus | `resolution_time_minutes`, `csat_rating` — escalated vs not | |
| C9 | KB covers what support answers repeatedly | Ines | `labels.answerable_from_docs` rate; `expected_doc_ids` coverage per intent | |
| C10 | KB articles are accurate within the review cycle | Ines | `documentation.json` → `last_reviewed_days_ago` | |
| C11 | Customer finds the answer in docs ~half the time | Ravi | compare with `answerable_from_docs` rate (Dataset Guide says ~75%) | |
| C12 | Enterprise customers get answers in ~1 hour | Ravi | `resolution_time_minutes` by `customer_tier` | |
| C13 | Urgent and trivial tickets wait the same (one queue) | Ravi | `resolution_time_minutes` by `labels.urgency` | |
| C14 | Re-asking customers on escalation drives frustration | Daniel | `repeat_contact` and `csat_rating` on escalated tickets | |

---

## 2. Places where two people contradict each other

| # | Disagreement | Who says what | How the data settles it | Result |
|---|---|---|---|---|
| D1 | What escalations are | Marcus reads escalation rate as tier two doing hard work; Daniel says ~half are tier-one confidence/findability failures | Escalated tickets that were answerable from docs / expected auto_respond. **Strongest candidate for the key factual contradiction.** | |
| D2 | Is the documentation the problem? | Sofia: docs fine, search broken. Ines (initially) heard "docs are bad"; she now sees agents rewriting her articles from memory | `answerable_from_docs` rate vs actual FCR | |
| D3 | Routine volume vs FCR | Sofia: ~70% are routine and answerable. Marcus: FCR only 42% | FCR within the top (routine) intents | |
| D4 | Response time by tier | Marcus: 8–12 hr average (enterprise on a separate agreement). Ravi: enterprise gets ~1 hr | Resolution time by tier. **Note:** data has resolution time, not first-response time — Marcus's SLA metric isn't directly measurable → log as open question + assumption | |
| D5 | Are current answers safe to learn from? | Ines: KB accurate. Daniel: answers actually sent come from stale private snippet files | Not directly in data; treat historical replies / ground truth with caution. Compare ground-truth `expected_doc_ids` vs KB | |
| D6 | Design tension (not factual) | Marcus: "rather it said nothing than something wrong". Ravi: wants fast, honest, provisional answer. Sofia: wants a draft, not auto-send | Drives the auto-respond threshold; evaluate cost of threshold in both directions using `expected_route` | |

---

## 3. Things expected to be mentioned that nobody did

| # | Never mentioned | Why it was expected | How to check |
|---|---|---|---|
| N1 | Standard-tier, non-fluent customers, and Product/Engineering were not interviewed | Standard ≈ half of volume; non-fluent ≈ a quarter; Eng owns incidents/roadmap | Segment outcomes by tier and fluency; record as interview-coverage gap |
| N2 | Channel differences (email / chat / docs_comment / forum) | Data has four channels; response style and expectations differ | Outcomes and intents by `channel` |
| N3 | How urgency is triaged today | Sofia sorts by age; Ravi says cost of waiting differs hugely | `labels.urgency` vs `resolution_time_minutes` |
| N4 | Time zones / coverage hours | Four regions; Ravi's 4pm ticket waits overnight | `received_at` hour × `customer_region` vs resolution time |
| N5 | CSAT as a headline metric | Marcus cites FCR and response time only, yet CSAT is recorded | `csat_rating` overall and by segment |
| N6 | Outage spikes / duplicate tickets / status page | Platform company; incidents create ticket storms | Clusters of same intent in short `received_at` windows |
| N7 | Reply language for non-fluent customers | ~25% non-fluent; Sofia notes misunderstandings | Open question — not answerable from data; record assumption |
| N8 | Privacy / data residency of the AI system itself | Daniel flags data-location tickets; Marcus has a compliance review | Open question; governance framework / risk register |
| N9 | Feedback loop (agent edits & KB gaps → Ines) | Ines wants source attribution to fix the right thing | Open question; design requirement |
| N10 | Existing helpdesk / ticketing tooling | Solution must integrate somewhere | Open question; record assumption |
| N11 | Budget / cost per ticket of the AI solution | Marcus only talks headcount cost | Open question; estimate in PRD |

---

## Notes to self
- Do not take Marcus's 42% or Sofia's 70% on trust — count them first.
- Evidence points to findability + agent drafts + structured escalation hand-off, not "a chatbot". Capture the "why the obvious answer was wrong" reasoning.
- Dataset Guide says "eight categories" for docs but lists ten — verify actual count in `documentation.json`.
