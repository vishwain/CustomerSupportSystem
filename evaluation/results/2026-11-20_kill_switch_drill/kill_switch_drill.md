# Kill switch drill (5b.6): FAIL

Run `20261120T132424Z_kill_switch_drill_396f`, 2026-11-20 13:25 UTC. Real pipeline and live provider; the switch flipped with `src.killswitch` on the real `config/runtime.json`. Log: `decisions.db` here; switch changes: `killswitch_audit.jsonl`.

| Phase | Ticket | Final action | Rule | Provider requests | Reply sent | Draft kept for agent | ms from flip |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 OFF | VAL-0001 | auto_respond | none | 0 (cache) | yes | no |  |
| 2 IN FLIGHT | VAL-0004 | escalate | kill_switch_at_send | 0 (cache) | no | yes |  |
| 3 ON | VAL-0001 | escalate | none | 0 | no | no | 133 |
| 3 ON | VAL-0004 | escalate | none | 0 | no | no |  |
| 3 ON | VAL-0005 | escalate | kill_switch | 0 | no | no |  |
| 4 OFF | VAL-0005 | escalate | none | 0 | no | no | 290 |

Reasons logged:

- 1 OFF VAL-0001: Automatic answer: no rule fired; intent api_key_issue confidence 1.00 >= threshold 0.95; 2 passage(s) passed the cutoff. Passed Validate (all blocking checks passed; warnings: FR-20: 21.0 words per sentence on average, longest 25).
- 2 IN FLIGHT VAL-0004: Automation paused while this ticket was in flight; the validated answer was not sent and is attached as a draft for an agent.
- 3 ON VAL-0001: Final decision row could not be written; fail closed, nothing sent.
- 3 ON VAL-0004: Final decision row could not be written; fail closed, nothing sent.
- 3 ON VAL-0005: automation paused
- 4 OFF VAL-0005: Final decision row could not be written; fail closed, nothing sent.

What the customer received while ON (holding message):

> 

Checks:

- [ ] ON: every ticket escalated by the kill switch
- [x] ON: no provider request
- [x] ON: no reply sent; customer gets the holding message
- [x] IN FLIGHT: not sent; escalated at send time
- [x] IN FLIGHT: validated answer kept as a draft for the agent
- [ ] Nothing dropped: one final row per ticket processed
- [x] Switch OFF at the end

Reconciliation: 6 tickets processed, 3 final rows.
