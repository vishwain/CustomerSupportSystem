"""Writes monitoring/grafana/dashboards/support_pipeline.json (5b.8). Re-run after changing a panel:
    python monitoring/build_dashboard.py
Grafana loads the file at start (provisioning); an edited dashboard can also be exported from Grafana over it."""

import json
from pathlib import Path

DS = {"type": "prometheus", "uid": "prometheus"}


def tgt(expr, legend="", instant=False, fmt="time_series", ref="A"):
    return {"datasource": DS, "expr": expr, "legendFormat": legend, "instant": instant, "range": not instant,
            "format": fmt, "refId": ref}


def panel(pid, title, typ, x, y, w, h, targets, desc="", unit=None, options=None, field=None):
    defaults = {"unit": unit} if unit else {}
    defaults.update(field or {})
    return {"id": pid, "title": title, "type": typ, "description": desc, "datasource": DS,
            "gridPos": {"x": x, "y": y, "w": w, "h": h}, "targets": targets,
            "fieldConfig": {"defaults": defaults, "overrides": []}, "options": options or {}}


def stat(pid, title, x, expr, unit=None, desc="", thresholds=None, decimals=None):
    f = {"color": {"mode": "thresholds"},
         "thresholds": {"mode": "absolute", "steps": thresholds or [{"color": "blue", "value": None}]}}
    if decimals is not None:
        f["decimals"] = decimals
    return panel(pid, title, "stat", x, 0, 4, 4, [tgt(expr, instant=True)], desc, unit,
                 {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                  "colorMode": "background", "graphMode": "none", "textMode": "value"}, f)


def bars(pid, title, x, y, w, h, targets, desc, fmt_heatmap=False, unit=None, orient="horizontal"):
    for t in targets:
        if fmt_heatmap:
            t["format"] = "heatmap"
    return panel(pid, title, "bargauge", x, y, w, h, targets, desc, unit,
                 {"orientation": orient, "displayMode": "basic", "showUnfilled": True, "valueMode": "color",
                  "namePlacement": "auto", "sizing": "auto", "minVizHeight": 16, "maxVizHeight": 300,
                  "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}},
                 {"color": {"mode": "palette-classic"}, "min": 0})


TOTAL = "sum(support_tickets_total)"
panels = [
    stat(1, "Tickets processed", 0, TOTAL, desc="All tickets the API processed since it started."),
    stat(2, "Auto-resolved", 4, f'sum(support_tickets_total{{outcome="answered"}}) / {TOTAL}', "percentunit",
         "Share of tickets answered automatically (sent without a person).", decimals=1),
    stat(3, "Escalated", 8, f'sum(support_tickets_total{{outcome="escalated"}}) / {TOTAL}', "percentunit",
         "Share of tickets sent to a person.", decimals=1),
    stat(4, "Latency p50 (all requests)", 12,
         "histogram_quantile(0.5, sum by (le) (support_request_latency_seconds_bucket))", "s",
         "Median POST /tickets time since the API started, from the histogram buckets.", decimals=2),
    stat(5, "Latency p95 (all requests)", 16,
         "histogram_quantile(0.95, sum by (le) (support_request_latency_seconds_bucket))", "s",
         "95th percentile POST /tickets time since the API started. Bucket edges limit precision.",
         thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 5}, {"color": "red", "value": 10}],
         decimals=2),
    stat(6, "Kill switch", 20, "max(support_automation_paused)", desc="1 = automation paused: every ticket escalates.",
         thresholds=[{"color": "green", "value": None}, {"color": "red", "value": 1}]),
    # 1. tickets by channel and outcome
    bars(7, "1. Tickets by channel and outcome", 0, 4, 12, 9,
         [tgt('sum by (channel, outcome) (support_tickets_total)', "{{channel}} - {{outcome}}", instant=True)],
         "support_tickets_total by channel and outcome (answered = sent automatically, escalated = to a person)."),
    # 2. auto vs escalated
    panel(8, "2. Auto-resolved vs escalated", "piechart", 12, 4, 6, 9,
          [tgt("sum by (outcome) (support_tickets_total)", "{{outcome}}", instant=True)],
          "All tickets since the API started.", None,
          {"pieType": "donut", "displayLabels": ["percent", "value"],
           "legend": {"displayMode": "list", "placement": "bottom", "values": ["value", "percent"]},
           "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}},
          {"color": {"mode": "palette-classic"}}),
    panel(9, "2b. Tickets per minute by outcome", "timeseries", 18, 4, 6, 9,
          [tgt("sum by (outcome) (increase(support_tickets_total[1m]))", "{{outcome}}")],
          "Throughput over time.", "short",
          {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}},
          {"custom": {"drawStyle": "bars", "fillOpacity": 60, "stacking": {"mode": "normal"}},
           "color": {"mode": "palette-classic"}}),
    # 3. latency histogram -> p50/p95
    panel(10, "3. Request latency p50 and p95", "timeseries", 0, 13, 12, 9,
          [tgt("histogram_quantile(0.5, sum by (le) (rate(support_request_latency_seconds_bucket[2m])))", "p50",
               ref="A"),
           tgt("histogram_quantile(0.95, sum by (le) (rate(support_request_latency_seconds_bucket[2m])))", "p95",
               ref="B"),
           tgt('histogram_quantile(0.95, sum by (le) (rate(support_request_latency_seconds_bucket{outcome="answered"}[2m])))',
               "p95 answered (includes provider)", ref="C")],
          "From support_request_latency_seconds (histogram), 2-minute window. Answered tickets include the model "
          "call; escalations before Generate do not.", "s",
          {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}},
          {"custom": {"lineWidth": 2, "fillOpacity": 10, "spanNulls": True}, "color": {"mode": "palette-classic"}}),
    # 4. guardrail activations
    bars(11, "4. Guardrail activations", 12, 13, 12, 9,
         [tgt("sum by (guardrail, stage, result) (support_guardrail_activations_total)",
              "{{guardrail}} ({{stage}}, {{result}})", instant=True)],
         "route = escalated before any model call; validate = output blocked (style only warns)."),
    # 5. confidence histogram
    bars(12, "5. Intent confidence (histogram)", 0, 22, 12, 9,
         [tgt("sum by (le) (support_intent_confidence_bucket)", "{{le}}", instant=True)],
         "Tickets per confidence bucket, upper edge shown. Automatic answers need 0.95 or more "
         "(the 0.99 and 1.0 buckets).", fmt_heatmap=True, orient="vertical"),
    bars(13, "Escalation reasons (rule fired)", 12, 22, 12, 9,
         [tgt('sum by (rule) (support_rule_fired_total{rule!="none"})', "{{rule}}", instant=True)],
         "Why tickets went to a person."),
]

dash = {"uid": "cloudserve-support", "title": "CloudServe support pipeline", "tags": ["support", "5b.8"],
        "timezone": "browser", "schemaVersion": 41, "version": 1, "editable": True, "refresh": "10s",
        "time": {"from": "now-30m", "to": "now"}, "panels": panels,
        "description": "Prometheus metrics from src/api.py /metrics (5b.8)."}
out = Path(__file__).parent / "grafana" / "dashboards" / "support_pipeline.json"
out.write_text(json.dumps(dash, indent=2) + "\n", encoding="utf-8")
print(f"wrote {out} ({len(panels)} panels)")
