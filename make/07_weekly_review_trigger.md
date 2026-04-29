# Scenario 07 — Weekly Review Trigger

## Purpose
Trigger the Weekly Reviewer Agent every Monday morning. The agent queries
all active items from the Notion Items DB, generates a structured weekly
digest grouped by project, saves it to Supabase, and delivers it via
Postmark email.

---

## Trigger Module
**App:** Schedule  
**Module:** (Built-in Make.com scheduler)  
**Label:** Monday 08:00 ET  

### Settings
| Field | Value |
|---|---|
| Run scenario | Every week |
| Day | Monday |
| At | 08:00 |
| Timezone | America/New_York |

---

## Module 2 — HTTP POST to FastAPI

**App:** HTTP  
**Module:** Make a Request  

| Field | Value |
|---|---|
| URL | `{{BASE_URL}}/notion/digest/weekly` |
| Method | POST |
| Body type | Raw |
| Content type | JSON (application/json) |
| Body | `{}` (empty JSON object, no payload required) |
| Parse response | Yes |
| Timeout | 120 seconds |

> The weekly digest queries up to 100 Notion items and calls Claude.
> Allow 120 seconds timeout to be safe.

---

## Module 3 — Filter: Check for delivery success
**App:** Flow Control  
**Module:** Filter  
**Label:** Only continue if delivered  

### Condition
```
{{2.delivered}} equals: true
```

---

## Module 4 — Error Alert (failure path)
If delivery failed, send an admin alert.

**App:** Email  
**Module:** Send an Email  

| Field | Value |
|---|---|
| To | Admin email address |
| Subject | Weekly digest delivery failed — {{formatDate(now; "YYYY-MM-DD")}} |
| Content | Weekly review digest failed to deliver. Check Supabase pm_audit_log for details. |

---

## Scenario Settings
| Setting | Value |
|---|---|
| Name | PM — Weekly Review Trigger |
| Active | Yes |
| Scheduling | Every Monday at 08:00 ET |
| Max cycles per run | 1 |
| Timeout | 150 seconds |

---

## Expected Response from FastAPI
```json
{
  "digest_type": "weekly",
  "item_count": null,
  "delivered": true,
  "saved_id": "uuid-of-supabase-record"
}
```

---

## Notes
- This scenario runs 30 minutes before the Scorecard Aggregator (Scenario 08)
  so the weekly digest is delivered before scorecard metrics arrive.
- If the client wants the digest on a different day or time, update the
  scheduler only. No code changes required.
