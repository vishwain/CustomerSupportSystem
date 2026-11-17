"""Stage 1 discovery analysis: counts for Section 2 of the Discovery Workbook.

Usage:
    python docs/discovery_analysis.py [--input data/development_tickets.json]

Standard library only. Prints each Section 2 figure with the field and
calculation it came from, so every workbook number can be traced back here.
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def pct(n, d):
    return f"{100 * n / d:.1f}%" if d else "n/a"


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else float("nan")


def split(tickets, key_fn, title):
    n = len(tickets)
    c = Counter(key_fn(t) for t in tickets)
    print(f"\n## {title}")
    for k, v in c.most_common():
        print(f"  {k:<28} {v:>4}  {pct(v, n)}")
    return c


def outcomes(group):
    """FCR, CSAT, resolution time, escalation and repeat rate for a ticket group."""
    n = len(group)
    h = [t["history"] for t in group]
    return {
        "n": n,
        "fcr": pct(sum(x["first_contact_resolution"] for x in h), n),
        "csat": round(mean([x["csat_rating"] for x in h]), 2),
        "res_min_mean": round(mean([x["resolution_time_minutes"] for x in h])),
        "escalated": pct(sum(x["escalated"] for x in h), n),
        "repeat": pct(sum(x["repeat_contact"] for x in h), n),
    }


def by_segment(tickets, field, title):
    groups = defaultdict(list)
    for t in tickets:
        groups[t[field]].append(t)
    print(f"\n## {title} (field: {field})")
    print("  segment          n     FCR     CSAT  res_min  escalated  repeat")
    for k in sorted(groups):
        o = outcomes(groups[k])
        print(f"  {k:<14} {o['n']:>4}  {o['fcr']:>6}  {o['csat']:>5}  {o['res_min_mean']:>7}"
              f"  {o['escalated']:>9}  {o['repeat']:>6}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data/development_tickets.json")
    args = ap.parse_args()

    tickets = json.loads(Path(args.input).read_text(encoding="utf-8"))
    n = len(tickets)
    print(f"# Section 2 figures from {args.input}")
    print(f"\n## Total tickets (len of list): {n}")

    split(tickets, lambda t: t["channel"], "Channel (channel)")
    intents = split(tickets, lambda t: t["labels"]["intent"], "Intent (labels.intent)")
    print(f"  distinct intents: {len(intents)}")
    top5 = sum(v for _, v in intents.most_common(5))
    print(f"  top-5 intents share: {pct(top5, n)}")
    split(tickets, lambda t: t["labels"]["urgency"], "Urgency (labels.urgency)")

    fcr = sum(t["history"]["first_contact_resolution"] for t in tickets)
    print(f"\n## First contact resolution (history.first_contact_resolution == true): "
          f"{fcr}/{n} = {pct(fcr, n)}")

    csats = [t["history"]["csat_rating"] for t in tickets]
    print(f"\n## Average CSAT (mean of history.csat_rating, nulls excluded): "
          f"{mean(csats):.2f}  (rated tickets: {sum(c is not None for c in csats)})")
    split(tickets, lambda t: t["history"]["csat_rating"], "CSAT distribution")

    top_intent, top_n = intents.most_common(1)[0]
    print(f"\n## Most frequent single question (mode of labels.intent): "
          f"{top_intent} {top_n} = {pct(top_n, n)}")

    ans = sum(t["labels"]["answerable_from_docs"] for t in tickets)
    print(f"\n## Answerable from docs (labels.answerable_from_docs == true): "
          f"{ans}/{n} = {pct(ans, n)}")

    nf = [t for t in tickets if t["language_fluency"] == "non_fluent"]
    print(f"\n## Non-fluent (language_fluency == non_fluent): {len(nf)}/{n} = {pct(len(nf), n)}")
    by_segment(tickets, "language_fluency", "Outcomes by fluency")

    by_segment(tickets, "customer_tier", "Outcomes by tier")

    rep = sum(t["history"]["repeat_contact"] for t in tickets)
    print(f"\n## Repeat contacts (history.repeat_contact == true): {rep}/{n} = {pct(rep, n)}")

    esc = sum(t["history"]["escalated"] for t in tickets)
    print(f"\n## Context: escalated (history.escalated == true): {esc}/{n} = {pct(esc, n)}")
    esc_ans = sum(t["history"]["escalated"] and t["labels"]["answerable_from_docs"] for t in tickets)
    print(f"## Context: escalated AND answerable_from_docs: {esc_ans}/{esc} = {pct(esc_ans, esc)}")
    print(f"## Context: overall outcomes: {outcomes(tickets)}")


if __name__ == "__main__":
    main()
