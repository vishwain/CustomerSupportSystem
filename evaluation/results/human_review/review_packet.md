# Review packet (5.18)

Read RUBRIC.md first. Score each item in your own sheet only; do not open the other assessor's sheet.
Ticket text has private data replaced by [REDACTED:...]. Sentence numbers match the sheet counts.

---

## 1. VAL-0002 (escalated)

Channel chat; predicted intent unclear_request (1.00); route escalate; final escalate; rule `must_escalate_intent:unclear_request`.

**Ticket**

> Following up on my previous message. Any update?

**Customer received (holding message)**

```
Thank you for contacting CloudServe Support. A member of our support team will look at your request and reply to you.
```

**Escalation package for the agent**

- Summary: unclear_request (1.00), medium urgency, chat: (no subject)
- Restatement: (no subject): Following up on my previous message.
- Reason: intent unclear_request must always escalate (FR-12) Also: no supporting passage passed the relevance cutoff.

**Sources retrieved for the agent**: none passed the cutoff

---

## 2. VAL-0003 (escalated)

Channel docs_comment; predicted intent unclear_request (1.00); route escalate; final escalate; rule `must_escalate_intent:unclear_request`.

**Ticket**

> It is not working
> 
> nothing is loading properly today. Can someone look into this? kindly check and revert.

**Customer received (holding message)**

```
Thank you for contacting CloudServe Support. A member of our support team will look at your request and reply to you.
```

**Escalation package for the agent**

- Summary: unclear_request (1.00), high urgency, docs_comment: It is not working
- Restatement: It is not working: nothing is loading properly today.
- Reason: intent unclear_request must always escalate (FR-12) Also: no supporting passage passed the relevance cutoff.

**Sources retrieved for the agent**: none passed the cutoff

---

## 3. VAL-0004 (answered)

Channel email; predicted intent authentication_failure (1.00); route auto_respond; final auto_respond; rule `none`.

**Ticket**

> MFA code keeps getting rejected
> 
> my authenticator app codes are being rejected every time. i am having tried generating new ones several times.

**Sent to the customer**

```
This is an automated reply from CloudServe Support. It is based on our help articles listed below.

Hello,

Check that automatic time synchronisation is enabled on the device generating the code.

If this does not solve the problem, reply to this message and a member of our support team will help you.

Sources:
- Multi-factor authentication setup and recovery (DOC-AUTH-002), reviewed today
```

**Answer sentences and their citations**

1. Check that automatic time synchronisation is enabled on the device generating the code.  [cites: DOC-AUTH-002#c01]

**Cited passages**

*DOC-AUTH-002#c01* (Multi-factor authentication setup and recovery)

> ## Resolution
> 
> 1. Ask the user to check that automatic time synchronisation is enabled on the device generating the code. Drift is the most common cause by a wide margin.
> 2. If the device is lost, the user should sign in with one of their recovery codes and then re-enrol a new device from the security page.
> 3. Where no recovery codes are available, an account administrator can reset multi-factor authentication for that user from the team members page.
> 4. If the user is the sole administrator and has no recovery codes, identity verification through support is required and takes up to one business day.
> 
> ## Notes
> 
> Support cannot disable multi-factor authentication without identity verification, regardless of urgency.

---

## 4. VAL-0005 (answered)

Channel chat; predicted intent api_usage_question (1.00); route auto_respond; final auto_respond; rule `none`.

**Ticket**

> Our cursor seems to stop working partway through a long iteration. Is there an expiry we should be handling?

**Sent to the customer**

```
This is an automated reply from CloudServe Support. It is based on our help articles listed below.

Hello,

Use cursor pagination for anything that may change while you iterate, and stop when the next_cursor value is null. Pass the next_cursor value from each response as the cursor parameter of the following request. Keep page size at or below two hundred; larger requests are rejected. Cursors expire after one hour; long-running iterations should handle expiry by restarting from a recorded checkpoint.

If this does not solve the problem, reply to this message and a member of our support team will help you.

Sources:
- Pagination and handling large result sets (DOC-API-002), reviewed today
```

**Answer sentences and their citations**

1. Use cursor pagination for anything that may change while you iterate, and stop when the next_cursor value is null.  [cites: DOC-API-002#c01]
2. Pass the next_cursor value from each response as the cursor parameter of the following request.  [cites: DOC-API-002#c01]
3. Keep page size at or below two hundred; larger requests are rejected.  [cites: DOC-API-002#c01]
4. Cursors expire after one hour; long-running iterations should handle expiry by restarting from a recorded checkpoint.  [cites: DOC-API-002#c01]

**Cited passages**

*DOC-API-002#c01* (Pagination and handling large result sets)

> ## Resolution
> 
> 1. Use cursor pagination for anything that may change while you iterate. Offset pagination will skip or repeat records when items are inserted mid-iteration.
> 2. Pass the next_cursor value from each response as the cursor parameter of the following request, and stop when it is null.
> 3. Keep page size at or below two hundred. Larger requests are rejected rather than truncated.
> 4. For very large extracts, use the export endpoint, which runs asynchronously and returns a download link.
> 
> ## Notes
> 
> Cursors expire after one hour. Long-running iterations should handle expiry by restarting from a recorded checkpoint.

---

## 5. VAL-0006 (escalated)

Channel email; predicted intent authentication_failure (1.00); route escalate; final escalate; rule `no_retrieval_hit`.

**Ticket**

> MFA code keeps getting rejected
> 
> I have been trying to sign in for the last two hours and keep getting an invalid credentials message. I am certain the password is correct because I use a password manager. Nothing has changed at our end that I am aware of.

**Customer received (holding message)**

```
Thank you for contacting CloudServe Support. A member of our support team will look at your request and reply to you.
```

**Escalation package for the agent**

- Summary: authentication_failure (1.00), medium urgency, email: MFA code keeps getting rejected
- Restatement: MFA code keeps getting rejected: I have been trying to sign in for the last two hours and keep getting an invalid credentials message.
- Reason: no supporting passage: nothing passed the relevance cutoff (No passage at or above cutoff 0.51; best was DOC-AUTH-002#c00 at 0.51.); escalated without a draft or a model call

**Sources retrieved for the agent**: none passed the cutoff

---

## 6. VAL-0007 (escalated)

Channel chat; predicted intent unclear_request (1.00); route escalate; final escalate; rule `must_escalate_intent:unclear_request`.

**Ticket**

> We have a problem and need someone to call us urgently.

**Customer received (holding message)**

```
Thank you for contacting CloudServe Support. A member of our support team will look at your request and reply to you.
```

**Escalation package for the agent**

- Summary: unclear_request (1.00), medium urgency, chat: (no subject)
- Restatement: (no subject): We have a problem and need someone to call us urgently.
- Reason: intent unclear_request must always escalate (FR-12) Also: no supporting passage passed the relevance cutoff.

**Sources retrieved for the agent**: none passed the cutoff

---

## 7. VAL-0009 (escalated)

Channel docs_comment; predicted intent compliance_request (1.00); route escalate; final escalate; rule `must_escalate_intent:compliance_request`.

**Ticket**

> Retention period question
> 
> We need to demonstrate that read access to customer records is logged. I cannot find these events in the audit log.

**Customer received (holding message)**

```
Thank you for contacting CloudServe Support. A member of our support team will look at your request and reply to you.
```

**Escalation package for the agent**

- Summary: compliance_request (1.00), medium urgency, docs_comment: Retention period question
- Restatement: Retention period question: We need to demonstrate that read access to customer records is logged.
- Reason: intent compliance_request must always escalate (FR-12)

**Sources retrieved for the agent**

*DOC-SEC-003#c00* (Audit logging and compliance evidence)

> # Audit logging and compliance evidence
> 
> **Applies to:** Business and Enterprise plans
> 
> ## Symptoms
> 
> - An auditor has requested access records
> - An event that should be logged cannot be found
> - Log retention is shorter than a policy requires
> 
> ## Common causes
> 
> - The event predates the retention window
> - The event type is not covered by the audit log
> - The organisation is on a plan with shorter retention
> 
> ## Resolution

*DOC-SEC-003#c01* (Audit logging and compliance evidence)

> ## Resolution
> 
> 1. Filter the audit log by actor, resource and date range. Every administrative action carries the user, the address and the outcome.
> 2. Export the relevant period to object storage for anything needed beyond the retention window. Exports are not subject to retention limits.
> 3. Configure continuous export to your own storage if a policy requires retention longer than the plan provides.
> 4. Note that read access to resources is not logged on Business plans, only administrative and configuration changes.
> 
> ## Notes
> 
> Audit log exports are themselves audited, including the fields selected and the destination.

---

## 8. VAL-0011 (answered)

Channel forum; predicted intent rollback_request (1.00); route auto_respond; final auto_respond; rule `none`.

**Ticket**

> How do I revert to the previous revision
> 
> We shipped a release yesterday morning that has broken checkout for a portion of our customers. We need to get back to the previous version quickly. What is the fastest safe route?

**Sent to the customer**

```
This is an automated reply from CloudServe Support. It is based on our help articles listed below.

Hello,

Open the revisions page for the service and identify the last revision that was healthy. Select roll back on that revision. Traffic moves within roughly thirty seconds and no rebuild takes place. If the release included a database migration, roll the migration back before the service, or the older code will encounter a schema it does not expect. Record the incident and the reason for the rollback before deploying a fix, while the detail is still fresh.

If this does not solve the problem, reply to this message and a member of our support team will help you.

Sources:
- Rolling back a failed release (DOC-DEPLOY-002), reviewed today
```

**Answer sentences and their citations**

1. Open the revisions page for the service and identify the last revision that was healthy.  [cites: DOC-DEPLOY-002#c01]
2. Select roll back on that revision. Traffic moves within roughly thirty seconds and no rebuild takes place.  [cites: DOC-DEPLOY-002#c01]
3. If the release included a database migration, roll the migration back before the service, or the older code will encounter a schema it does not expect.  [cites: DOC-DEPLOY-002#c01]
4. Record the incident and the reason for the rollback before deploying a fix, while the detail is still fresh.  [cites: DOC-DEPLOY-002#c01]

**Cited passages**

*DOC-DEPLOY-002#c01* (Rolling back a failed release)

> ## Resolution
> 
> 1. Open the revisions page for the service and identify the last revision that was healthy.
> 2. Select roll back on that revision. Traffic moves within roughly thirty seconds and no rebuild takes place.
> 3. If the release included a database migration, roll the migration back before the service, or the older code will encounter a schema it does not expect.
> 4. Record the incident and the reason for the rollback before deploying a fix, while the detail is still fresh.
> 
> ## Notes
> 
> Rollback restores the container image and its configuration together. It does not restore data.

---

## 9. VAL-0012 (answered)

Channel email; predicted intent rollback_request (1.00); route auto_respond; final auto_respond; rule `none`.

**Ticket**

> Need to roll back the latest release
> 
> How do I revert to an earlier revision? The release we put out this morning is causing errors and I would rather roll back than try to fix forward.

**Sent to the customer**

```
This is an automated reply from CloudServe Support. It is based on our help articles listed below.

Hello,

Open the revisions page for the service and identify the last revision that was healthy. Select roll back on that revision. Traffic moves within roughly thirty seconds and no rebuild takes place. If the release included a database migration, roll the migration back before the service, or the older code will encounter a schema it does not expect. Record the incident and the reason for the rollback before deploying a fix, while the detail is still fresh.

If this does not solve the problem, reply to this message and a member of our support team will help you.

Sources:
- Rolling back a failed release (DOC-DEPLOY-002), reviewed today
```

**Answer sentences and their citations**

1. Open the revisions page for the service and identify the last revision that was healthy.  [cites: DOC-DEPLOY-002#c01]
2. Select roll back on that revision. Traffic moves within roughly thirty seconds and no rebuild takes place.  [cites: DOC-DEPLOY-002#c01]
3. If the release included a database migration, roll the migration back before the service, or the older code will encounter a schema it does not expect.  [cites: DOC-DEPLOY-002#c01]
4. Record the incident and the reason for the rollback before deploying a fix, while the detail is still fresh.  [cites: DOC-DEPLOY-002#c01]

**Cited passages**

*DOC-DEPLOY-002#c01* (Rolling back a failed release)

> ## Resolution
> 
> 1. Open the revisions page for the service and identify the last revision that was healthy.
> 2. Select roll back on that revision. Traffic moves within roughly thirty seconds and no rebuild takes place.
> 3. If the release included a database migration, roll the migration back before the service, or the older code will encounter a schema it does not expect.
> 4. Record the incident and the reason for the rollback before deploying a fix, while the detail is still fresh.
> 
> ## Notes
> 
> Rollback restores the container image and its configuration together. It does not restore data.

---

## 10. VAL-0013 (answered)

Channel docs_comment; predicted intent billing_query (1.00); route auto_respond; final auto_respond; rule `none`.

**Ticket**

> Question about this month's charges
> 
> There are charges on our invoice for a service I do not believe we use. Could you explain what these relate to?

**Sent to the customer**

```
This is an automated reply from CloudServe Support. It is based on our help articles listed below.

Hello,

Open the usage breakdown for the period to see charges itemised by service and environment. Look for resources in staging or development environments that may be billed at the same rate as production. Check the billing period dates at the top of the invoice, as the period runs from the anniversary of the subscription date rather than the first of the month.

If this does not solve the problem, reply to this message and a member of our support team will help you.

Sources:
- Understanding your invoice and usage breakdown (DOC-BILL-001), reviewed today
```

**Answer sentences and their citations**

1. Open the usage breakdown for the period to see charges itemised by service and environment.  [cites: DOC-BILL-001#c01]
2. Look for resources in staging or development environments that may be billed at the same rate as production.  [cites: DOC-BILL-001#c01]
3. Check the billing period dates at the top of the invoice, as the period runs from the anniversary of the subscription date rather than the first of the month.  [cites: DOC-BILL-001#c01]

**Cited passages**

*DOC-BILL-001#c01* (Understanding your invoice and usage breakdown)

> ## Resolution
> 
> 1. Open the usage breakdown for the period, which itemises charges by service and by environment.
> 2. Look for resources in staging or development environments, which are billed at the same rate as production.
> 3. Check the billing period dates at the top of the invoice. The period runs from the anniversary of the subscription date.
> 4. Set a usage alert on the billing page so that unexpected accrual is noticed during the period rather than at the end of it.
> 
> ## Notes
> 
> Invoices are finalised three days after the period ends. Adjustments requested before finalisation appear on the same invoice.

---

## 11. VAL-0014 (escalated)

Channel email; predicted intent rollback_request (1.00); route escalate; final escalate; rule `no_retrieval_hit`.

**Ticket**

> Bad release in production
> 
> we shipped a release around 14:00 yesterday that has broken checkout for portion of our customers. We need to get back to the previous version quickly. waiting for your reply.

**Customer received (holding message)**

```
Thank you for contacting CloudServe Support. A member of our support team will look at your request and reply to you.
```

**Escalation package for the agent**

- Summary: rollback_request (1.00), high urgency, email: Bad release in production
- Restatement: Bad release in production: we shipped a release around 14:00 yesterday that has broken checkout for portion of our customers.
- Reason: no supporting passage: nothing passed the relevance cutoff (No passage at or above cutoff 0.51; best was DOC-DEPLOY-002#c00 at 0.48.); escalated without a draft or a model call

**Sources retrieved for the agent**: none passed the cutoff

---

## 12. VAL-0015 (escalated)

Channel forum; predicted intent unclear_request (1.00); route escalate; final escalate; rule `must_escalate_intent:unclear_request`.

**Ticket**

> Urgent help needed
> 
> We have a problem and need someone to call us urgently.

**Customer received (holding message)**

```
Thank you for contacting CloudServe Support. A member of our support team will look at your request and reply to you.
```

**Escalation package for the agent**

- Summary: unclear_request (1.00), medium urgency, forum: Urgent help needed
- Restatement: Urgent help needed: We have a problem and need someone to call us urgently.
- Reason: intent unclear_request must always escalate (FR-12) Also: no supporting passage passed the relevance cutoff.

**Sources retrieved for the agent**: none passed the cutoff

---

## 13. VAL-0016 (answered)

Channel chat; predicted intent performance_degradation (1.00); route auto_respond; final auto_respond; rule `none`.

**Ticket**

> The service is noticeably slow during our afternoon peak and fine the rest of the day. We have autoscaling enabled so I expected it to cope.

**Sent to the customer**

```
This is an automated reply from CloudServe Support. It is based on our help articles listed below.

Hello,

Compare median and 95th percentile latency on the metrics page to check for contention or queueing. Check memory utilisation across instances; sustained utilisation above eighty per cent typically shows up as latency before failure. Review the dependency timing breakdown on the trace view to identify whether time is spent in your service or waiting on another dependency. Adjust the autoscaling policy to scale on request count rather than processor utilisation for request-bound services. Set a minimum instance count above zero for latency-sensitive services to avoid cold starts on the first request.

If this does not solve the problem, reply to this message and a member of our support team will help you.

Sources:
- Diagnosing elevated response latency (DOC-PERF-001), reviewed today
- Autoscaling behaviour and instance limits (DOC-PERF-002), reviewed today
```

**Answer sentences and their citations**

1. Compare median and 95th percentile latency on the metrics page to check for contention or queueing.  [cites: DOC-PERF-001#c01]
2. Check memory utilisation across instances; sustained utilisation above eighty per cent typically shows up as latency before failure.  [cites: DOC-PERF-001#c01]
3. Review the dependency timing breakdown on the trace view to identify whether time is spent in your service or waiting on another dependency.  [cites: DOC-PERF-001#c01]
4. Adjust the autoscaling policy to scale on request count rather than processor utilisation for request-bound services.  [cites: DOC-PERF-002#c01]
5. Set a minimum instance count above zero for latency-sensitive services to avoid cold starts on the first request.  [cites: DOC-PERF-002#c01]

**Cited passages**

*DOC-PERF-001#c01* (Diagnosing elevated response latency)

> ## Resolution
> 
> 1. Compare median and 95th percentile latency on the metrics page. A large gap points to contention or queueing rather than a uniformly slower service.
> 2. Check memory utilisation across instances. Sustained utilisation above eighty per cent typically shows up as latency before it shows up as failure.
> 3. Review the dependency timing breakdown on the trace view to identify whether the time is being spent in your service or waiting on another.
> 4. Adjust the autoscaling policy if load is predictable. Scaling on request count responds sooner than scaling on processor utilisation.
> 
> ## Notes
> 
> Cold starts affect the first request to a new instance. Frequent scaling events will therefore raise the 95th percentile even when the service itself is healthy.

*DOC-PERF-002#c01* (Autoscaling behaviour and instance limits)

> ## Resolution
> 
> 1. Check whether the service is sitting at its configured maximum. Scaling stops there regardless of load.
> 2. Choose a scaling metric that reflects the pressure you actually face. Request concurrency reacts faster than processor utilisation for request-bound services.
> 3. Set the cooldown longer than your startup time so that new instances are counted before another scaling decision is taken.
> 4. Set a minimum instance count above zero for latency-sensitive services to avoid cold starts on the first request.
> 
> ## Notes
> 
> Scaling decisions are evaluated every fifteen seconds. Very short traffic spikes will finish before scaling responds.

---

## 14. VAL-0017 (escalated)

Channel docs_comment; predicted intent unclear_request (1.00); route escalate; final escalate; rule `must_escalate_intent:unclear_request`.

**Ticket**

> Question
> 
> It is not working. Please help.

**Customer received (holding message)**

```
Thank you for contacting CloudServe Support. A member of our support team will look at your request and reply to you.
```

**Escalation package for the agent**

- Summary: unclear_request (1.00), medium urgency, docs_comment: Question
- Restatement: Question: It is not working.
- Reason: intent unclear_request must always escalate (FR-12) Also: no supporting passage passed the relevance cutoff.

**Sources retrieved for the agent**: none passed the cutoff

---

## 15. VAL-0020 (escalated)

Channel email; predicted intent feature_request (1.00); route escalate; final escalate; rule `must_escalate_intent:feature_request`.

**Ticket**

> Would like custom retention
> 
> Are staged rollouts on the roadmap? We would like to move traffic gradually rather than all at once.

**Customer received (holding message)**

```
Thank you for contacting CloudServe Support. A member of our support team will look at your request and reply to you.
```

**Escalation package for the agent**

- Summary: feature_request (1.00), low urgency, email: Would like custom retention
- Restatement: Would like custom retention: Are staged rollouts on the roadmap?
- Reason: intent feature_request must always escalate (FR-12) Also: no supporting passage passed the relevance cutoff.

**Sources retrieved for the agent**: none passed the cutoff

---

## 16. VAL-0023 (answered)

Channel email; predicted intent onboarding (1.00); route auto_respond; final auto_respond; rule `none`.

**Ticket**

> Migrating our app across
> 
> We have just signed up and I am not sure where to start. We have a containerised application and would like to get it deployed.

**Sent to the customer**

```
This is an automated reply from CloudServe Support. It is based on our help articles listed below.

Hello,

Externalise configuration before migrating, moving anything read from a file on disk to environment variables or secrets. Identify local state such as uploaded files or session data and move it to object storage or the managed database first. Run in parallel with the existing deployment and shift a small share of traffic before committing to the move. Plan the database migration separately from the application migration to make any failure easier to diagnose.

If this does not solve the problem, reply to this message and a member of our support team will help you.

Sources:
- Migrating an existing application to CloudServe (DOC-ONB-002), reviewed today
```

**Answer sentences and their citations**

1. Externalise configuration before migrating, moving anything read from a file on disk to environment variables or secrets.  [cites: DOC-ONB-002#c01]
2. Identify local state such as uploaded files or session data and move it to object storage or the managed database first.  [cites: DOC-ONB-002#c01]
3. Run in parallel with the existing deployment and shift a small share of traffic before committing to the move.  [cites: DOC-ONB-002#c01]
4. Plan the database migration separately from the application migration to make any failure easier to diagnose.  [cites: DOC-ONB-002#c01]

**Cited passages**

*DOC-ONB-002#c01* (Migrating an existing application to CloudServe)

> ## Resolution
> 
> 1. Externalise configuration before migrating. Anything read from a file on disk should move to environment variables or secrets.
> 2. Identify local state such as uploaded files or session data and move it to object storage or the managed database first.
> 3. Run in parallel with the existing deployment and shift a small share of traffic before committing to the move.
> 4. Plan the database migration separately from the application migration; attempting both at once makes any failure hard to diagnose.
> 
> ## Notes
> 
> Applications that write to the local filesystem will lose that data on every deployment and every scaling event.

---

## 17. VAL-0024 (answered)

Channel chat; predicted intent api_key_issue (1.00); route auto_respond; final auto_respond; rule `none`.

**Ticket**

> A key can read fine but every write returns a permission error. I created it myself and I thought I gave it full access.

**Sent to the customer**

```
This is an automated reply from CloudServe Support. It is based on our help articles listed below.

Hello,

Check the API keys page for the key's status and expiry to see if it was revoked or reached its configured expiry. Review the scopes attached to the key; read-only keys cannot write, and project-scoped keys cannot reach organisation endpoints.

If this does not solve the problem, reply to this message and a member of our support team will help you.

Sources:
- API key rotation and scope management (DOC-AUTH-004), reviewed today
```

**Answer sentences and their citations**

1. Check the API keys page for the key's status and expiry to see if it was revoked or reached its configured expiry.  [cites: DOC-AUTH-004#c01]
2. Review the scopes attached to the key; read-only keys cannot write, and project-scoped keys cannot reach organisation endpoints.  [cites: DOC-AUTH-004#c01]

**Cited passages**

*DOC-AUTH-004#c01* (API key rotation and scope management)

> ## Resolution
> 
> 1. Check the API keys page for the key's status and expiry. Revoked and expired keys are listed with the date and the user who acted.
> 2. Review the scopes attached to the key. Read-only keys cannot write, and project-scoped keys cannot reach organisation endpoints.
> 3. To rotate without downtime, create the replacement key first, deploy it, confirm traffic has moved, then revoke the old key.
> 4. If a key has been exposed publicly, revoke it immediately rather than waiting for the rotation window.
> 
> ## Notes
> 
> Keys issued to individual users are removed when that user is deleted. Use service accounts for anything running in production.

---

## 18. VAL-0025 (answered)

Channel chat; predicted intent deployment_failure (1.00); route auto_respond; final auto_respond; rule `none`.

**Ticket**

> every deployment fails at health check stage. i am having increase timeout twice already and it makes no difference. kindly check and revert.

**Sent to the customer**

```
This is an automated reply from CloudServe Support. It is based on our help articles listed below.

Hello,

Confirm the container is listening on the port declared in the service definition. Increase the initial delay to thirty seconds if the application needs time to warm up before it can answer. Compare the environment variables present in the deployment against those the application requires. Inspect the container logs from the failed revision rather than the running one.

If this does not solve the problem, reply to this message and a member of our support team will help you.

Sources:
- Container deployments failing during the health check phase (DOC-DEPLOY-001), reviewed today
```

**Answer sentences and their citations**

1. Confirm the container is listening on the port declared in the service definition.  [cites: DOC-DEPLOY-001#c01]
2. Increase the initial delay to thirty seconds if the application needs time to warm up before it can answer.  [cites: DOC-DEPLOY-001#c01]
3. Compare the environment variables present in the deployment against those the application requires.  [cites: DOC-DEPLOY-001#c01]
4. Inspect the container logs from the failed revision rather than the running one.  [cites: DOC-DEPLOY-001#c01]

**Cited passages**

*DOC-DEPLOY-001#c01* (Container deployments failing during the health check phase)

> ## Resolution
> 
> 1. Confirm the container is listening on the port declared in the service definition. A mismatch here produces a health check failure that looks like a timeout.
> 2. Increase the initial delay if the application needs time to warm up before it can answer. Thirty seconds is a reasonable starting point for services that load models or caches.
> 3. Compare the environment variables present in the deployment against those the application requires. Missing configuration frequently causes a silent startup failure.
> 4. Inspect the container logs from the failed revision rather than the running one; the rollback replaces the logs shown by default.
> 
> ## Notes

---

## 19. VAL-0026 (escalated)

Channel email; predicted intent data_residency (1.00); route escalate; final escalate; rule `must_escalate_intent:data_residency`.

**Ticket**

> Need data to stay in the EU
> 
> we need our data to remain within EU for contract we are signing. Our organisation created some time ago and i not sure which region it is in. please do the needful.

**Customer received (holding message)**

```
Thank you for contacting CloudServe Support. A member of our support team will look at your request and reply to you.
```

**Escalation package for the agent**

- Summary: data_residency (1.00), medium urgency, email: Need data to stay in the EU
- Restatement: Need data to stay in the EU: we need our data to remain within EU for contract we are signing.
- Reason: intent data_residency must always escalate (FR-12)

**Sources retrieved for the agent**

*DOC-DATA-003#c00* (Data residency and regional storage)

> # Data residency and regional storage
> 
> **Applies to:** Business and Enterprise plans
> 
> ## Symptoms
> 
> - A customer requires data to remain in a specific region
> - Latency is high for users far from the primary region
> - A compliance review has asked where data is held
> 
> ## Common causes
> 
> - The organisation was created in a region that no longer suits the requirement
> - Read traffic is being served from the primary region only
> - Backups are replicated to a second region by default
> 
> ## Resolution

*DOC-DATA-003#c01* (Data residency and regional storage)

> ## Resolution
> 
> 1. Check the region shown on the organisation settings page. This is fixed at creation and determines where primary data is stored.
> 2. Enable read replicas in additional regions to reduce latency for distant users without moving primary storage.
> 3. Review the backup replication setting if a single-region requirement applies, since cross-region replication is enabled by default.
> 4. Migrating an organisation between regions requires a planned migration with support and involves a maintenance window.
> 
> ## Notes
> 
> Metadata such as account names and billing records is stored centrally regardless of the data region.

---

## 20. VAL-0028 (answered)

Channel email; predicted intent deployment_failure (1.00); route auto_respond; final auto_respond; rule `none`.

**Ticket**

> Deployment rolls back every time
> 
> builds that work last week are now fail during dependency resolution. we having not change our code at all.

**Sent to the customer**

```
This is an automated reply from CloudServe Support. It is based on our help articles listed below.

Hello,

Pin your dependencies with exact versions and commit the lock file. Compare the runtime version declared in your build configuration against the version you use locally. Clear the build cache from the settings page and trigger a fresh build to rule out a corrupted artefact.

If this does not solve the problem, reply to this message and a member of our support team will help you.

Sources:
- Build failures caused by dependency resolution (DOC-DEPLOY-003), reviewed today
```

**Answer sentences and their citations**

1. Pin your dependencies with exact versions and commit the lock file.  [cites: DOC-DEPLOY-003#c01]
2. Compare the runtime version declared in your build configuration against the version you use locally.  [cites: DOC-DEPLOY-003#c01]
3. Clear the build cache from the settings page and trigger a fresh build to rule out a corrupted artefact.  [cites: DOC-DEPLOY-003#c01]

**Cited passages**

*DOC-DEPLOY-003#c01* (Build failures caused by dependency resolution)

> ## Resolution
> 
> 1. Pin your dependencies with exact versions and commit the lock file. Unpinned dependencies are the cause in the large majority of cases of this kind.
> 2. Compare the runtime version declared in your build configuration against the version you use locally.
> 3. Clear the build cache from the settings page and trigger a fresh build to rule out a corrupted artefact.
> 4. If a specific dependency is failing to resolve, check whether its registry is reachable from the build network.
> 
> ## Notes
> 
> Build logs retain the full resolution output for thirty days, which is usually enough to identify which version changed.

---

## 21. VAL-0029 (escalated)

Channel chat; predicted intent onboarding (1.00); route escalate; final escalate; rule `no_retrieval_hit`.

**Ticket**

> Could you point me at the right starting place? I have created an account but the console has more in it than I expected.

**Customer received (holding message)**

```
Thank you for contacting CloudServe Support. A member of our support team will look at your request and reply to you.
```

**Escalation package for the agent**

- Summary: onboarding (1.00), medium urgency, chat: (no subject)
- Restatement: (no subject): Could you point me at the right starting place?
- Reason: no supporting passage: nothing passed the relevance cutoff (No passage at or above cutoff 0.51; best was DOC-ONB-001#c01 at 0.44.); escalated without a draft or a model call

**Sources retrieved for the agent**: none passed the cutoff

---

## 22. VAL-0030 (escalated)

Channel email; predicted intent feature_request (1.00); route escalate; final escalate; rule `must_escalate_intent:feature_request`.

**Ticket**

> Feature request: staged rollouts
> 
> Are staged rollouts on the roadmap? We would like to move traffic gradually rather than all at once.

**Customer received (holding message)**

```
Thank you for contacting CloudServe Support. A member of our support team will look at your request and reply to you.
```

**Escalation package for the agent**

- Summary: feature_request (1.00), low urgency, email: Feature request: staged rollouts
- Restatement: Feature request: staged rollouts: Are staged rollouts on the roadmap?
- Reason: intent feature_request must always escalate (FR-12) Also: no supporting passage passed the relevance cutoff.

**Sources retrieved for the agent**: none passed the cutoff

---

## 23. VAL-0031 (escalated)

Channel email; predicted intent rollback_request (1.00); route escalate; final escalate; rule `no_retrieval_hit`.

**Ticket**

> Bad release in production
> 
> We shipped a release yesterday morning that has broken checkout for a portion of our customers. We need to get back to the previous version quickly. What is the fastest safe route?

**Customer received (holding message)**

```
Thank you for contacting CloudServe Support. A member of our support team will look at your request and reply to you.
```

**Escalation package for the agent**

- Summary: rollback_request (1.00), high urgency, email: Bad release in production
- Restatement: Bad release in production: We shipped a release yesterday morning that has broken checkout for a portion of our customers.
- Reason: no supporting passage: nothing passed the relevance cutoff (No passage at or above cutoff 0.51; best was DOC-DEPLOY-002#c01 at 0.51.); escalated without a draft or a model call

**Sources retrieved for the agent**: none passed the cutoff

---

## 24. VAL-0032 (escalated)

Channel chat; predicted intent feature_request (1.00); route escalate; final escalate; rule `must_escalate_intent:feature_request`.

**Ticket**

> It would be very useful to set spend caps per project rather than only for the whole organisation. At the moment one team's overspend affects everyone.

**Customer received (holding message)**

```
Thank you for contacting CloudServe Support. A member of our support team will look at your request and reply to you.
```

**Escalation package for the agent**

- Summary: feature_request (1.00), medium urgency, chat: (no subject)
- Restatement: (no subject): It would be very useful to set spend caps per project rather than only for the whole organisation.
- Reason: intent feature_request must always escalate (FR-12) Also: no supporting passage passed the relevance cutoff.

**Sources retrieved for the agent**: none passed the cutoff

---

## 25. VAL-0033 (answered)

Channel forum; predicted intent webhook_issue (1.00); route auto_respond; final auto_respond; rule `none`.

**Ticket**

> Duplicate webhook deliveries
> 
> Signature verification fails for every delivery. We are computing the signature exactly as the documentation describes, over the parsed body.

**Sent to the customer**

```
This is an automated reply from CloudServe Support. It is based on our help articles listed below.

Hello,

Compute the signature over the raw request body before any parsing, as re-serialising JSON changes the bytes and invalidates the signature. Check the webhook delivery log to see every attempt with the response status and body for the last seven days. Return 2xx as quickly as possible and process the event asynchronously, as deliveries time out after five seconds.

If this does not solve the problem, reply to this message and a member of our support team will help you.

Sources:
- Webhook delivery, retries and signature verification (DOC-API-003), reviewed today
```

**Answer sentences and their citations**

1. Compute the signature over the raw request body before any parsing, as re-serialising JSON changes the bytes and invalidates the signature.  [cites: DOC-API-003#c01]
2. Check the webhook delivery log to see every attempt with the response status and body for the last seven days.  [cites: DOC-API-003#c01]
3. Return 2xx as quickly as possible and process the event asynchronously, as deliveries time out after five seconds.  [cites: DOC-API-003#c01]

**Cited passages**

*DOC-API-003#c01* (Webhook delivery, retries and signature verification)

> ## Resolution
> 
> 1. Check the webhook delivery log, which records every attempt with the response status and body for the last seven days.
> 2. Return 2xx as quickly as possible and process the event asynchronously. Deliveries time out after five seconds.
> 3. Compute the signature over the raw request body before any parsing. Re-serialising JSON changes the bytes and invalidates the signature.
> 4. Make your handler idempotent using the event identifier. At-least-once delivery means duplicates are expected rather than exceptional.
> 
> ## Notes
> 
> Failed deliveries are retried with backoff for twenty-four hours, after which the endpoint is disabled and the account is notified.

---

## 26. VAL-0035 (escalated)

Channel chat; predicted intent unclear_request (1.00); route escalate; final escalate; rule `must_escalate_intent:unclear_request`.

**Ticket**

> It is not working. Please help.

**Customer received (holding message)**

```
Thank you for contacting CloudServe Support. A member of our support team will look at your request and reply to you.
```

**Escalation package for the agent**

- Summary: unclear_request (1.00), medium urgency, chat: (no subject)
- Restatement: (no subject): It is not working.
- Reason: intent unclear_request must always escalate (FR-12) Also: no supporting passage passed the relevance cutoff.

**Sources retrieved for the agent**: none passed the cutoff

---

## 27. VAL-0036 (blocked)

Channel forum; predicted intent onboarding (1.00); route auto_respond; final escalate; rule `guardrail:grounding`.

**Ticket**

> Getting started with first deployment
> 
> Could you point me at the right starting place? I have created an account but the console has more in it than I expected.

**Blocked draft (never sent).** Block reason: Validate blocked the answer (grounding: sentence(s) [1] below the floor 0.21 (lowest 0.18)). Escalated; the answer is left out and the customer gets the holding message.

**Answer sentences and their citations**

1. Create a project, then a service within it. Resources belong to services and services belong to projects.  [cites: DOC-ONB-001#c00]
2. Connect a repository or push a container image. The build service detects common project layouts automatically.  [cites: DOC-ONB-001#c00]
3. Set any environment variables the application needs before the first deployment rather than after it.  [cites: DOC-ONB-001#c00]
4. Deploy, then watch the logs for the first sixty seconds. Most first-deployment problems are visible immediately in startup output.  [cites: DOC-ONB-001#c00]

**Cited passages**

*DOC-ONB-001#c00* (First deployment: a walkthrough)

> # First deployment: a walkthrough
> 
> **Applies to:** All plans
> 
> ## Symptoms
> 
> - A new user does not know where to begin
> - The first deployment fails for unclear reasons
> 
> ## Common causes
> 
> - Required configuration has not been set
> - The project structure does not match what the build expects
> 
> ## Resolution
> 
> 1. Create a project, then a service within it. Resources belong to services and services belong to projects.
> 2. Connect a repository or push a container image. The build service detects common project layouts automatically.
> 3. Set any environment variables the application needs before the first deployment rather than after it.
> 4. Deploy, then watch the logs for the first sixty seconds. Most first-deployment problems are visible immediately in startup output.
> 
> ## Notes

---

## 28. VAL-0037 (escalated)

Channel email; predicted intent data_residency (1.00); route escalate; final escalate; rule `must_escalate_intent:data_residency`.

**Ticket**

> Question about backup regions
> 
> Are backups replicated outside our primary region? A compliance review has raised this and I need a definite answer.

**Customer received (holding message)**

```
Thank you for contacting CloudServe Support. A member of our support team will look at your request and reply to you.
```

**Escalation package for the agent**

- Summary: data_residency (1.00), medium urgency, email: Question about backup regions
- Restatement: Question about backup regions: Are backups replicated outside our primary region?
- Reason: intent data_residency must always escalate (FR-12)

**Sources retrieved for the agent**

*DOC-DATA-003#c01* (Data residency and regional storage)

> ## Resolution
> 
> 1. Check the region shown on the organisation settings page. This is fixed at creation and determines where primary data is stored.
> 2. Enable read replicas in additional regions to reduce latency for distant users without moving primary storage.
> 3. Review the backup replication setting if a single-region requirement applies, since cross-region replication is enabled by default.
> 4. Migrating an organisation between regions requires a planned migration with support and involves a maintenance window.
> 
> ## Notes
> 
> Metadata such as account names and billing records is stored centrally regardless of the data region.

*DOC-DATA-003#c00* (Data residency and regional storage)

> # Data residency and regional storage
> 
> **Applies to:** Business and Enterprise plans
> 
> ## Symptoms
> 
> - A customer requires data to remain in a specific region
> - Latency is high for users far from the primary region
> - A compliance review has asked where data is held
> 
> ## Common causes
> 
> - The organisation was created in a region that no longer suits the requirement
> - Read traffic is being served from the primary region only
> - Backups are replicated to a second region by default
> 
> ## Resolution

---

## 29. VAL-0038 (escalated)

Channel forum; predicted intent performance_degradation (1.00); route escalate; final escalate; rule `no_retrieval_hit`.

**Ticket**

> p95 latency is very high
> 
> Our response times have roughly doubled since two days ago with no deployment on our side. The median looks acceptable but the 95th percentile is far worse than it was.

**Customer received (holding message)**

```
Thank you for contacting CloudServe Support. A member of our support team will look at your request and reply to you.
```

**Escalation package for the agent**

- Summary: performance_degradation (1.00), medium urgency, forum: p95 latency is very high
- Restatement: p95 latency is very high: Our response times have roughly doubled since two days ago with no deployment on our side.
- Reason: no supporting passage: nothing passed the relevance cutoff (No passage at or above cutoff 0.51; best was DOC-PERF-001#c01 at 0.50.); escalated without a draft or a model call

**Sources retrieved for the agent**: none passed the cutoff

---

## 30. VAL-0039 (answered)

Channel forum; predicted intent api_key_issue (1.00); route auto_respond; final auto_respond; rule `none`.

**Ticket**

> API key returning 401
> 
> One of our engineers pushed a key to a public repository by mistake. We need to replace it without taking the service down. What is the correct order of operations?

**Sent to the customer**

```
This is an automated reply from CloudServe Support. It is based on our help articles listed below.

Hello,

To rotate without downtime, create the replacement key first, deploy it, confirm traffic has moved, then revoke the old key. If a key has been exposed publicly, revoke it immediately rather than waiting for the rotation window.

If this does not solve the problem, reply to this message and a member of our support team will help you.

Sources:
- API key rotation and scope management (DOC-AUTH-004), reviewed today
```

**Answer sentences and their citations**

1. To rotate without downtime, create the replacement key first, deploy it, confirm traffic has moved, then revoke the old key.  [cites: DOC-AUTH-004#c01]
2. If a key has been exposed publicly, revoke it immediately rather than waiting for the rotation window.  [cites: DOC-AUTH-004#c01]

**Cited passages**

*DOC-AUTH-004#c01* (API key rotation and scope management)

> ## Resolution
> 
> 1. Check the API keys page for the key's status and expiry. Revoked and expired keys are listed with the date and the user who acted.
> 2. Review the scopes attached to the key. Read-only keys cannot write, and project-scoped keys cannot reach organisation endpoints.
> 3. To rotate without downtime, create the replacement key first, deploy it, confirm traffic has moved, then revoke the old key.
> 4. If a key has been exposed publicly, revoke it immediately rather than waiting for the rotation window.
> 
> ## Notes
> 
> Keys issued to individual users are removed when that user is deleted. Use service accounts for anything running in production.

---

## 31. VAL-0041 (answered)

Channel email; predicted intent billing_query (1.00); route auto_respond; final auto_respond; rule `none`.

**Ticket**

> Question about this month's charges
> 
> There are charges on our invoice for a service I do not believe we use. Could you explain what these relate to?

**Sent to the customer**

```
This is an automated reply from CloudServe Support. It is based on our help articles listed below.

Hello,

Open the usage breakdown for the period to see charges itemised by service and environment. Look for resources in staging or development environments that may be running and accruing charges. Check the billing period dates at the top of the invoice, as the period runs from the subscription anniversary rather than the first of the month.

If this does not solve the problem, reply to this message and a member of our support team will help you.

Sources:
- Understanding your invoice and usage breakdown (DOC-BILL-001), reviewed today
```

**Answer sentences and their citations**

1. Open the usage breakdown for the period to see charges itemised by service and environment.  [cites: DOC-BILL-001#c01]
2. Look for resources in staging or development environments that may be running and accruing charges.  [cites: DOC-BILL-001#c01]
3. Check the billing period dates at the top of the invoice, as the period runs from the subscription anniversary rather than the first of the month.  [cites: DOC-BILL-001#c01]

**Cited passages**

*DOC-BILL-001#c01* (Understanding your invoice and usage breakdown)

> ## Resolution
> 
> 1. Open the usage breakdown for the period, which itemises charges by service and by environment.
> 2. Look for resources in staging or development environments, which are billed at the same rate as production.
> 3. Check the billing period dates at the top of the invoice. The period runs from the anniversary of the subscription date.
> 4. Set a usage alert on the billing page so that unexpected accrual is noticed during the period rather than at the end of it.
> 
> ## Notes
> 
> Invoices are finalised three days after the period ends. Adjustments requested before finalisation appear on the same invoice.

---

## 32. VAL-0043 (escalated)

Channel forum; predicted intent security_incident (1.00); route escalate; final escalate; rule `must_escalate_intent:security_incident`.

**Ticket**

> Suspicious activity in audit log
> 
> One of our engineers believes their credentials may have been exposed in a breach at another service. What should we be doing right now?

**Customer received (holding message)**

```
Thank you for contacting CloudServe Support. A member of our support team will look at your request and reply to you.
```

**Escalation package for the agent**

- Summary: security_incident (1.00), high urgency, forum: Suspicious activity in audit log
- Restatement: Suspicious activity in audit log: One of our engineers believes their credentials may have been exposed in a breach at another service.
- Reason: intent security_incident must always escalate (FR-12)

**Sources retrieved for the agent**

*DOC-SEC-001#c01* (Responding to a suspected account compromise)

> ## Resolution
> 
> 1. Revoke all API keys for the affected account immediately. This is disruptive and it is the correct first action.
> 2. Force a password reset and terminate active sessions for the affected users from the team members page.
> 3. Review the audit log for the period in question, filtering by the affected user, and record anything unexpected before it ages out.
> 4. Enable multi-factor authentication for all users if it is not already mandatory for the organisation.
> 
> ## Notes
> 
> Audit logs are retained for ninety days on Business plans and one year on Enterprise. Export them promptly during an investigation.

*DOC-SEC-001#c00* (Responding to a suspected account compromise)

> # Responding to a suspected account compromise
> 
> **Applies to:** All plans
> 
> ## Symptoms
> 
> - Unrecognised activity appears in the audit log
> - A user reports credentials may have been exposed
> - Resources were created that nobody claims
> 
> ## Common causes
> 
> - Credentials were reused from a service that suffered a breach
> - An API key was committed to a public repository
> - A former team member retained access after leaving
> 
> ## Resolution

*DOC-SEC-002#c01* (Handling exposed secrets and credential rotation)

> ## Resolution
> 
> 1. Revoke the exposed credential first. Removing it from the repository does not help, because it remains in the history.
> 2. Issue a replacement with the narrowest scope that still works, rather than recreating the original permissions by default.
> 3. Search the audit log for use of the exposed credential from unfamiliar addresses during the exposure window.
> 4. Add secret scanning to your pipeline so that the next occurrence is caught before it reaches a remote branch.
> 
> ## Notes
> 
> Never send a live credential to support. Support will never ask for one, and any credential shared in a ticket must be treated as exposed.

---

## 33. VAL-0047 (answered)

Channel chat; predicted intent rate_limit (1.00); route auto_respond; final auto_respond; rule `none`.

**Ticket**

> Are the search endpoints limited differently from the rest? Our read traffic is fine but search is being rejected constantly.

**Sent to the customer**

```
This is an automated reply from CloudServe Support. It is based on our help articles listed below.

Hello,

Search and export endpoints have tighter limits than reads and are limited more tightly. Confirm whether the endpoint being called has a specific limit, as search endpoints are more expensive and have lower limits than reads.

If this does not solve the problem, reply to this message and a member of our support team will help you.

Sources:
- Understanding API rate limits and quota tiers (DOC-API-001), reviewed today
```

**Answer sentences and their citations**

1. Search and export endpoints have tighter limits than reads and are limited more tightly.  [cites: DOC-API-001#c01]
2. Confirm whether the endpoint being called has a specific limit, as search endpoints are more expensive and have lower limits than reads.  [cites: DOC-API-001#c01]

**Cited passages**

*DOC-API-001#c01* (Understanding API rate limits and quota tiers)

> ## Resolution
> 
> 1. Read the rate limit headers returned with every response. They give the limit, the remaining allowance and the reset time, which is more reliable than inferring the limit from behaviour.
> 2. Confirm whether the endpoint has a specific limit. Search and export endpoints are more expensive and are limited more tightly than reads.
> 3. Implement exponential backoff with jitter on 429 responses rather than retrying immediately, which prolongs the throttling.
> 4. Where sustained higher throughput is genuinely required, the limit can be raised on Business and Enterprise plans through an account request.
> 
> ## Notes
> 
> Limits are enforced per organisation. Issuing more keys does not increase the available quota.

---

## 34. VAL-0048 (escalated)

Channel chat; predicted intent security_incident (1.00); route escalate; final escalate; rule `must_escalate_intent:security_incident`.

**Ticket**

> one of our engineers believes their credentials may have been exposed in breach at another service. What should we be doing right now? please tell what to do.

**Customer received (holding message)**

```
Thank you for contacting CloudServe Support. A member of our support team will look at your request and reply to you.
```

**Escalation package for the agent**

- Summary: security_incident (1.00), high urgency, chat: (no subject)
- Restatement: (no subject): one of our engineers believes their credentials may have been exposed in breach at another service.
- Reason: intent security_incident must always escalate (FR-12)

**Sources retrieved for the agent**

*DOC-SEC-001#c01* (Responding to a suspected account compromise)

> ## Resolution
> 
> 1. Revoke all API keys for the affected account immediately. This is disruptive and it is the correct first action.
> 2. Force a password reset and terminate active sessions for the affected users from the team members page.
> 3. Review the audit log for the period in question, filtering by the affected user, and record anything unexpected before it ages out.
> 4. Enable multi-factor authentication for all users if it is not already mandatory for the organisation.
> 
> ## Notes
> 
> Audit logs are retained for ninety days on Business plans and one year on Enterprise. Export them promptly during an investigation.

*DOC-SEC-001#c00* (Responding to a suspected account compromise)

> # Responding to a suspected account compromise
> 
> **Applies to:** All plans
> 
> ## Symptoms
> 
> - Unrecognised activity appears in the audit log
> - A user reports credentials may have been exposed
> - Resources were created that nobody claims
> 
> ## Common causes
> 
> - Credentials were reused from a service that suffered a breach
> - An API key was committed to a public repository
> - A former team member retained access after leaving
> 
> ## Resolution

---

## 35. VAL-0049 (escalated)

Channel email; predicted intent api_key_issue (1.00); route escalate; final escalate; rule `no_retrieval_hit`.

**Ticket**

> Need to rotate an exposed key
> 
> key can read fine but every write returns permission error. I created it myself and I thought I gave it full access. please help fast.

**Customer received (holding message)**

```
Thank you for contacting CloudServe Support. A member of our support team will look at your request and reply to you.
```

**Escalation package for the agent**

- Summary: api_key_issue (1.00), medium urgency, email: Need to rotate an exposed key
- Restatement: Need to rotate an exposed key: key can read fine but every write returns permission error.
- Reason: no supporting passage: nothing passed the relevance cutoff (No passage at or above cutoff 0.51; best was DOC-AUTH-004#c01 at 0.45.); escalated without a draft or a model call

**Sources retrieved for the agent**: none passed the cutoff

---

## 36. VAL-0050 (blocked)

Channel email; predicted intent onboarding (1.00); route auto_respond; final escalate; rule `guardrail:grounding`.

**Ticket**

> Getting started with first deployment
> 
> We have just signed up and I am not sure where to start. We have a containerised application and would like to get it deployed.

**Blocked draft (never sent).** Block reason: Validate blocked the answer (grounding: sentence(s) [1] below the floor 0.21 (lowest 0.18)). Escalated; the answer is left out and the customer gets the holding message.

**Answer sentences and their citations**

1. Create a project, then a service within it. Resources belong to services and services belong to projects.  [cites: DOC-ONB-001#c00]
2. Connect a repository or push a container image. The build service detects common project layouts automatically.  [cites: DOC-ONB-001#c00]
3. Set any environment variables the application needs before the first deployment rather than after it.  [cites: DOC-ONB-001#c00]
4. Deploy, then watch the logs for the first sixty seconds. Most first-deployment problems are visible immediately in startup output.  [cites: DOC-ONB-001#c00]

**Cited passages**

*DOC-ONB-001#c00* (First deployment: a walkthrough)

> # First deployment: a walkthrough
> 
> **Applies to:** All plans
> 
> ## Symptoms
> 
> - A new user does not know where to begin
> - The first deployment fails for unclear reasons
> 
> ## Common causes
> 
> - Required configuration has not been set
> - The project structure does not match what the build expects
> 
> ## Resolution
> 
> 1. Create a project, then a service within it. Resources belong to services and services belong to projects.
> 2. Connect a repository or push a container image. The build service detects common project layouts automatically.
> 3. Set any environment variables the application needs before the first deployment rather than after it.
> 4. Deploy, then watch the logs for the first sixty seconds. Most first-deployment problems are visible immediately in startup output.
> 
> ## Notes

---

## 37. VAL-0051 (answered)

Channel forum; predicted intent integration_help (1.00); route auto_respond; final auto_respond; rule `none`.

**Ticket**

> Log forwarding stopped working
> 
> log forwarding to our external system stop two days ago and not resumed by itself. destination is healthy as we know. kindly check and revert.

**Sent to the customer**

```
This is an automated reply from CloudServe Support. It is based on our help articles listed below.

Hello,

Check the forwarding status page to see the last successful delivery and any error returned by the destination. Apply a level filter at source so that debug output is not forwarded. Verify the destination credential separately if delivery has stopped entirely, as expired credentials are the most common cause.

If this does not solve the problem, reply to this message and a member of our support team will help you.

Sources:
- Third party monitoring and log forwarding (DOC-INT-002), reviewed today
```

**Answer sentences and their citations**

1. Check the forwarding status page to see the last successful delivery and any error returned by the destination.  [cites: DOC-INT-002#c01]
2. Apply a level filter at source so that debug output is not forwarded.  [cites: DOC-INT-002#c01]
3. Verify the destination credential separately if delivery has stopped entirely, as expired credentials are the most common cause.  [cites: DOC-INT-002#c01]

**Cited passages**

*DOC-INT-002#c01* (Third party monitoring and log forwarding)

> ## Resolution
> 
> 1. Check the forwarding status page, which shows the last successful delivery and any error returned by the destination.
> 2. Expect a delay of up to two minutes on metrics, since they are aggregated before being sent.
> 3. Apply a level filter at source so that debug output is not forwarded, which is usually the reason volume is higher than expected.
> 4. Verify the destination credential separately if delivery has stopped entirely, as expired credentials are the most common cause.
> 
> ## Notes
> 
> Forwarding pauses after one hour of consecutive failures and must be resumed manually once the destination is healthy.

---

## 38. VAL-0053 (answered)

Channel chat; predicted intent billing_query (1.00); route auto_respond; final auto_respond; rule `none`.

**Ticket**

> There are charges on our invoice for a service I do not believe we use. Could you explain what these relate to?

**Sent to the customer**

```
This is an automated reply from CloudServe Support. It is based on our help articles listed below.

Hello,

Open the usage breakdown for the period to see charges itemised by service and environment. Look for resources in staging or development environments, which are billed at the same rate as production. Check the billing period dates at the top of the invoice; the period runs from the anniversary of the subscription date.

If this does not solve the problem, reply to this message and a member of our support team will help you.

Sources:
- Understanding your invoice and usage breakdown (DOC-BILL-001), reviewed today
```

**Answer sentences and their citations**

1. Open the usage breakdown for the period to see charges itemised by service and environment.  [cites: DOC-BILL-001#c01]
2. Look for resources in staging or development environments, which are billed at the same rate as production.  [cites: DOC-BILL-001#c01]
3. Check the billing period dates at the top of the invoice; the period runs from the anniversary of the subscription date.  [cites: DOC-BILL-001#c01]

**Cited passages**

*DOC-BILL-001#c01* (Understanding your invoice and usage breakdown)

> ## Resolution
> 
> 1. Open the usage breakdown for the period, which itemises charges by service and by environment.
> 2. Look for resources in staging or development environments, which are billed at the same rate as production.
> 3. Check the billing period dates at the top of the invoice. The period runs from the anniversary of the subscription date.
> 4. Set a usage alert on the billing page so that unexpected accrual is noticed during the period rather than at the end of it.
> 
> ## Notes
> 
> Invoices are finalised three days after the period ends. Adjustments requested before finalisation appear on the same invoice.

---

## 39. VAL-0054 (escalated)

Channel email; predicted intent data_residency (1.00); route escalate; final escalate; rule `must_escalate_intent:data_residency`.

**Ticket**

> Where is our data stored
> 
> One of our customers has asked for written confirmation of where their data is physically stored. Could you point me to something I can share with them?

**Customer received (holding message)**

```
Thank you for contacting CloudServe Support. A member of our support team will look at your request and reply to you.
```

**Escalation package for the agent**

- Summary: data_residency (1.00), medium urgency, email: Where is our data stored
- Restatement: Where is our data stored: One of our customers has asked for written confirmation of where their data is physically stored.
- Reason: intent data_residency must always escalate (FR-12)

**Sources retrieved for the agent**

*DOC-DATA-003#c00* (Data residency and regional storage)

> # Data residency and regional storage
> 
> **Applies to:** Business and Enterprise plans
> 
> ## Symptoms
> 
> - A customer requires data to remain in a specific region
> - Latency is high for users far from the primary region
> - A compliance review has asked where data is held
> 
> ## Common causes
> 
> - The organisation was created in a region that no longer suits the requirement
> - Read traffic is being served from the primary region only
> - Backups are replicated to a second region by default
> 
> ## Resolution

*DOC-DATA-003#c01* (Data residency and regional storage)

> ## Resolution
> 
> 1. Check the region shown on the organisation settings page. This is fixed at creation and determines where primary data is stored.
> 2. Enable read replicas in additional regions to reduce latency for distant users without moving primary storage.
> 3. Review the backup replication setting if a single-region requirement applies, since cross-region replication is enabled by default.
> 4. Migrating an organisation between regions requires a planned migration with support and involves a maintenance window.
> 
> ## Notes
> 
> Metadata such as account names and billing records is stored centrally regardless of the data region.

---

## 40. VAL-0056 (answered)

Channel email; predicted intent deployment_failure (1.00); route auto_respond; final auto_respond; rule `none`.

**Ticket**

> Build fails in the pipeline
> 
> Every deployment fails at the health check stage. I have increased the timeout twice already and it makes no difference.

**Sent to the customer**

```
This is an automated reply from CloudServe Support. It is based on our help articles listed below.

Hello,

Confirm the container is listening on the port declared in the service definition. Increase the initial delay if the application needs time to warm up before it can answer; thirty seconds is a reasonable starting point for services that load models or caches. Compare the environment variables present in the deployment against those the application requires. Inspect the container logs from the failed revision rather than the running one.

If this does not solve the problem, reply to this message and a member of our support team will help you.

Sources:
- Container deployments failing during the health check phase (DOC-DEPLOY-001), reviewed today
```

**Answer sentences and their citations**

1. Confirm the container is listening on the port declared in the service definition.  [cites: DOC-DEPLOY-001#c01]
2. Increase the initial delay if the application needs time to warm up before it can answer; thirty seconds is a reasonable starting point for services that load models or caches.  [cites: DOC-DEPLOY-001#c01]
3. Compare the environment variables present in the deployment against those the application requires.  [cites: DOC-DEPLOY-001#c01]
4. Inspect the container logs from the failed revision rather than the running one.  [cites: DOC-DEPLOY-001#c01]

**Cited passages**

*DOC-DEPLOY-001#c01* (Container deployments failing during the health check phase)

> ## Resolution
> 
> 1. Confirm the container is listening on the port declared in the service definition. A mismatch here produces a health check failure that looks like a timeout.
> 2. Increase the initial delay if the application needs time to warm up before it can answer. Thirty seconds is a reasonable starting point for services that load models or caches.
> 3. Compare the environment variables present in the deployment against those the application requires. Missing configuration frequently causes a silent startup failure.
> 4. Inspect the container logs from the failed revision rather than the running one; the rollback replaces the logs shown by default.
> 
> ## Notes

---

## 41. VAL-0057 (answered)

Channel email; predicted intent deployment_failure (1.00); route auto_respond; final auto_respond; rule `none`.

**Ticket**

> Deployment rolls back every time
> 
> Our deployment reaches running and then rolls back after about a minute. The logs mention a health check timeout. It runs perfectly on my machine and in staging.

**Sent to the customer**

```
This is an automated reply from CloudServe Support. It is based on our help articles listed below.

Hello,

Confirm the container is listening on the port declared in the service definition. Increase the initial delay to thirty seconds if the application needs time to warm up before it can answer. Compare the environment variables present in the deployment against those the application requires. Inspect the container logs from the failed revision rather than the running one.

If this does not solve the problem, reply to this message and a member of our support team will help you.

Sources:
- Container deployments failing during the health check phase (DOC-DEPLOY-001), reviewed today
```

**Answer sentences and their citations**

1. Confirm the container is listening on the port declared in the service definition.  [cites: DOC-DEPLOY-001#c01]
2. Increase the initial delay to thirty seconds if the application needs time to warm up before it can answer.  [cites: DOC-DEPLOY-001#c01]
3. Compare the environment variables present in the deployment against those the application requires.  [cites: DOC-DEPLOY-001#c01]
4. Inspect the container logs from the failed revision rather than the running one.  [cites: DOC-DEPLOY-001#c01]

**Cited passages**

*DOC-DEPLOY-001#c01* (Container deployments failing during the health check phase)

> ## Resolution
> 
> 1. Confirm the container is listening on the port declared in the service definition. A mismatch here produces a health check failure that looks like a timeout.
> 2. Increase the initial delay if the application needs time to warm up before it can answer. Thirty seconds is a reasonable starting point for services that load models or caches.
> 3. Compare the environment variables present in the deployment against those the application requires. Missing configuration frequently causes a silent startup failure.
> 4. Inspect the container logs from the failed revision rather than the running one; the rollback replaces the logs shown by default.
> 
> ## Notes

---

## 42. VAL-0058 (answered)

Channel docs_comment; predicted intent api_key_issue (1.00); route auto_respond; final auto_respond; rule `none`.

**Ticket**

> Need to rotate an exposed key
> 
> one of our production keys start returning 401 at around last Friday without any change on our side. Other keys against same account still working. waiting for your reply.

**Sent to the customer**

```
This is an automated reply from CloudServe Support. It is based on our help articles listed below.

Hello,

Check the API keys page for the key's status and expiry. Revoked and expired keys are listed with the date and the user who acted. Review the scopes attached to the key. Read-only keys cannot write, and project-scoped keys cannot reach organisation endpoints. To rotate without downtime, create the replacement key first, deploy it, confirm traffic has moved, then revoke the old key.

If this does not solve the problem, reply to this message and a member of our support team will help you.

Sources:
- API key rotation and scope management (DOC-AUTH-004), reviewed today
```

**Answer sentences and their citations**

1. Check the API keys page for the key's status and expiry. Revoked and expired keys are listed with the date and the user who acted.  [cites: DOC-AUTH-004#c01]
2. Review the scopes attached to the key. Read-only keys cannot write, and project-scoped keys cannot reach organisation endpoints.  [cites: DOC-AUTH-004#c01]
3. To rotate without downtime, create the replacement key first, deploy it, confirm traffic has moved, then revoke the old key.  [cites: DOC-AUTH-004#c01]

**Cited passages**

*DOC-AUTH-004#c01* (API key rotation and scope management)

> ## Resolution
> 
> 1. Check the API keys page for the key's status and expiry. Revoked and expired keys are listed with the date and the user who acted.
> 2. Review the scopes attached to the key. Read-only keys cannot write, and project-scoped keys cannot reach organisation endpoints.
> 3. To rotate without downtime, create the replacement key first, deploy it, confirm traffic has moved, then revoke the old key.
> 4. If a key has been exposed publicly, revoke it immediately rather than waiting for the rotation window.
> 
> ## Notes
> 
> Keys issued to individual users are removed when that user is deleted. Use service accounts for anything running in production.

---

## 43. VAL-0060 (answered)

Channel email; predicted intent webhook_issue (1.00); route auto_respond; final auto_respond; rule `none`.

**Ticket**

> Webhooks not arriving
> 
> Signature verification fails for every delivery. We are computing the signature exactly as the documentation describes, over the parsed body.

**Sent to the customer**

```
This is an automated reply from CloudServe Support. It is based on our help articles listed below.

Hello,

Compute the signature over the raw request body before any parsing, as re-serialising JSON changes the bytes and invalidates the signature. Check the webhook delivery log to see every attempt with the response status and body for the last seven days.

If this does not solve the problem, reply to this message and a member of our support team will help you.

Sources:
- Webhook delivery, retries and signature verification (DOC-API-003), reviewed today
```

**Answer sentences and their citations**

1. Compute the signature over the raw request body before any parsing, as re-serialising JSON changes the bytes and invalidates the signature.  [cites: DOC-API-003#c01]
2. Check the webhook delivery log to see every attempt with the response status and body for the last seven days.  [cites: DOC-API-003#c01]

**Cited passages**

*DOC-API-003#c01* (Webhook delivery, retries and signature verification)

> ## Resolution
> 
> 1. Check the webhook delivery log, which records every attempt with the response status and body for the last seven days.
> 2. Return 2xx as quickly as possible and process the event asynchronously. Deliveries time out after five seconds.
> 3. Compute the signature over the raw request body before any parsing. Re-serialising JSON changes the bytes and invalidates the signature.
> 4. Make your handler idempotent using the event identifier. At-least-once delivery means duplicates are expected rather than exceptional.
> 
> ## Notes
> 
> Failed deliveries are retried with backoff for twenty-four hours, after which the endpoint is disabled and the account is notified.

---

## 44. VAL-0061 (answered)

Channel email; predicted intent webhook_issue (1.00); route auto_respond; final auto_respond; rule `none`.

**Ticket**

> Webhooks not arriving
> 
> Signature verification fails for every delivery. We are computing the signature exactly as the documentation describes, over the parsed body.

**Sent to the customer**

```
This is an automated reply from CloudServe Support. It is based on our help articles listed below.

Hello,

Compute the signature over the raw request body before any parsing, as re-serialising JSON changes the bytes and invalidates the signature. Check the webhook delivery log to see every attempt with the response status and body for the last seven days. Return 2xx as quickly as possible and process the event asynchronously, as deliveries time out after five seconds.

If this does not solve the problem, reply to this message and a member of our support team will help you.

Sources:
- Webhook delivery, retries and signature verification (DOC-API-003), reviewed today
```

**Answer sentences and their citations**

1. Compute the signature over the raw request body before any parsing, as re-serialising JSON changes the bytes and invalidates the signature.  [cites: DOC-API-003#c01]
2. Check the webhook delivery log to see every attempt with the response status and body for the last seven days.  [cites: DOC-API-003#c01]
3. Return 2xx as quickly as possible and process the event asynchronously, as deliveries time out after five seconds.  [cites: DOC-API-003#c01]

**Cited passages**

*DOC-API-003#c01* (Webhook delivery, retries and signature verification)

> ## Resolution
> 
> 1. Check the webhook delivery log, which records every attempt with the response status and body for the last seven days.
> 2. Return 2xx as quickly as possible and process the event asynchronously. Deliveries time out after five seconds.
> 3. Compute the signature over the raw request body before any parsing. Re-serialising JSON changes the bytes and invalidates the signature.
> 4. Make your handler idempotent using the event identifier. At-least-once delivery means duplicates are expected rather than exceptional.
> 
> ## Notes
> 
> Failed deliveries are retried with backoff for twenty-four hours, after which the endpoint is disabled and the account is notified.

---

## 45. VAL-0064 (answered)

Channel chat; predicted intent api_usage_question (1.00); route auto_respond; final auto_respond; rule `none`.

**Ticket**

> What is the right way to pull a very large extract? Requesting a big page size gets rejected and iterating page by page takes hours.

**Sent to the customer**

```
This is an automated reply from CloudServe Support. It is based on our help articles listed below.

Hello,

Use cursor pagination for large result sets, passing the next_cursor value from each response as the cursor parameter of the following request and stopping when it is null. Keep the page size at or below two hundred; larger requests are rejected rather than truncated. For very large extracts, use the export endpoint, which runs asynchronously and returns a download link.

If this does not solve the problem, reply to this message and a member of our support team will help you.

Sources:
- Pagination and handling large result sets (DOC-API-002), reviewed today
```

**Answer sentences and their citations**

1. Use cursor pagination for large result sets, passing the next_cursor value from each response as the cursor parameter of the following request and stopping when it is null.  [cites: DOC-API-002#c01]
2. Keep the page size at or below two hundred; larger requests are rejected rather than truncated.  [cites: DOC-API-002#c01]
3. For very large extracts, use the export endpoint, which runs asynchronously and returns a download link.  [cites: DOC-API-002#c01]

**Cited passages**

*DOC-API-002#c01* (Pagination and handling large result sets)

> ## Resolution
> 
> 1. Use cursor pagination for anything that may change while you iterate. Offset pagination will skip or repeat records when items are inserted mid-iteration.
> 2. Pass the next_cursor value from each response as the cursor parameter of the following request, and stop when it is null.
> 3. Keep page size at or below two hundred. Larger requests are rejected rather than truncated.
> 4. For very large extracts, use the export endpoint, which runs asynchronously and returns a download link.
> 
> ## Notes
> 
> Cursors expire after one hour. Long-running iterations should handle expiry by restarting from a recorded checkpoint.

---

## 46. VAL-0065 (answered)

Channel email; predicted intent billing_query (1.00); route auto_respond; final auto_respond; rule `none`.

**Ticket**

> Billing period dates unclear
> 
> There are charges on our invoice for a service I do not believe we use. Could you explain what these relate to?

**Sent to the customer**

```
This is an automated reply from CloudServe Support. It is based on our help articles listed below.

Hello,

Open the usage breakdown for the period to see charges itemised by service and environment. Check the billing period dates at the top of the invoice; the period runs from the anniversary of the subscription date, not the first of the month. Look for resources left running in staging or development environments, as these are billed at the same rate as production.

If this does not solve the problem, reply to this message and a member of our support team will help you.

Sources:
- Understanding your invoice and usage breakdown (DOC-BILL-001), reviewed today
```

**Answer sentences and their citations**

1. Open the usage breakdown for the period to see charges itemised by service and environment.  [cites: DOC-BILL-001#c01]
2. Check the billing period dates at the top of the invoice; the period runs from the anniversary of the subscription date, not the first of the month.  [cites: DOC-BILL-001#c01]
3. Look for resources left running in staging or development environments, as these are billed at the same rate as production.  [cites: DOC-BILL-001#c01]

**Cited passages**

*DOC-BILL-001#c01* (Understanding your invoice and usage breakdown)

> ## Resolution
> 
> 1. Open the usage breakdown for the period, which itemises charges by service and by environment.
> 2. Look for resources in staging or development environments, which are billed at the same rate as production.
> 3. Check the billing period dates at the top of the invoice. The period runs from the anniversary of the subscription date.
> 4. Set a usage alert on the billing page so that unexpected accrual is noticed during the period rather than at the end of it.
> 
> ## Notes
> 
> Invoices are finalised three days after the period ends. Adjustments requested before finalisation appear on the same invoice.

---

## 47. VAL-0066 (escalated)

Channel forum; predicted intent data_residency (1.00); route escalate; final escalate; rule `must_escalate_intent:data_residency`.

**Ticket**

> Question about backup regions
> 
> one of our customers has asked for written confirmation of where their data is physically stored. Can you please point me to something I can share with them? sorry for my english.

**Customer received (holding message)**

```
Thank you for contacting CloudServe Support. A member of our support team will look at your request and reply to you.
```

**Escalation package for the agent**

- Summary: data_residency (1.00), medium urgency, forum: Question about backup regions
- Restatement: Question about backup regions: one of our customers has asked for written confirmation of where their data is physically stored.
- Reason: intent data_residency must always escalate (FR-12)

**Sources retrieved for the agent**

*DOC-DATA-003#c01* (Data residency and regional storage)

> ## Resolution
> 
> 1. Check the region shown on the organisation settings page. This is fixed at creation and determines where primary data is stored.
> 2. Enable read replicas in additional regions to reduce latency for distant users without moving primary storage.
> 3. Review the backup replication setting if a single-region requirement applies, since cross-region replication is enabled by default.
> 4. Migrating an organisation between regions requires a planned migration with support and involves a maintenance window.
> 
> ## Notes
> 
> Metadata such as account names and billing records is stored centrally regardless of the data region.

*DOC-DATA-003#c00* (Data residency and regional storage)

> # Data residency and regional storage
> 
> **Applies to:** Business and Enterprise plans
> 
> ## Symptoms
> 
> - A customer requires data to remain in a specific region
> - Latency is high for users far from the primary region
> - A compliance review has asked where data is held
> 
> ## Common causes
> 
> - The organisation was created in a region that no longer suits the requirement
> - Read traffic is being served from the primary region only
> - Backups are replicated to a second region by default
> 
> ## Resolution

---

## 48. VAL-0067 (escalated)

Channel docs_comment; predicted intent security_incident (1.00); route escalate; final escalate; rule `must_escalate_intent:security_incident`.

**Ticket**

> Suspicious activity in audit log
> 
> We have found activity in our audit log from an address none of us recognise, going back to yesterday morning. Resources were created that nobody on the team claims. We need help urgently.

**Customer received (holding message)**

```
Thank you for contacting CloudServe Support. A member of our support team will look at your request and reply to you.
```

**Escalation package for the agent**

- Summary: security_incident (1.00), high urgency, docs_comment: Suspicious activity in audit log
- Restatement: Suspicious activity in audit log: We have found activity in our audit log from an address none of us recognise, going back to yesterday morning.
- Reason: intent security_incident must always escalate (FR-12)

**Sources retrieved for the agent**

*DOC-SEC-001#c01* (Responding to a suspected account compromise)

> ## Resolution
> 
> 1. Revoke all API keys for the affected account immediately. This is disruptive and it is the correct first action.
> 2. Force a password reset and terminate active sessions for the affected users from the team members page.
> 3. Review the audit log for the period in question, filtering by the affected user, and record anything unexpected before it ages out.
> 4. Enable multi-factor authentication for all users if it is not already mandatory for the organisation.
> 
> ## Notes
> 
> Audit logs are retained for ninety days on Business plans and one year on Enterprise. Export them promptly during an investigation.

*DOC-SEC-001#c00* (Responding to a suspected account compromise)

> # Responding to a suspected account compromise
> 
> **Applies to:** All plans
> 
> ## Symptoms
> 
> - Unrecognised activity appears in the audit log
> - A user reports credentials may have been exposed
> - Resources were created that nobody claims
> 
> ## Common causes
> 
> - Credentials were reused from a service that suffered a breach
> - An API key was committed to a public repository
> - A former team member retained access after leaving
> 
> ## Resolution

---

## 49. VAL-0068 (escalated)

Channel email; predicted intent security_incident (1.00); route escalate; final escalate; rule `must_escalate_intent:security_incident`.

**Ticket**

> Suspicious activity in audit log
> 
> we having found activity in our audit log from address none of us recognise, going back to around 14:00 yesterday. Resources created that nobody on the team claims.

**Customer received (holding message)**

```
Thank you for contacting CloudServe Support. A member of our support team will look at your request and reply to you.
```

**Escalation package for the agent**

- Summary: security_incident (1.00), high urgency, email: Suspicious activity in audit log
- Restatement: Suspicious activity in audit log: we having found activity in our audit log from address none of us recognise, going back to around 14:00 yesterday.
- Reason: intent security_incident must always escalate (FR-12)

**Sources retrieved for the agent**

*DOC-SEC-001#c01* (Responding to a suspected account compromise)

> ## Resolution
> 
> 1. Revoke all API keys for the affected account immediately. This is disruptive and it is the correct first action.
> 2. Force a password reset and terminate active sessions for the affected users from the team members page.
> 3. Review the audit log for the period in question, filtering by the affected user, and record anything unexpected before it ages out.
> 4. Enable multi-factor authentication for all users if it is not already mandatory for the organisation.
> 
> ## Notes
> 
> Audit logs are retained for ninety days on Business plans and one year on Enterprise. Export them promptly during an investigation.

*DOC-SEC-001#c00* (Responding to a suspected account compromise)

> # Responding to a suspected account compromise
> 
> **Applies to:** All plans
> 
> ## Symptoms
> 
> - Unrecognised activity appears in the audit log
> - A user reports credentials may have been exposed
> - Resources were created that nobody claims
> 
> ## Common causes
> 
> - Credentials were reused from a service that suffered a breach
> - An API key was committed to a public repository
> - A former team member retained access after leaving
> 
> ## Resolution

---

## 50. VAL-0069 (answered)

Channel chat; predicted intent configuration_help (1.00); route auto_respond; final auto_respond; rule `none`.

**Ticket**

> Our staging environment is picking up production configuration values. I cannot work out where the override is coming from.

**Sent to the customer**

```
This is an automated reply from CloudServe Support. It is based on our help articles listed below.

Hello,

Check the scope at which the variable was defined. Service scope overrides project scope, and project scope overrides organisation defaults. Review the environment overrides page, which lists values that differ from the defaults for each environment.

If this does not solve the problem, reply to this message and a member of our support team will help you.

Sources:
- Configuring environment variables and secrets (DOC-DEPLOY-004), reviewed today
```

**Answer sentences and their citations**

1. Check the scope at which the variable was defined. Service scope overrides project scope, and project scope overrides organisation defaults.  [cites: DOC-DEPLOY-004#c01]
2. Review the environment overrides page, which lists values that differ from the defaults for each environment.  [cites: DOC-DEPLOY-004#c01]

**Cited passages**

*DOC-DEPLOY-004#c01* (Configuring environment variables and secrets)

> ## Resolution
> 
> 1. Check the scope at which the variable was defined. Service scope overrides project scope, and project scope overrides organisation defaults.
> 2. Store anything sensitive as a secret rather than a variable. Secrets are masked in logs and are not readable through the API after creation.
> 3. Review the environment overrides page, which lists values that differ from the defaults for each environment.
> 4. Redeploy after changing configuration. Running containers do not pick up new values without a restart.
> 
> ## Notes
> 
> A secret that has been printed to logs should be treated as exposed and rotated, even if the logs are private.

---

## 51. VAL-0071 (answered)

Channel docs_comment; predicted intent quota_or_overage (1.00); route auto_respond; final auto_respond; rule `none`.

**Ticket**

> Spend cap stopped our service
> 
> We were throttled over the weekend after a traffic increase and it took down part of our product. We would rather pay overage than be stopped. How do we change that?

**Sent to the customer**

```
This is an automated reply from CloudServe Support. It is based on our help articles listed below.

Hello,

Check the current period usage against the plan allowance on the billing page. Decide deliberately between a hard spend cap, which stops the service, and overage, which continues at the listed rate, and choose overage if you want service to continue after the allowance is used. Configure alerts at fifty, eighty and ninety-five per cent of allowance rather than relying on the cap as a warning. If a spend cap has stopped a production service, an account owner can raise it immediately from the billing page and service resumes within a minute.

If this does not solve the problem, reply to this message and a member of our support team will help you.

Sources:
- Usage limits, overage and spend controls (DOC-BILL-003), reviewed today
```

**Answer sentences and their citations**

1. Check the current period usage against the plan allowance on the billing page.  [cites: DOC-BILL-003#c01]
2. Decide deliberately between a hard spend cap, which stops the service, and overage, which continues at the listed rate, and choose overage if you want service to continue after the allowance is used.  [cites: DOC-BILL-003#c01]
3. Configure alerts at fifty, eighty and ninety-five per cent of allowance rather than relying on the cap as a warning.  [cites: DOC-BILL-003#c01]
4. If a spend cap has stopped a production service, an account owner can raise it immediately from the billing page and service resumes within a minute.  [cites: DOC-BILL-003#c01]

**Cited passages**

*DOC-BILL-003#c01* (Usage limits, overage and spend controls)

> ## Resolution
> 
> 1. Check the current period usage against the plan allowance on the billing page.
> 2. Decide deliberately between a hard spend cap, which stops the service, and overage, which continues at the listed rate. Production workloads generally need the second.
> 3. Configure alerts at fifty, eighty and ninety-five per cent of allowance rather than relying on the cap as a warning.
> 4. Where a cap has stopped a production service, an account owner can raise it immediately from the billing page and service resumes within a minute.
> 
> ## Notes
> 
> Spend caps apply per organisation and cannot currently be set per project.

---

## 52. VAL-0073 (answered)

Channel forum; predicted intent billing_query (1.00); route auto_respond; final auto_respond; rule `none`.

**Ticket**

> Invoice higher than expected
> 
> bill is very high this month. i not understand the charge. please explain what is this.

**Sent to the customer**

```
This is an automated reply from CloudServe Support. It is based on our help articles listed below.

Hello,

Open the usage breakdown for the period to see charges by service and environment. Look for resources left running in staging or development environments, which are billed at the same rate as production. Check the billing period dates at the top of the invoice; the period runs from the anniversary of the subscription date, not necessarily the first of the month. Set a usage alert on the billing page so that unexpected accrual is noticed during the period rather than at the end of it.

If this does not solve the problem, reply to this message and a member of our support team will help you.

Sources:
- Understanding your invoice and usage breakdown (DOC-BILL-001), reviewed today
```

**Answer sentences and their citations**

1. Open the usage breakdown for the period to see charges by service and environment.  [cites: DOC-BILL-001#c01]
2. Look for resources left running in staging or development environments, which are billed at the same rate as production.  [cites: DOC-BILL-001#c01]
3. Check the billing period dates at the top of the invoice; the period runs from the anniversary of the subscription date, not necessarily the first of the month.  [cites: DOC-BILL-001#c01]
4. Set a usage alert on the billing page so that unexpected accrual is noticed during the period rather than at the end of it.  [cites: DOC-BILL-001#c01]

**Cited passages**

*DOC-BILL-001#c01* (Understanding your invoice and usage breakdown)

> ## Resolution
> 
> 1. Open the usage breakdown for the period, which itemises charges by service and by environment.
> 2. Look for resources in staging or development environments, which are billed at the same rate as production.
> 3. Check the billing period dates at the top of the invoice. The period runs from the anniversary of the subscription date.
> 4. Set a usage alert on the billing page so that unexpected accrual is noticed during the period rather than at the end of it.
> 
> ## Notes
> 
> Invoices are finalised three days after the period ends. Adjustments requested before finalisation appear on the same invoice.

---

## 53. VAL-0074 (answered)

Channel docs_comment; predicted intent account_access (1.00); route auto_respond; final auto_respond; rule `none`.

**Ticket**

> Remove a departing team member
> 
> We are tightening permissions after a review and I want to understand how group membership interacts with directly assigned roles.

**Sent to the customer**

```
This is an automated reply from CloudServe Support. It is based on our help articles listed below.

Hello,

Check the effective permissions view for the user, which resolves direct roles and group memberships together. Remove a departing user rather than only changing their password, and revoke any API keys they created.

If this does not solve the problem, reply to this message and a member of our support team will help you.

Sources:
- Managing team members, roles and permissions (DOC-ACCT-001), reviewed today
```

**Answer sentences and their citations**

1. Check the effective permissions view for the user, which resolves direct roles and group memberships together.  [cites: DOC-ACCT-001#c01]
2. Remove a departing user rather than only changing their password, and revoke any API keys they created.  [cites: DOC-ACCT-001#c01]

**Cited passages**

*DOC-ACCT-001#c01* (Managing team members, roles and permissions)

> ## Resolution
> 
> 1. Check the effective permissions view for the user, which resolves direct roles and group memberships together.
> 2. Confirm the invitation was accepted. Pending invitations appear in a separate section and expire after seven days.
> 3. Remove a departing user rather than only changing their password, and revoke any API keys they created.
> 4. Prefer group membership to direct role assignment, so that access can be reviewed in one place.
> 
> ## Notes
> 
> Removing the last account owner is not permitted. Transfer ownership before removing the account.

---

## 54. VAL-0075 (answered)

Channel docs_comment; predicted intent api_key_issue (1.00); route auto_respond; final auto_respond; rule `none`.

**Ticket**

> API key returning 401
> 
> A key can read fine but every write returns a permission error. I created it myself and I thought I gave it full access.

**Sent to the customer**

```
This is an automated reply from CloudServe Support. It is based on our help articles listed below.

Hello,

Check the API keys page for the key's status and expiry. Revoked and expired keys are listed with the date and the user who acted. Review the scopes attached to the key. Read-only keys cannot write, and project-scoped keys cannot reach organisation endpoints. To rotate without downtime, create the replacement key first, deploy it, confirm traffic has moved, then revoke the old key.

If this does not solve the problem, reply to this message and a member of our support team will help you.

Sources:
- API key rotation and scope management (DOC-AUTH-004), reviewed today
```

**Answer sentences and their citations**

1. Check the API keys page for the key's status and expiry. Revoked and expired keys are listed with the date and the user who acted.  [cites: DOC-AUTH-004#c01]
2. Review the scopes attached to the key. Read-only keys cannot write, and project-scoped keys cannot reach organisation endpoints.  [cites: DOC-AUTH-004#c01]
3. To rotate without downtime, create the replacement key first, deploy it, confirm traffic has moved, then revoke the old key.  [cites: DOC-AUTH-004#c01]

**Cited passages**

*DOC-AUTH-004#c01* (API key rotation and scope management)

> ## Resolution
> 
> 1. Check the API keys page for the key's status and expiry. Revoked and expired keys are listed with the date and the user who acted.
> 2. Review the scopes attached to the key. Read-only keys cannot write, and project-scoped keys cannot reach organisation endpoints.
> 3. To rotate without downtime, create the replacement key first, deploy it, confirm traffic has moved, then revoke the old key.
> 4. If a key has been exposed publicly, revoke it immediately rather than waiting for the rotation window.
> 
> ## Notes
> 
> Keys issued to individual users are removed when that user is deleted. Use service accounts for anything running in production.

---

## 55. VAL-0076 (escalated)

Channel email; predicted intent data_residency (1.00); route escalate; final escalate; rule `must_escalate_intent:data_residency`.

**Ticket**

> Need data to stay in the EU
> 
> We need our data to remain within the EU for a contract we are signing. Our organisation was created some time ago and I am not sure which region it is in.

**Customer received (holding message)**

```
Thank you for contacting CloudServe Support. A member of our support team will look at your request and reply to you.
```

**Escalation package for the agent**

- Summary: data_residency (1.00), medium urgency, email: Need data to stay in the EU
- Restatement: Need data to stay in the EU: We need our data to remain within the EU for a contract we are signing.
- Reason: intent data_residency must always escalate (FR-12)

**Sources retrieved for the agent**

*DOC-DATA-003#c00* (Data residency and regional storage)

> # Data residency and regional storage
> 
> **Applies to:** Business and Enterprise plans
> 
> ## Symptoms
> 
> - A customer requires data to remain in a specific region
> - Latency is high for users far from the primary region
> - A compliance review has asked where data is held
> 
> ## Common causes
> 
> - The organisation was created in a region that no longer suits the requirement
> - Read traffic is being served from the primary region only
> - Backups are replicated to a second region by default
> 
> ## Resolution

*DOC-DATA-003#c01* (Data residency and regional storage)

> ## Resolution
> 
> 1. Check the region shown on the organisation settings page. This is fixed at creation and determines where primary data is stored.
> 2. Enable read replicas in additional regions to reduce latency for distant users without moving primary storage.
> 3. Review the backup replication setting if a single-region requirement applies, since cross-region replication is enabled by default.
> 4. Migrating an organisation between regions requires a planned migration with support and involves a maintenance window.
> 
> ## Notes
> 
> Metadata such as account names and billing records is stored centrally regardless of the data region.

---

## 56. VAL-0077 (answered)

Channel chat; predicted intent billing_query (1.00); route auto_respond; final auto_respond; rule `none`.

**Ticket**

> Our billing period does not seem to match the calendar month, which is making reconciliation difficult. Is that expected?

**Sent to the customer**

```
This is an automated reply from CloudServe Support. It is based on our help articles listed below.

Hello,

The billing period runs from the anniversary of the subscription date rather than the first of the month.

If this does not solve the problem, reply to this message and a member of our support team will help you.

Sources:
- Understanding your invoice and usage breakdown (DOC-BILL-001), reviewed today
```

**Answer sentences and their citations**

1. The billing period runs from the anniversary of the subscription date rather than the first of the month.  [cites: DOC-BILL-001#c01]

**Cited passages**

*DOC-BILL-001#c01* (Understanding your invoice and usage breakdown)

> ## Resolution
> 
> 1. Open the usage breakdown for the period, which itemises charges by service and by environment.
> 2. Look for resources in staging or development environments, which are billed at the same rate as production.
> 3. Check the billing period dates at the top of the invoice. The period runs from the anniversary of the subscription date.
> 4. Set a usage alert on the billing page so that unexpected accrual is noticed during the period rather than at the end of it.
> 
> ## Notes
> 
> Invoices are finalised three days after the period ends. Adjustments requested before finalisation appear on the same invoice.

---

## 57. VAL-0078 (escalated)

Channel docs_comment; predicted intent database_issue (1.00); route escalate; final escalate; rule `no_retrieval_hit`.

**Ticket**

> Database restore taking hours
> 
> connection not available error coming. we scale up service then problem start. please check.

**Customer received (holding message)**

```
Thank you for contacting CloudServe Support. A member of our support team will look at your request and reply to you.
```

**Escalation package for the agent**

- Summary: database_issue (1.00), medium urgency, docs_comment: Database restore taking hours
- Restatement: Database restore taking hours: connection not available error coming.
- Reason: no supporting passage: nothing passed the relevance cutoff (No passage at or above cutoff 0.51; best was DOC-PERF-003#c00 at 0.41.); escalated without a draft or a model call

**Sources retrieved for the agent**: none passed the cutoff

---

## 58. VAL-0079 (escalated)

Channel email; predicted intent data_residency (1.00); route escalate; final escalate; rule `must_escalate_intent:data_residency`.

**Ticket**

> Need data to stay in the EU
> 
> one of our customers has asked for written confirmation of where their data is physically stored. Can you please point me to something I can share with them? kindly check and revert.

**Customer received (holding message)**

```
Thank you for contacting CloudServe Support. A member of our support team will look at your request and reply to you.
```

**Escalation package for the agent**

- Summary: data_residency (1.00), medium urgency, email: Need data to stay in the EU
- Restatement: Need data to stay in the EU: one of our customers has asked for written confirmation of where their data is physically stored.
- Reason: intent data_residency must always escalate (FR-12)

**Sources retrieved for the agent**

*DOC-DATA-003#c00* (Data residency and regional storage)

> # Data residency and regional storage
> 
> **Applies to:** Business and Enterprise plans
> 
> ## Symptoms
> 
> - A customer requires data to remain in a specific region
> - Latency is high for users far from the primary region
> - A compliance review has asked where data is held
> 
> ## Common causes
> 
> - The organisation was created in a region that no longer suits the requirement
> - Read traffic is being served from the primary region only
> - Backups are replicated to a second region by default
> 
> ## Resolution

*DOC-DATA-003#c01* (Data residency and regional storage)

> ## Resolution
> 
> 1. Check the region shown on the organisation settings page. This is fixed at creation and determines where primary data is stored.
> 2. Enable read replicas in additional regions to reduce latency for distant users without moving primary storage.
> 3. Review the backup replication setting if a single-region requirement applies, since cross-region replication is enabled by default.
> 4. Migrating an organisation between regions requires a planned migration with support and involves a maintenance window.
> 
> ## Notes
> 
> Metadata such as account names and billing records is stored centrally regardless of the data region.

---

## 59. VAL-0080 (answered)

Channel chat; predicted intent deployment_failure (1.00); route auto_respond; final auto_respond; rule `none`.

**Ticket**

> Builds that worked last week are now failing during dependency resolution. We have not changed our code at all. This is blocking a release we had planned for yesterday morning.

**Sent to the customer**

```
This is an automated reply from CloudServe Support. It is based on our help articles listed below.

Hello,

Pin your dependencies with exact versions and commit the lock file to resolve dependency resolution failures. Compare the runtime version declared in your build configuration against the version you use locally. Clear the build cache from the settings page and trigger a fresh build to rule out a corrupted artefact.

If this does not solve the problem, reply to this message and a member of our support team will help you.

Sources:
- Build failures caused by dependency resolution (DOC-DEPLOY-003), reviewed today
```

**Answer sentences and their citations**

1. Pin your dependencies with exact versions and commit the lock file to resolve dependency resolution failures.  [cites: DOC-DEPLOY-003#c01, DOC-DEPLOY-003#c00]
2. Compare the runtime version declared in your build configuration against the version you use locally.  [cites: DOC-DEPLOY-003#c01]
3. Clear the build cache from the settings page and trigger a fresh build to rule out a corrupted artefact.  [cites: DOC-DEPLOY-003#c01]

**Cited passages**

*DOC-DEPLOY-003#c01* (Build failures caused by dependency resolution)

> ## Resolution
> 
> 1. Pin your dependencies with exact versions and commit the lock file. Unpinned dependencies are the cause in the large majority of cases of this kind.
> 2. Compare the runtime version declared in your build configuration against the version you use locally.
> 3. Clear the build cache from the settings page and trigger a fresh build to rule out a corrupted artefact.
> 4. If a specific dependency is failing to resolve, check whether its registry is reachable from the build network.
> 
> ## Notes
> 
> Build logs retain the full resolution output for thirty days, which is usually enough to identify which version changed.

*DOC-DEPLOY-003#c00* (Build failures caused by dependency resolution)

> # Build failures caused by dependency resolution
> 
> **Applies to:** Build Service
> 
> ## Symptoms
> 
> - Builds that previously succeeded now fail without code changes
> - The build works locally but fails in the pipeline
> - Dependency resolution takes far longer than usual
> 
> ## Common causes
> 
> - An unpinned dependency released a new incompatible version
> - The build environment uses a different language runtime than the local machine
> - The dependency cache holds a partially written artefact
> 
> ## Resolution

