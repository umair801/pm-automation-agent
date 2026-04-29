# Scenario 04 — REIReply CRM Capture

## Purpose
Watch REIReply for new or updated CRM records and forward them to the
FastAPI capture pipeline as action items. Also aggregates weekly metrics
for the Scorecard DB.

---

## Part A: Real-Time Record Capture

### Trigger Module
**App:** REIReply (via Make.com HTTP module or native connector if available)  
**Module:** Watch Records / Webhook  
**Label:** Watch REIReply for New Records  

> If REIReply has a native Make.com connector, use Watch Records.
> If not, configure a REIReply webhook to POST to a Make.com webhook URL,
> then use the Webhooks module as the trigger.

### Settings (Webhook trigger fallback)
| Field | Value |
|---|---|
| App | Webhooks |
| Module | Custom Webhook |
| Webhook name | reireply-new-record |
| IP restriction | REIReply outbound IPs if available |

---

### Module 2 — HTTP POST to FastAPI

**App:** HTTP  
**Module:** Make a Request  

| Field | Value |
|---|---|
| URL | `{{BASE_URL}}/capture/postmark` |
| Method | POST |
| Body type | Raw |
| Content type | JSON (application/json) |

### Request Body
```json
{
  "MessageID": "reireply-{{1.id}}",
  "From": "reireply@internal",
  "To": "capture@internal",
  "Subject": "REIReply: {{1.name}} — {{1.status}}",
  "TextBody": "Contact: {{1.name}}\nPhone: {{1.phone}}\nEmail: {{1.email}}\nStatus: {{1.status}}\nNotes: {{1.notes}}\nUpdated: {{1.updatedAt}}",
  "Date": "{{formatDate(now; \"YYYY-MM-DDTHH:mm:ssZ\")}}"
}
```

---

## Part B: Weekly Scorecard Aggregation

This runs weekly and feeds the `/notion/scorecard` endpoint.
See Scenario 08 for the full Scorecard Aggregator scenario, which
combines REIReply and OpenPhone data before calling the endpoint.

---

## Scenario Settings (Part A)
| Setting | Value |
|---|---|
| Name | PM — REIReply CRM Capture |
| Active | Yes |
| Scheduling | Real-time or every 15 minutes |
| Max cycles per run | 10 |
| Timeout | 40 seconds |
