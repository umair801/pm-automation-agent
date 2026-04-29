# Scenario 08 — Scorecard Aggregator

## Purpose
Every Monday morning, pull the previous week's metrics from REIReply and
OpenPhone, aggregate them, and POST the combined payload to the FastAPI
scorecard endpoint, which writes a new entry to the Notion Scorecard DB.

---

## Trigger Module
**App:** Schedule  
**Module:** (Built-in Make.com scheduler)  
**Label:** Monday 08:30 ET  

### Settings
| Field | Value |
|---|---|
| Run scenario | Every week |
| Day | Monday |
| At | 08:30 |
| Timezone | America/New_York |

---

## Module 2 — Get REIReply Weekly Metrics

**App:** HTTP (or REIReply native connector if available)  
**Module:** Make a Request  
**Label:** Fetch REIReply weekly summary  

| Field | Value |
|---|---|
| URL | REIReply API endpoint for weekly summary |
| Method | GET |
| Headers | Authorization: Bearer {{REIReply API Key}} |
| Parse response | Yes |

### Expected REIReply Response Fields
| Field | Description |
|---|---|
| `leads_added` | New leads added this week |
| `deals_closed` | Deals closed this week |
| `follow_ups_sent` | Follow-up messages sent |
| `appointments_set` | Appointments booked |

> If REIReply does not have a summary API endpoint, use the REIReply
> Make.com module to Search Records with a date filter for the past 7 days,
> then use a Math module to count results.

---

## Module 3 — Get OpenPhone Weekly Metrics

**App:** HTTP  
**Module:** Make a Request  
**Label:** Fetch OpenPhone weekly summary  

| Field | Value |
|---|---|
| URL | `https://api.openphone.com/v1/calls?from={{formatDate(addDays(now; -7); "YYYY-MM-DD")}}&to={{formatDate(now; "YYYY-MM-DD")}}` |
| Method | GET |
| Headers | Authorization: {{OpenPhone API Key}} |
| Parse response | Yes |

### Expected OpenPhone Response Fields
| Field | Description |
|---|---|
| `calls_made` | Total outbound calls |
| `calls_answered` | Calls that were answered |
| `sms_sent` | SMS messages sent |
| `voicemails_left` | Calls that went to voicemail |
| `avg_call_duration_seconds` | Average call duration in seconds |

---

## Module 4 — HTTP POST to FastAPI Scorecard

**App:** HTTP  
**Module:** Make a Request  

| Field | Value |
|---|---|
| URL | `{{BASE_URL}}/notion/scorecard` |
| Method | POST |
| Body type | Raw |
| Content type | JSON (application/json) |
| Parse response | Yes |
| Timeout | 60 seconds |

### Request Body
```json
{
  "week_label": "{{formatDate(now; \"GGGG-[W]WW\")}}",
  "reireply_data": {
    "leads_added": "{{2.leads_added}}",
    "deals_closed": "{{2.deals_closed}}",
    "follow_ups_sent": "{{2.follow_ups_sent}}",
    "appointments_set": "{{2.appointments_set}}"
  },
  "openphone_data": {
    "calls_made": "{{3.calls_made}}",
    "calls_answered": "{{3.calls_answered}}",
    "sms_sent": "{{3.sms_sent}}",
    "voicemails_left": "{{3.voicemails_left}}",
    "avg_call_duration_seconds": "{{3.avg_call_duration_seconds}}"
  }
}
```

> Module numbers `2.` and `3.` refer to the REIReply and OpenPhone modules
> respectively. Adjust to match your actual scenario module positions.

> The `week_label` uses Make.com's ISO week format: `GGGG-[W]WW`
> which produces strings like `2026-W18`. This matches the format
> expected by `ScorecardService._current_week_label()`.

---

## Module 5 — Error Alert (failure path)
**App:** Email  
**Module:** Send an Email  

| Field | Value |
|---|---|
| To | Admin email address |
| Subject | Scorecard write failed — {{formatDate(now; "YYYY-MM-DD")}} |
| Content | Scorecard aggregation failed. Check Supabase pm_audit_log. REIReply response: {{2.statusCode}}. OpenPhone response: {{3.statusCode}}. |

---

## Scenario Settings
| Setting | Value |
|---|---|
| Name | PM — Scorecard Aggregator |
| Active | Yes |
| Scheduling | Every Monday at 08:30 ET |
| Max cycles per run | 1 |
| Timeout | 90 seconds |

---

## Expected Response from FastAPI
```json
{
  "page_id": "notion-page-uuid",
  "week_label": "2026-W18",
  "metrics": {
    "leads_added": 12,
    "deals_closed": 2,
    "follow_ups_sent": 45,
    "appointments_set": 6,
    "calls_made": 87,
    "calls_answered": 54,
    "sms_sent": 123,
    "voicemails_left": 33,
    "avg_call_duration_minutes": 4.2,
    "call_answer_rate_pct": 62.1
  }
}
```

---

## Notes
- This scenario runs at 08:30, 30 minutes after the Weekly Review Trigger (08:00),
  so they do not compete for Claude API capacity at the same moment.
- If either the REIReply or OpenPhone API call fails, the scorecard endpoint
  still runs with the available data. Missing fields default to 0 in
  `ScorecardService._compute_metrics()`.
- To backfill a missed week, call `POST /notion/scorecard` manually with
  the `week_label` field set to the target week (e.g. `"2026-W17"`).
