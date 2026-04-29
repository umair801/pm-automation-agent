# Scenario 06 — Daily Pruner Trigger

## Purpose
Trigger the Daily Pruner Agent every morning. The agent identifies stale
and duplicate items in the Notion Items DB, generates a pruning report,
saves it to Supabase, and delivers it via Postmark email.

---

## Trigger Module
**App:** Schedule  
**Module:** (Built-in Make.com scheduler)  
**Label:** Daily 07:00 ET  

### Settings
| Field | Value |
|---|---|
| Run scenario | Every day |
| At | 07:00 |
| Timezone | America/New_York |

---

## Module 2 — HTTP POST to FastAPI

**App:** HTTP  
**Module:** Make a Request  

| Field | Value |
|---|---|
| URL | `{{BASE_URL}}/notion/digest/daily` |
| Method | POST |
| Body type | Raw |
| Content type | JSON (application/json) |
| Body | `{}` (empty JSON object, no payload required) |
| Parse response | Yes |
| Timeout | 60 seconds |

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
If delivery failed, send a Slack or email alert.

**App:** HTTP  
**Module:** Make a Request  

| Field | Value |
|---|---|
| URL | `{{BASE_URL}}/webhooks/slack` |
| Method | POST |
| Body | `{"type": "event_callback", "event": {"type": "message", "text": "Daily pruner digest delivery failed. Check Supabase pm_audit_log."}}` |

> Alternatively, use the Make.com Email module to alert the admin directly.

---

## Scenario Settings
| Setting | Value |
|---|---|
| Name | PM — Daily Pruner Trigger |
| Active | Yes |
| Scheduling | Daily at 07:00 ET |
| Max cycles per run | 1 |
| Timeout | 90 seconds |

---

## Expected Response from FastAPI
```json
{
  "digest_type": "daily",
  "item_count": 5,
  "delivered": true,
  "saved_id": "uuid-of-supabase-record"
}
```
