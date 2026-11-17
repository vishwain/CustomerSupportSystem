# Data Sources — Notes Outside the Workbook

Findings from the Section 5 data audit that don't fit the table.
Reproduce every figure: `python docs/data_audit.py` (writes `docs/data_audit.md`).

---

## 1. Validation set is not independent of dev
- 45 of 80 validation tickets have the exact same text as a dev ticket. Only 35 are unseen.
- Dev itself has 343 distinct texts across 500 tickets. 254 tickets share a text with another.
- **Effect:** a classifier or prompt tuned on dev will look better on validation than on truly unseen tickets.
- **Action:**
  - Report validation scores two ways: all 80, and the 35 unseen.
  - When tuning on dev, split by text, not by ticket, so duplicates don't sit on both sides.
  - Expect the hidden set to behave similarly (same population per Dataset Guide). Unconfirmed.

## 2. Label noise on identical text
Among 97 dev texts that repeat:

| Label | Texts with conflicting values |
|---|---|
| intent | 0 |
| expected_route | 30 |
| urgency | 67 |
| answerable_from_docs | 36 |

- Intent is consistent. Route, urgency and answerable are not.
- Not yet checked: whether tier, channel or time explain the route conflicts.
- **Effect:** a text-only router has a ceiling below 100% on `expected_route`. Don't read the gap as model error.
- **Action:** check in Stage 3 what else predicts route and urgency (tier, channel, hour). Record the ceiling in the evaluation report.

## 3. Customer identity is unstable
- 150 of 220 customer_ids have 2+ tickets. All 150 show different `customer_name` values across them.
- Tier differs for 112, region for 130, fluency for 74.
- **Effect:**
  - Per-customer history can't be built. Workbook Section 3 step 3 (check customer context) stays an open question.
  - customer_id is not a reliable key for repeat contacts. Fairness segments must be taken per ticket.
- **Assumption for PRD:** tier, region and fluency are read from each ticket as given.
- Not in the data at all: plan, contract, enterprise SLA terms, billing, prior threads.

## 4. Ground truth covers answerable tickets only
- 200 reference answers, all for dev tickets, all answerable from docs. That is 200 of 357 answerable dev tickets (56%).
- None for escalate, unclear or feature-request tickets.
- **Effect:** nothing in the pack shows what a good escalation hand-off looks like. `must_not_claim` is the only negative signal.
- **Action:** write your own escalation-package examples (summary, intent, retrieved docs, uncertainty). Daniel's wish list is the spec.
- If reference answers are used as few-shot examples, exclude those tickets from generation scoring.

## 5. Private data: what the scan does and doesn't show
- Pattern scan (email, phone, IP, URL, card-like, key-like, long secret, CUST id) found **0 matches** in ticket text, reference answers and docs.
- Customer first names appear in **no** ticket text or reference answer.
- A regex scan is a floor, not proof. The hidden set is unseen.
- Real outbound risks are: the model echoing `customer_name` or `customer_id`, inventing identifiers, or leaking across tickets.
- **Decisions to confirm in PRD:**
  - Never pass `customer_name` or `customer_id` into a prompt.
  - Retrieval corpus is `documentation.json` only. Never index tickets or reference answers.
  - Outbound guardrail blocks both fields and runs the same pattern scan.

## 6. Which fields the system may read at run time (proposal)
- Allowed: `subject`, `body`, `channel`, `received_at`.
- Audit only: `customer_tier`, `customer_region`, `language_fluency`. Using fluency to change behaviour would itself be a fairness risk.
- Never: anything under `labels` or `history`.
- **Open decision:** tier may be needed for enterprise handling (Marcus's worry). If so, say why in the PRD and test it in the fairness audit.

## 7. Repo hygiene
- All four data files are tracked in git, including validation tickets and ground truth. The GitHub repo is public (your setup).
  - Check the course rules on publishing validation tickets and reference answers.
  - Option: untrack `data/`, add it to `.gitignore`, and document where to copy it from in the README.
- `.env.example` is listed in `.gitignore` and is not tracked. A clean checkout has no template. Reference README says it holds placeholders only, so it can be committed.
  - This bears on the clean-checkout gate (A9). Remove it from `.gitignore` and commit it.
- `.env` is correctly ignored.

## 8. Still open
- Where the agents' private snippet files are, and whether any can be provided for review.
- Whether the hidden set is 100 or 120 tickets. See `DocumentInconsistencies.md` I1.
