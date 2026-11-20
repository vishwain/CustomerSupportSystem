# Human review sample (5.18)

Run `20261120T025358Z_validation_tickets_056a` (5.17 official run), input `data/validation_tickets.json`.

How it was drawn (rule fixed before scoring, script `evaluation/review_sample.py`):

1. Every escalated ticket: 29. This includes every guardrail-blocked ticket (2: VAL-0036, VAL-0050), whose blocked draft is reviewed.
2. A random sample of the automatic answers: 30 of 51, `random.Random(42).sample(sorted ids, 30)`, to reach 59 items.
3. Total: **59** of 80 responses.

Automatic answers sampled: VAL-0004, VAL-0005, VAL-0011, VAL-0012, VAL-0013, VAL-0016, VAL-0023, VAL-0024, VAL-0025, VAL-0028, VAL-0033, VAL-0039, VAL-0041, VAL-0047, VAL-0051, VAL-0053, VAL-0056, VAL-0057, VAL-0058, VAL-0060, VAL-0061, VAL-0064, VAL-0065, VAL-0069, VAL-0071, VAL-0073, VAL-0074, VAL-0075, VAL-0077, VAL-0080

Escalated: VAL-0002, VAL-0003, VAL-0006, VAL-0007, VAL-0009, VAL-0014, VAL-0015, VAL-0017, VAL-0020, VAL-0026, VAL-0029, VAL-0030, VAL-0031, VAL-0032, VAL-0035, VAL-0036, VAL-0037, VAL-0038, VAL-0043, VAL-0048, VAL-0049, VAL-0050, VAL-0054, VAL-0066, VAL-0067, VAL-0068, VAL-0076, VAL-0078, VAL-0079
