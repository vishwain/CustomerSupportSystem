"""Stage 1, Section 3: volume vs effort by ticket category.

Usage:
    python docs/effort_analysis.py [--input data/development_tickets.json]
                                   [--output docs/effort_breakdown.md]

Groups the 22 intents into 7 categories and compares share of tickets with
share of effort. Standard library only.

Effort caveat: history.resolution_time_minutes is elapsed time from arrival to
resolution. It includes queue waiting, not just agent handling time. The data
has no agent-minutes field. Two proxies are reported:
  1. Elapsed minutes summed per category (primary, as requested).
  2. Escalation-weighted tickets: resolved = 1 unit, escalated = 4 units,
     using Marcus's interview figure that an escalation costs ~4x.
Agreement between the two raises confidence in the ranking.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

CATEGORIES = {
    "Access & authentication": ["authentication_failure", "account_access",
                                "sso_configuration", "api_key_issue"],
    "Deployment & runtime": ["deployment_failure", "rollback_request",
                             "performance_degradation", "database_issue"],
    "API, integration & setup": ["api_usage_question", "rate_limit", "webhook_issue",
                                 "integration_help", "configuration_help", "onboarding"],
    "Billing & quota": ["billing_query", "quota_or_overage"],
    "Data & compliance": ["data_export", "data_residency", "compliance_request"],
    "Security incidents": ["security_incident"],
    "No documented answer": ["feature_request", "unclear_request"],
}
INTENT_TO_CAT = {i: c for c, intents in CATEGORIES.items() for i in intents}
ESCALATION_WEIGHT = 4


def pct(n, d):
    return 100 * n / d if d else 0.0


def analyse(tickets):
    unknown = {t["labels"]["intent"] for t in tickets} - set(INTENT_TO_CAT)
    if unknown:
        raise SystemExit(f"Unmapped intents: {sorted(unknown)}")
    g = defaultdict(list)
    for t in tickets:
        g[INTENT_TO_CAT[t["labels"]["intent"]]].append(t)

    n = len(tickets)
    total_min = sum(t["history"]["resolution_time_minutes"] for t in tickets)
    weight = lambda t: ESCALATION_WEIGHT if t["history"]["escalated"] else 1
    total_w = sum(weight(t) for t in tickets)

    rows = []
    for cat in CATEGORIES:
        ts = g[cat]
        k = len(ts)
        mins = sum(t["history"]["resolution_time_minutes"] for t in ts)
        w = sum(weight(t) for t in ts)
        vol, eff, effw = pct(k, n), pct(mins, total_min), pct(w, total_w)
        rows.append({
            "category": cat,
            "intents": ", ".join(CATEGORIES[cat]),
            "tickets": k,
            "volume_pct": vol,
            "minutes": mins,
            "effort_pct": eff,
            "effort_weighted_pct": effw,
            "effort_to_volume": eff / vol if vol else 0,
            "mean_min": mins / k,
            "escalated_pct": pct(sum(t["history"]["escalated"] for t in ts), k),
            "answerable_pct": pct(sum(t["labels"]["answerable_from_docs"] for t in ts), k),
            "auto_pct": pct(sum(t["labels"]["expected_route"] == "auto_respond" for t in ts), k),
            "must_not_auto_pct": pct(sum(t["labels"]["must_not_auto_respond"] for t in ts), k),
            "csat": sum(t["history"]["csat_rating"] for t in ts) / k,
            "repeat_pct": pct(sum(t["history"]["repeat_contact"] for t in ts), k),
            "high_urgency_pct": pct(sum(t["labels"]["urgency"] == "high" for t in ts), k),
            # Minutes on tickets escalated although labels say auto_respond: avoidable effort.
            "avoidable_min_pct": pct(sum(t["history"]["resolution_time_minutes"] for t in ts
                                         if t["history"]["escalated"]
                                         and t["labels"]["expected_route"] == "auto_respond"), mins),
            "fcr_mean_min": (sum(t["history"]["resolution_time_minutes"] for t in ts
                                 if not t["history"]["escalated"])
                             / max(1, sum(not t["history"]["escalated"] for t in ts))),
        })
    rows.sort(key=lambda r: -r["effort_pct"])

    # Split of minutes: answerable vs not, escalated vs not.
    ans_min = sum(t["history"]["resolution_time_minutes"] for t in tickets
                  if t["labels"]["answerable_from_docs"])
    esc_min = sum(t["history"]["resolution_time_minutes"] for t in tickets
                  if t["history"]["escalated"])
    auto_min = sum(t["history"]["resolution_time_minutes"] for t in tickets
                   if t["labels"]["expected_route"] == "auto_respond")
    avoid_min = sum(t["history"]["resolution_time_minutes"] for t in tickets
                    if t["history"]["escalated"] and t["labels"]["expected_route"] == "auto_respond")
    totals = {"tickets": n, "minutes": total_min,
              "avoidable_min_pct": pct(avoid_min, total_min),
              "answerable_min_pct": pct(ans_min, total_min),
              "escalated_min_pct": pct(esc_min, total_min),
              "auto_eligible_min_pct": pct(auto_min, total_min)}
    return rows, totals


def to_markdown(rows, totals, src):
    out = [
        "# Volume vs effort by ticket category",
        "",
        f"Generated by `docs/effort_analysis.py` from `{src}`. Do not edit by hand.",
        "",
        "**Effort caveat:** `history.resolution_time_minutes` is elapsed time, including queue wait.",
        "No agent-minutes field exists. Cross-check: escalation-weighted tickets "
        f"(resolved = 1, escalated = {ESCALATION_WEIGHT}, per Marcus's ~4x cost).",
        "",
        "## Category mapping",
        "",
        "| Category | Intents |",
        "|---|---|",
    ]
    out += [f"| {r['category']} | {r['intents']} |" for r in rows]
    out += [
        "",
        "## Volume vs effort",
        "",
        "| Category | Tickets | Volume % | Minutes | Effort % (minutes) | Effort % (esc-weighted) "
        "| Effort ÷ volume | Mean min | Escalated % | Answerable % | Auto-eligible % "
        "| Must-not-auto % | CSAT | Repeat % | High urgency % | Avoidable min % | Mean min if resolved first contact |",
        "|" + "---|" * 17,
    ]
    for r in rows:
        out.append(
            f"| {r['category']} | {r['tickets']} | {r['volume_pct']:.1f} | {r['minutes']:,} "
            f"| {r['effort_pct']:.1f} | {r['effort_weighted_pct']:.1f} | {r['effort_to_volume']:.2f} "
            f"| {r['mean_min']:.0f} | {r['escalated_pct']:.0f} | {r['answerable_pct']:.0f} "
            f"| {r['auto_pct']:.0f} | {r['must_not_auto_pct']:.0f} | {r['csat']:.2f} "
            f"| {r['repeat_pct']:.0f} | {r['high_urgency_pct']:.0f} | {r['avoidable_min_pct']:.0f} "
            f"| {r['fcr_mean_min']:.0f} |")
    out += [
        "",
        "## Totals",
        "",
        f"- Tickets: {totals['tickets']}. Minutes: {totals['minutes']:,}.",
        f"- Share of minutes on answerable tickets: {totals['answerable_min_pct']:.1f}%.",
        f"- Share of minutes on escalated tickets: {totals['escalated_min_pct']:.1f}%.",
        f"- Share of minutes on auto-eligible tickets (expected_route = auto_respond): "
        f"{totals['auto_eligible_min_pct']:.1f}%.",
        f"- Share of minutes on avoidable escalations (escalated, but expected_route = auto_respond): "
        f"{totals['avoidable_min_pct']:.1f}%.",
        "",
    ]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data/development_tickets.json")
    ap.add_argument("--output", default="docs/effort_breakdown.md")
    args = ap.parse_args()
    tickets = json.loads(Path(args.input).read_text(encoding="utf-8"))
    rows, totals = analyse(tickets)
    md = to_markdown(rows, totals, args.input)
    Path(args.output).write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
