# Scenario 03 — Google Calendar Capture

## Purpose
Watch a Google Calendar for new or updated events and forward them to the
FastAPI capture pipeline as meeting notes or action items.

---

## Trigger Module
**App:** Google Calendar  
**Module:** Watch Events  
**Label:** Watch Calendar for New Events  

### Settings
| Field | Value |
|---|---|
| Connection | Client Google account |
| Calendar | Primary calendar (or specify by name) |
| Watch | New events only |
| Max results | 10 |

---

## Module 2 — Filter
**App:** Flow Control  
**Module:** Filter  
**Label:** Skip cancelled events  

### Condition
```
Status does not equal: cancelled
AND Summary (title) is not empty
```

---

## Module 3 — HTTP POST to FastAPI

**App:** HTTP  
**Module:** Make a Request  

### Settings
| Field | Value |
|---|---|
| URL | `{{BASE_URL}}/capture/raycast` |
| Method | POST |
| Body type | Raw |
| Content type | JSON (application/json) |

### Request Body
```json
{
  "text": "Calendar event: {{2.summary}}\nStart: {{formatDate(2.start.dateTime; \"YYYY-MM-DD HH:mm\")}}\nEnd: {{formatDate(2.end.dateTime; \"YYYY-MM-DD HH:mm\")}}\nLocation: {{2.location}}\nDescription: {{2.description}}\nAttendees: {{join(map(2.attendees; \"email\"); \", \")}}",
  "source": "google_calendar",
  "project_hint": null,
  "tags": ["calendar", "meeting"]
}
```

> The Raycast capture endpoint accepts any plain text payload, making it
> a good general-purpose capture target for Make.com modules that do not
> have a dedicated FastAPI endpoint.

---

## Module 4 — Error Handler
| Field | Value |
|---|---|
| Log target | Make.com Data Store — table: `capture_errors` |
| Fields to log | Source (google_calendar), Event title, Error code, Timestamp |

---

## Scenario Settings
| Setting | Value |
|---|---|
| Name | PM — Google Calendar Capture |
| Active | Yes |
| Scheduling | Real-time (as events are created) |
| Max cycles per run | 10 |
| Timeout | 40 seconds |
