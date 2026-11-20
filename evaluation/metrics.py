"""Metrics report (5.13, A10; PRD FR-27, FR-28, NFR-01, NFR-05, NFR-06, NFR-08, NFR-10).

Built from the decision log and the input file only (FR-27). The harness calls build_report() at the end
of every run and writes <output>/metrics_report.md and .json, plus answer_review.csv for the human
review of sent answers (NFR-08). Labels and segment fields (tier, fluency) are joined from the input file
by ticket_id here, in the evaluation layer; the pipeline never reads them (FR-03). Label-based figures
show "n/a" when the input has no labels.

A consistency section recomputes the main counts from results.jsonl and compares them with the figures
from the decision log, so the report shows it matches the log.

Re-build the report for an existing run (no re-run, no model):
    python -m evaluation.metrics --run-dir evaluation/results/<run folder>
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from src import pii
from src.ingest import iter_raw, load
from src.logging_store import REQUIRED
from src.splits import text_key

DEV_PATH = Path("data/development_tickets.json")
LATENCY_TARGET_MS = 3000  # NFR-01
SEGMENT_GAP_PTS = 5.0  # NFR-06
CAL_BANDS = ((0.0, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 0.95), (0.95, 1.0001))  # NFR-10, 5 bands
CAL_MIN_N = 20
SHORT_WORDS = 28  # NFR-06 length split (dev median)
ROUTE_RULES = ("kill_switch", "instruction_integrity", "prior_contact_claim", "billing_dispute", "risk_terms",
               "must_escalate_intent", "must_escalate_alternative", "classification_failed", "no_retrieval_hit")


# ------------------------------------------------------------------ helpers

def pct(k: int, n: int) -> float | None:
    return round(100.0 * k / n, 1) if n else None


def percentile(xs: list[float], q: float) -> int | None:
    if not xs:
        return None
    s = sorted(xs)
    return int(s[min(len(s) - 1, int(round(q * (len(s) - 1))))])


def fmt(x: Any, unit: str = "") -> str:
    if x is None:
        return "n/a"
    if isinstance(x, float):
        return f"{x:g}{unit}"
    return f"{x}{unit}"


def git_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or "n/a"
    except (OSError, subprocess.SubprocessError):
        return "n/a"


def input_join(input_path: Path) -> dict[str, dict[str, Any]]:
    """ticket_id (as ingest assigns it) -> raw input record, for labels and segment fields."""
    raws = [raw for _, raw in iter_raw(input_path)]
    return {rec.ticket_id: (raw if isinstance(raw, dict) else {}) for rec, raw in zip(load(input_path), raws)}


def dev_text_keys(input_path: Path) -> set[str] | None:
    """FR-28: texts seen in dev. None when the input is the dev file itself or dev is missing."""
    if not DEV_PATH.exists() or Path(input_path).resolve() == DEV_PATH.resolve():
        return None
    return {text_key(t) for t in json.loads(DEV_PATH.read_text(encoding="utf-8"))}


def by_ticket(rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    out: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for r in rows:
        out[r["ticket_id"]][r["stage"]] = r  # one row per stage per ticket in this pipeline
    return out


def rule_family(rule: str) -> str:
    rule = rule or "none"
    for f in ROUTE_RULES:
        if rule.startswith(f):
            return f
    if rule.startswith("guardrail:"):
        return "validate_block"
    if rule.startswith("provider_"):
        return "provider_failure"
    return rule


# ------------------------------------------------------------------ figures

def ticket_facts(tid: str, st: dict[str, dict[str, Any]], raw: dict[str, Any]) -> dict[str, Any]:
    """Everything the report needs about one ticket, from its log rows and its input record."""
    fin, ing = st.get("final", {}), st.get("ingest", {})
    cls, ret, rte = st.get("classification"), st.get("retrieval"), st.get("routing")
    gen, val = st.get("generation"), st.get("validation")
    lab = raw.get("labels") or {}
    wait = sum(int(r.get("rate_limit_wait_ms") or 0) for r in st.values())
    retrieved = [s["doc_id"] for s in (ret or {}).get("sources_used", [])]
    allowed = {s["passage_id"] for s in (ret or {}).get("sources_used", [])} | set(
        (ret or {}).get("prediction", {}).get("context_added", []))
    cited = [s["passage_id"] for s in (gen or {}).get("sources_used", [])]
    cited_docs = sorted({c.split("#")[0] for c in cited})
    expected = lab.get("expected_doc_ids") or []
    body = raw.get("body") if isinstance(raw.get("body"), str) else ""
    return {
        "ticket_id": tid,
        "channel": (ing.get("prediction") or {}).get("channel", "unknown"),
        "action": fin.get("action_taken"), "rule": fin.get("rule_fired", "none"), "error": fin.get("error", "none"),
        "degraded": bool(fin.get("degraded_mode")),
        "latency_ms": int(fin.get("latency_ms") or 0), "wait_ms": wait,
        "route": (rte or {}).get("action_taken"), "route_rule": (rte or {}).get("rule_fired", "none"),
        "intent": ((cls or {}).get("prediction") or {}).get("intent"),
        "intent_conf": (cls or {}).get("confidence"),
        "urgency": ((cls or {}).get("prediction") or {}).get("urgency"),
        "retrieved_docs": retrieved,
        "generated": gen is not None, "gen_action": (gen or {}).get("action_taken"),
        "citations_ok": ((gen or {}).get("prediction") or {}).get("citations_ok"),
        "cited": cited, "cited_docs": cited_docs, "cited_in_retrieved": all(c in allowed for c in cited),
        "requests": sum(int(r.get("requests") or 0) for r in st.values()),
        "cached": bool(((gen or {}).get("prediction") or {}).get("cached")),
        "validation": (val or {}).get("guardrail_results") or {},
        "blocked_by": ((val or {}).get("prediction") or {}).get("blocked_by") or [],
        # labels and segments (input file; n/a when absent)
        "has_labels": bool(lab),
        "label_intent": lab.get("intent"), "label_urgency": lab.get("urgency"),
        "expected_route": lab.get("expected_route"), "answerable": lab.get("answerable_from_docs"),
        "must_not": bool(lab.get("must_not_auto_respond")), "expected_docs": expected,
        "tier": raw.get("customer_tier") or "unknown", "fluency": raw.get("language_fluency") or "unknown",
        "region": raw.get("customer_region") or "unknown",
        "has_subject": bool(str(raw.get("subject") or "").strip()),
        "query_expanded": bool(((ret or {}).get("prediction") or {}).get("query_intent")),
        "length": "short (<=28 words)" if len(body.split()) <= SHORT_WORDS else "long (>28 words)",
        "text_key": text_key(raw) if raw else "",
    }


def hit3(f: dict[str, Any]) -> bool:
    return bool(set(f["retrieved_docs"][:3]) & set(f["expected_docs"]))


def subset_figures(fs: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(fs)
    auto = [f for f in fs if f["action"] == "auto_respond"]
    lab = [f for f in fs if f["has_labels"]]
    ans = [f for f in lab if f["answerable"] and f["expected_docs"]]
    sent_lab = [f for f in auto if f["expected_docs"]]
    elig = [f for f in lab if f["answerable"] and not f["must_not"]]
    return {
        "n": n, "auto": len(auto), "auto_rate": pct(len(auto), n), "escalation_rate": pct(n - len(auto), n),
        "auto_rate_eligible": pct(sum(f["action"] == "auto_respond" for f in elig), len(elig)) if elig else None,
        "eligible_n": len(elig),
        "intent_accuracy": pct(sum(f["intent"] == f["label_intent"] for f in lab), len(lab)) if lab else None,
        "retrieval_hit3": pct(sum(hit3(f) for f in ans), len(ans)) if ans else None, "retrieval_n": len(ans),
        "sent_cites_expected_doc": pct(sum(bool(set(f["cited_docs"]) & set(f["expected_docs"])) for f in sent_lab),
                                       len(sent_lab)) if sent_lab else None,
        "sent_with_expected_docs": len(sent_lab),
    }


def per_class(fs: list[dict[str, Any]], pred_key: str, label_key: str) -> dict[str, Any]:
    lab = [f for f in fs if f["has_labels"] and f[label_key] is not None]
    classes = sorted({f[label_key] for f in lab} | {f[pred_key] for f in lab if f[pred_key]})
    out = {}
    for c in classes:
        tp = sum(f[pred_key] == c and f[label_key] == c for f in lab)
        fp = sum(f[pred_key] == c and f[label_key] != c for f in lab)
        fn = sum(f[pred_key] != c and f[label_key] == c for f in lab)
        out[c] = {"n": tp + fn, "precision": pct(tp, tp + fp), "recall": pct(tp, tp + fn)}
    have = [v for v in out.values() if v["n"]]
    macro_p = [v["precision"] for v in have if v["precision"] is not None]
    return {"per_class": out,
            "macro_precision": round(statistics.mean(macro_p), 1) if macro_p else None,
            "macro_recall": round(statistics.mean(v["recall"] for v in have), 1) if have else None,
            "accuracy": pct(sum(f[pred_key] == f[label_key] for f in lab), len(lab)) if lab else None}


def confusion(fs: list[dict[str, Any]], pred_key: str, label_key: str) -> dict[str, Any]:
    """Rows = label, columns = prediction. Off-diagonal cells listed separately for the report."""
    lab = [f for f in fs if f["has_labels"] and f[label_key] is not None]
    classes = sorted({f[label_key] for f in lab} | {str(f[pred_key]) for f in lab})
    m = {a: {b: 0 for b in classes} for a in classes}
    for f in lab:
        m[f[label_key]][str(f[pred_key])] += 1
    off = sorted(((a, b, n) for a, row in m.items() for b, n in row.items() if a != b and n),
                 key=lambda x: -x[2])
    return {"classes": classes, "matrix": m, "off_diagonal": [{"label": a, "predicted": b, "n": n} for a, b, n in off]}


def outbound_private_data(results: list[dict[str, Any]] | None, raw_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Safety (NFR-04): scan EVERY outbound customer message (sent answers and holding messages) for
    private-data patterns and for any customer name or id that appears anywhere in the input file."""
    if results is None:
        return {"scanned": None}
    terms = {str(v).strip() for raw in raw_by_id.values() for k in ("customer_name", "customer_id")
             for v in [raw.get(k)] if v and len(str(v).strip()) >= 3}
    hits = []
    for r in results:
        text = r.get("customer_message") or ""
        found = pii.find(text)
        low = text.lower()
        names = sorted(t for t in terms if t.lower() in low)
        if found or names:
            hits.append({"ticket_id": r["ticket_id"], "patterns": found, "customer_terms": len(names)})
    return {"scanned": len(results), "sent_answers": sum(r["action"] == "auto_respond" for r in results),
            "messages_with_private_data": len(hits), "hits": hits,
            "terms_checked": len(terms)}


def calibration(fs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lab = [f for f in fs if f["has_labels"] and f["intent_conf"] is not None and f["intent"] not in (None, "unknown")]
    out = []
    for lo, hi in CAL_BANDS:
        b = [f for f in lab if lo <= f["intent_conf"] < hi]
        if not b:
            out.append({"band": f"{lo:g}-{min(hi, 1):g}", "n": 0})
            continue
        conf = 100 * statistics.mean(f["intent_conf"] for f in b)
        acc = 100 * sum(f["intent"] == f["label_intent"] for f in b) / len(b)
        out.append({"band": f"{lo:g}-{min(hi, 1):g}", "n": len(b), "mean_confidence": round(conf, 1),
                    "accuracy": round(acc, 1), "gap_pts": round(conf - acc, 1),
                    "pass": None if len(b) < CAL_MIN_N else abs(conf - acc) <= 5.0})
    return out


def segments(fs: list[dict[str, Any]]) -> dict[str, Any]:
    out = {}
    for dim in ("tier", "region", "fluency", "channel", "length"):
        groups = defaultdict(list)
        for f in fs:
            groups[f[dim]].append(f)
        rows = {g: subset_figures(v) for g, v in sorted(groups.items())}
        gaps = {}
        for k in ("auto_rate_eligible", "retrieval_hit3"):
            vals = [r[k] for r in rows.values() if r[k] is not None and r["n"] >= 10]
            gaps[k] = round(max(vals) - min(vals), 1) if len(vals) >= 2 else None
        out[dim] = {"groups": rows, "gap_pts": gaps,
                    "pass": None if gaps["auto_rate_eligible"] is None else all(
                        g is None or g < SEGMENT_GAP_PTS for g in gaps.values())}
    return out


def build_report(rows: list[dict[str, Any]], run_info: dict[str, Any],
                 results: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    input_path = Path(run_info["input_path"])
    raw_by_id = input_join(input_path)
    n_run = int(run_info.get("tickets_in") or 0)
    if n_run and n_run < len(raw_by_id):  # --limit N: the run covers the first N records only
        raw_by_id = dict(list(raw_by_id.items())[:n_run])
    st_by = by_ticket(rows)
    fs = [ticket_facts(tid, st_by.get(tid, {}), raw) for tid, raw in raw_by_id.items()]
    labelled = any(f["has_labels"] for f in fs)
    n = len(fs)
    finals = [r for r in rows if r["stage"] == "final"]
    auto = [f for f in fs if f["action"] == "auto_respond"]
    esc = [f for f in fs if f["action"] == "escalate"]

    # ---- volume
    by_channel = Counter(f["channel"] for f in fs)
    volume = {
        "processed": n, "automatic": len(auto), "escalated": len(esc),
        "by_channel": dict(by_channel),
        "by_channel_and_outcome": {c: dict(Counter(f["action"] for f in fs if f["channel"] == c)) for c in by_channel},
        "escalated_by_cause": dict(Counter(rule_family(f["rule"]) if f["rule"] != "none" else
                                           (f["error"] if f["error"] != "none" else "other") for f in esc)),
        "blocked_by_guardrail": dict(Counter(b for f in fs for b in f["blocked_by"])),
    }

    # ---- business
    lat = [f["latency_ms"] for f in fs if f["action"]]
    business = {
        "auto_resolution_rate": pct(len(auto), n), "escalation_rate": pct(len(esc), n),
        "replay_fcr": pct(sum(f["expected_route"] == "auto_respond" for f in auto), n) if labelled else None,
        "replay_fcr_definition": "automatic answers on tickets labelled expected_route = auto_respond, that passed "
                                 "Validate, / all tickets (PRD Section 8). The label follows past handling (AS-07).",
        "time_to_final_ms_mean": round(statistics.mean(lat)) if lat else None,
        "time_to_final_ms_median": percentile(lat, 0.5),
    }

    # ---- technical
    proc = [max(0, f["latency_ms"] - f["wait_ms"]) for f in fs if f["action"]]
    gens = [f for f in fs if f["generated"]]
    intent = per_class(fs, "intent", "label_intent") if labelled else None
    urgency = per_class(fs, "urgency", "label_urgency") if labelled else None
    ans = [f for f in fs if f["answerable"] and f["expected_docs"]]
    technical = {
        "intent": intent, "urgency": urgency,
        "retrieval_hit3": pct(sum(hit3(f) for f in ans), len(ans)) if ans else None, "retrieval_n": len(ans),
        "retrieval_by_subject": {k: {"n": len(g), "hit3": pct(sum(hit3(f) for f in g), len(g)) if g else None}
                                 for k, g in (("with subject", [f for f in ans if f["has_subject"]]),
                                              ("no subject", [f for f in ans if not f["has_subject"]]))},
        "query_expanded_tickets": sum(f["query_expanded"] for f in fs),
        "latency_ms_p50": percentile(lat, 0.5), "latency_ms_p95": percentile(lat, 0.95),
        "processing_ms_p50": percentile(proc, 0.5), "processing_ms_p95": percentile(proc, 0.95),
        "nfr01_pass": None if not proc else percentile(proc, 0.95) < LATENCY_TARGET_MS,
        "stage_latency_ms": {s: {"n": len(xs), "p50": percentile(xs, 0.5), "p95": percentile(xs, 0.95)}
                             for s in ("classification", "retrieval", "generation", "validation")
                             for xs in [[int(r.get("latency_ms") or 0) for r in rows if r["stage"] == s]] if xs},
        "provider_wait_ms_total": sum(f["wait_ms"] for f in fs),
        "provider_requests": sum(f["requests"] for f in fs),
        "generation_cache_hits": sum(f["cached"] for f in fs),
        "citations": {
            "generated_answers": len(gens),
            "citations_resolve_in_code": pct(sum(bool(f["citations_ok"]) for f in gens), len(gens)),
            "sent_answers": len(auto),
            "sent_cited_ids_in_retrieved_set": pct(sum(f["cited_in_retrieved"] and bool(f["cited"]) for f in auto),
                                                   len(auto)),
            "sent_cites_expected_doc": subset_figures(fs)["sent_cites_expected_doc"],
            "sent_with_expected_docs": subset_figures(fs)["sent_with_expected_docs"],
            "hallucination_rate": None,
            "note": "Citation validity is checked in code: every cited passage id must be in the set retrieved for "
                    "that ticket. Agreement with expected_doc_ids is reported, not a gate (AS-03, AS-07: labels are "
                    "per intent and follow past handling). Hallucination rate and human citation accuracy come from "
                    "answer_review.csv (NFR-08).",
        },
    }

    # ---- governance
    empty = sum(1 for r in rows for c in REQUIRED if r.get(c) in (None, "") or (isinstance(r.get(c), str)
                                                                                and not r[c].strip()))
    final_ids = Counter(r["ticket_id"] for r in finals)
    checks = Counter()
    for f in fs:
        for k, v in f["validation"].items():
            checks[(k, v)] += 1
    route_rules = Counter(rule_family(f["route_rule"]) for f in fs if f["route_rule"] not in ("none", None))
    governance = {
        "tickets_in_input": n, "final_rows": len(finals),
        "tickets_without_final": sorted(set(raw_by_id) - set(final_ids))[:20],
        "duplicate_final_rows": sum(v - 1 for v in final_ids.values() if v > 1),
        "rows_with_empty_required_field": empty,
        "decision_log_coverage_ok": len(finals) == n and set(final_ids) == set(raw_by_id) and empty == 0,
        "rows_by_stage": dict(Counter(r["stage"] for r in rows)),
        "route_rule_activations": dict(route_rules),
        "validate_checks": {k: {"pass": checks[(k, "pass")], "block": checks[(k, "block")],
                                "warn": checks[(k, "warn")]} for k in sorted({k for k, _ in checks})},
        "validate_blocks": sum(bool(f["blocked_by"]) for f in fs),
        "private_data_detections": checks[("private_data", "block")],
        "unsafe_automatic_answers": sum(f["must_not"] for f in auto) if labelled else None,
        "degraded_mode_tickets": sum(f["degraded"] for f in fs),
        "errors": dict(Counter(f["error"] for f in fs)),
    }

    # ---- segments, calibration, FR-28
    seen = dev_text_keys(input_path)
    fr28 = {"all": subset_figures(fs)}
    if seen is not None:
        fr28["unseen"] = subset_figures([f for f in fs if f["text_key"] not in seen])
        fr28["repeats_dev_text"] = subset_figures([f for f in fs if f["text_key"] in seen])

    report = {
        "run": {"run_id": run_info["run_id"], "finished_at": run_info.get("finished_at"),
                "git_commit": git_commit(), "input": run_info["input_path"],
                "input_sha256": run_info.get("input_sha256"), "runs_on_this_input": run_info.get("runs_on_this_input"),
                "labelled_input": labelled},
        "volume": volume, "business": business, "technical": technical, "governance": governance,
        "segments": segments(fs) if labelled else None,
        "calibration": calibration(fs) if labelled else None,
        "fr28": fr28,
        # flat keys kept for gate_check and the failure drill
        "tickets_in": n, "final_rows": len(finals), "decision_log_coverage_ok": governance["decision_log_coverage_ok"],
        "provider_requests": technical["provider_requests"],
        "generation_cache_hits": technical["generation_cache_hits"],
        "degraded_mode_tickets": governance["degraded_mode_tickets"],
        "latency_ms_p50": technical["latency_ms_p50"], "latency_ms_p95": technical["latency_ms_p95"],
        "by_action": dict(Counter(f["action"] for f in fs)), "by_channel": volume["by_channel"],
        "by_route_action": dict(Counter(f["route"] for f in fs)), "by_error": governance["errors"],
    }
    report["consistency"] = consistency(fs, results) if results is not None else None
    report["confusion"] = ({"intent": confusion(fs, "intent", "label_intent"),
                            "urgency": confusion(fs, "urgency", "label_urgency")} if labelled else None)
    report["safety"] = outbound_private_data(results, raw_by_id)
    return report


def consistency(fs: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    """Recount from results.jsonl and compare with the decision-log figures."""
    pairs = {
        "tickets": (len(fs), len(results)),
        "final actions": (dict(Counter(f["action"] for f in fs)), dict(Counter(r["action"] for r in results))),
        "channels": (dict(Counter(f["channel"] for f in fs)), dict(Counter(r["channel"] for r in results))),
        "route actions": (dict(Counter(f["route"] for f in fs if f["route"])),
                          dict(Counter(r["route_action"] for r in results
                                       if r.get("route_action") not in (None, "", "n/a", "none")))),
        "final rule fired": (dict(Counter(f["rule"] for f in fs)), dict(Counter(r["rule_fired"] for r in results))),
        "errors": (dict(Counter(f["error"] for f in fs)), dict(Counter(r["error"] for r in results))),
        "sent answers with a reply": (sum(f["action"] == "auto_respond" for f in fs),
                                      sum(r["action"] == "auto_respond" and bool(r.get("reply")) for r in results)),
        "Validate blocks": (sum(bool(f["blocked_by"]) for f in fs),
                            sum((r.get("generation") or {}).get("validated") is False for r in results)),
    }
    return {k: {"log": a, "results": b, "match": a == b} for k, (a, b) in pairs.items()}


# ------------------------------------------------------------------ outputs

def to_markdown(m: dict[str, Any]) -> str:
    r, v, b, t, g = m["run"], m["volume"], m["business"], m["technical"], m["governance"]
    L = [f"# Metrics report: {r['run_id']}", "",
         f"Input `{r['input']}` (sha256 {str(r['input_sha256'])[:12]}), run {r['runs_on_this_input']} on this file, "
         f"finished {r['finished_at']}, git {r['git_commit']}. Built from the decision log and the input file "
         "(FR-27) by `evaluation/metrics.py`." + ("" if r["labelled_input"] else " Input has no labels: label-based "
                                                   "figures are n/a."), ""]
    L += ["## Volume", "", "| Figure | Value |", "| --- | --- |",
          f"| Tickets processed | {v['processed']} |", f"| Answered automatically | {v['automatic']} |",
          f"| Escalated | {v['escalated']} |", "", "| Channel | Tickets | Automatic | Escalated |",
          "| --- | --- | --- | --- |"]
    for c, k in sorted(v["by_channel"].items()):
        o = v["by_channel_and_outcome"][c]
        L.append(f"| {c} | {k} | {o.get('auto_respond', 0)} | {o.get('escalate', 0)} |")
    L += ["", "Escalated by cause: " + ", ".join(f"{k} {n}" for k, n in sorted(v["escalated_by_cause"].items(),
                                                                                key=lambda x: -x[1])),
          "", "Blocked by guardrail: " + (", ".join(f"{k} {n}" for k, n in v["blocked_by_guardrail"].items()) or "none")]
    L += ["", "## Business", "", "| Figure | Value | Target |", "| --- | --- | --- |",
          f"| Auto-resolution rate | {fmt(b['auto_resolution_rate'], '%')} | 50% or more (Section 8) |",
          f"| Escalation rate | {fmt(b['escalation_rate'], '%')} | 50% or less |",
          f"| Replay FCR (label-based) | {fmt(b['replay_fcr'], '%')} | 50% or more |",
          f"| Time to final action, mean / median | {fmt(b['time_to_final_ms_mean'], ' ms')} / "
          f"{fmt(b['time_to_final_ms_median'], ' ms')} | |", "", b["replay_fcr_definition"]]
    i, u, c = t["intent"], t["urgency"], t["citations"]
    L += ["", "## Technical", "", "| Figure | Value | Target |", "| --- | --- | --- |",
          f"| Intent accuracy | {fmt(i and i['accuracy'], '%')} | |",
          f"| Intent macro precision / recall | {fmt(i and i['macro_precision'], '%')} / "
          f"{fmt(i and i['macro_recall'], '%')} | 85% or more (NFR-03) |",
          f"| Urgency accuracy | {fmt(u and u['accuracy'], '%')} | |",
          f"| Retrieval hit rate, top 3 (answerable, n={t['retrieval_n']}) | {fmt(t['retrieval_hit3'], '%')} | "
          "85% or more (AS-01) |",
          "| Hit@3 with / without a subject | " + " / ".join(
              f"{fmt(x['hit3'], '%')} (n={x['n']})" for x in t["retrieval_by_subject"].values())
          + f" | Tickets with the intent-expanded query: {t['query_expanded_tickets']} |",
          f"| Latency p50 / p95, ingest to final action | {fmt(t['latency_ms_p50'], ' ms')} / "
          f"{fmt(t['latency_ms_p95'], ' ms')} | |",
          f"| Latency p50 / p95, excluding provider waits (NFR-01) | {fmt(t['processing_ms_p50'], ' ms')} / "
          f"{fmt(t['processing_ms_p95'], ' ms')} | p95 under 3,000 ms: "
          f"{'PASS' if t['nfr01_pass'] else 'FAIL' if t['nfr01_pass'] is False else 'n/a'} |",
          "| Stage latency p50 / p95 | " + "; ".join(f"{s} {x['p50']} / {x['p95']} ms (n={x['n']})"
                                                     for s, x in t["stage_latency_ms"].items()) + " | |",
          f"| Provider requests / cache hits / wait total | {t['provider_requests']} / {t['generation_cache_hits']} / "
          f"{t['provider_wait_ms_total']} ms | |",
          f"| Generated answers whose citations resolve (checked in code) | {fmt(c['citations_resolve_in_code'], '%')} "
          f"of {c['generated_answers']} | |",
          f"| Sent answers: every cited passage in the retrieved set | {fmt(c['sent_cited_ids_in_retrieved_set'], '%')}"
          f" of {c['sent_answers']} | 100% |",
          f"| Sent answers citing a labelled expected article | {fmt(c['sent_cites_expected_doc'], '%')} of "
          f"{c['sent_with_expected_docs']} | reported only |",
          f"| Hallucination rate / human citation accuracy | from answer_review.csv | 5% or less / 95% or more "
          "(NFR-08) |", "", c["note"]]
    if i:
        L += ["", "Intent per class (labelled n, precision, recall): " + "; ".join(
            f"{k} {x['n']} {fmt(x['precision'])}/{fmt(x['recall'])}" for k, x in i["per_class"].items())]
    if u:
        L += ["", "Urgency per level (n, precision, recall): " + "; ".join(
            f"{k} {x['n']} {fmt(x['precision'])}/{fmt(x['recall'])}" for k, x in u["per_class"].items())]
    L += ["", "## Governance", "", "| Figure | Value |", "| --- | --- |",
          f"| Final rows / tickets in input | {g['final_rows']} / {g['tickets_in_input']} |",
          f"| Tickets without a final row / duplicate final rows | {len(g['tickets_without_final'])} / "
          f"{g['duplicate_final_rows']} |",
          f"| Rows with an empty required field | {g['rows_with_empty_required_field']} |",
          f"| Decision-log coverage (NFR-05) | {'100%: PASS' if g['decision_log_coverage_ok'] else 'FAIL'} |",
          f"| Validate blocks | {g['validate_blocks']} |",
          f"| Private-data detections (NFR-04) | {g['private_data_detections']} |",
          f"| Unsafe automatic answers (must_not_auto_respond, NFR-09) | {fmt(g['unsafe_automatic_answers'])} |",
          f"| Degraded-mode tickets | {g['degraded_mode_tickets']} |",
          f"| Errors | {', '.join(f'{k} {n}' for k, n in g['errors'].items())} |",
          "", "Route rule activations: " + (", ".join(f"{k} {n}" for k, n in sorted(
              g["route_rule_activations"].items(), key=lambda x: -x[1])) or "none"),
          "", "| Validate check | Pass | Block | Warn |", "| --- | --- | --- | --- |"]
    for k, x in g["validate_checks"].items():
        L.append(f"| {k} | {x['pass']} | {x['block']} | {x['warn']} |")
    L += ["", f"Rows by stage: {g['rows_by_stage']}"]
    if m["segments"]:
        L += ["", "## Segments (NFR-06: under 5 pts between groups of 10 or more; 5b.3)", "",
              "Auto rate (eligible) = automatic answers among tickets labelled answerable and not must-not-auto-respond, "
              "so intent mix does not drive the gap (FR-19 acceptance).", "",
              "| Dimension | Group | n | Auto rate (all) | Auto rate, eligible (n) | Hit@3 (n) | Intent acc |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
        for dim, s in m["segments"].items():
            for grp, x in s["groups"].items():
                L.append(f"| {dim} | {grp} | {x['n']} | {fmt(x['auto_rate'], '%')} | {fmt(x['auto_rate_eligible'], '%')} "
                         f"({x['eligible_n']}) | {fmt(x['retrieval_hit3'], '%')} ({x['retrieval_n']}) | "
                         f"{fmt(x['intent_accuracy'], '%')} |")
            gp = s["gap_pts"]
            L.append(f"| {dim} | **gap (groups of 10+)** | | | {fmt(gp['auto_rate_eligible'], ' pts')} | "
                     f"{fmt(gp['retrieval_hit3'], ' pts')} | "
                     f"{'PASS' if s['pass'] else 'FAIL' if s['pass'] is False else 'n/a'} |")
    if m["calibration"]:
        L += ["", f"## Calibration (NFR-10: within 5 pts in bands of {CAL_MIN_N}+)", "",
              "| Band | n | Mean confidence | Accuracy | Gap | Result |", "| --- | --- | --- | --- | --- | --- |"]
        for x in m["calibration"]:
            if x["n"]:
                L.append(f"| {x['band']} | {x['n']} | {x['mean_confidence']}% | {x['accuracy']}% | {x['gap_pts']} | "
                         f"{'PASS' if x['pass'] else 'FAIL' if x['pass'] is False else 'n < 20'} |")
            else:
                L.append(f"| {x['band']} | 0 | | | | |")
    L += ["", "## All tickets vs unseen text (FR-28)", "",
          "| Subset | n | Auto rate | Intent acc | Hit@3 (n) | Sent citing expected article (n) |",
          "| --- | --- | --- | --- | --- | --- |"]
    for k, x in m["fr28"].items():
        L.append(f"| {k} | {x['n']} | {fmt(x['auto_rate'], '%')} | {fmt(x['intent_accuracy'], '%')} | "
                 f"{fmt(x['retrieval_hit3'], '%')} ({x['retrieval_n']}) | {fmt(x['sent_cites_expected_doc'], '%')} "
                 f"({x['sent_with_expected_docs']}) |")
    if m.get("confusion"):
        u = m["confusion"]["urgency"]
        L += ["", "## Confusion matrices", "", "Urgency (rows = label, columns = predicted):", "",
              "| label \\ predicted | " + " | ".join(u["classes"]) + " |", "| --- |" + " --- |" * len(u["classes"])]
        for a in u["classes"]:
            L.append(f"| {a} | " + " | ".join(str(u["matrix"][a][b]) for b in u["classes"]) + " |")
        i = m["confusion"]["intent"]
        L += ["", f"Intent: {len(i['classes'])} classes; full matrix in metrics_report.json. Off-diagonal cells: "
              + ("; ".join(f"{x['label']} -> {x['predicted']} {x['n']}" for x in i["off_diagonal"]) or "none "
                 "(every ticket on the diagonal)") + "."]
    s = m.get("safety") or {}
    if s.get("scanned") is not None:
        L += ["", "## Safety: private data in outbound responses (NFR-04)", "",
              f"Every outbound customer message scanned: {s['scanned']} ({s['sent_answers']} sent answers, the rest "
              f"holding messages), against the private-data patterns and all {s['terms_checked']} customer names "
              f"and ids in the input file. **Messages with private data: {s['messages_with_private_data']}**"
              + ("" if not s["hits"] else ": " + ", ".join(h["ticket_id"] for h in s["hits"])) + "."]
    if m["consistency"]:
        ok = all(x["match"] for x in m["consistency"].values())
        L += ["", "## Consistency with results.jsonl", "",
              f"**{'Every figure matches' if ok else 'MISMATCH'}** between the decision log and results.jsonl.", "",
              "| Figure | Decision log | results.jsonl | Match |", "| --- | --- | --- | --- |"]
        for k, x in m["consistency"].items():
            L.append(f"| {k} | {x['log']} | {x['results']} | {'yes' if x['match'] else 'NO'} |")
    return "\n".join(L) + "\n"


REVIEW_FIELDS = ("ticket_id", "intent", "ticket_text", "reply", "cited_passages", "cited_text",
                 "assessor_1_unsupported_claim", "assessor_1_citation_correct", "assessor_1_notes",
                 "assessor_2_unsupported_claim", "assessor_2_citation_correct", "assessor_2_notes", "agreed")


def write_review_sheet(path: Path, results: list[dict[str, Any]], input_path: Path,
                       chunking: str | None = None) -> int:
    """NFR-08: one row per sent answer, for two assessors. Ticket text is scrubbed of private data."""
    sent = [r for r in results if r["action"] == "auto_respond"]
    if not sent:
        return 0
    texts = {rec.ticket_id: rec.text for rec in load(input_path)}
    passages = {}
    try:
        from src.retrieve import CONFIGS, chunk_docs, load_config, load_docs
        passages = {p.passage_id: p.text for p in chunk_docs(load_docs(), CONFIGS[chunking or load_config().chunking])}
    except Exception:  # noqa: BLE001 - the sheet still works with ids only
        pass
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=REVIEW_FIELDS)
        w.writeheader()
        for r in sent:
            cited = (r.get("generation") or {}).get("cited") or []
            w.writerow({"ticket_id": r["ticket_id"], "intent": r["intent"],
                        "ticket_text": pii.scrub(texts.get(r["ticket_id"], "")), "reply": r.get("reply") or "",
                        "cited_passages": "; ".join(cited),
                        "cited_text": "\n---\n".join(f"[{c}] {passages.get(c, '(text not found)')}" for c in cited)})
    return len(sent)


def write_outputs(out_dir: Path, report: dict[str, Any], results: list[dict[str, Any]] | None) -> None:
    (out_dir / "metrics_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out_dir / "metrics_report.md").write_text(to_markdown(report), encoding="utf-8")
    if results is not None:
        write_review_sheet(out_dir / "answer_review.csv", results, Path(report["run"]["input"]))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-dir", required=True)
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from src.logging_store import DecisionLog

    run_dir = Path(a.run_dir)
    info = json.loads((run_dir / "run_info.json").read_text(encoding="utf-8"))
    log = DecisionLog(info["db_path"], info["run_id"])
    rows = log.rows()
    log.close()
    rp = run_dir / "results.jsonl"
    results = [json.loads(x) for x in rp.read_text(encoding="utf-8").splitlines() if x.strip()] if rp.exists() else None
    report = build_report(rows, info, results)
    write_outputs(run_dir, report, results)
    print(to_markdown(report))
    bad = report["consistency"] and not all(x["match"] for x in report["consistency"].values())
    return 1 if bad or not report["governance"]["decision_log_coverage_ok"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
