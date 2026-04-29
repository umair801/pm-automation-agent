# Scenario 01 — Gmail Capture

## Purpose
Watch two Gmail accounts for new emails and forward them to the FastAPI
capture pipeline as structured action items.

---

## Trigger Module
**App:** Gmail  
**Module:** Watch Emails  
**Label:** Watch Gmail Inbox  

### Settings
| Field | Value |
|---|---|
| Connection | Gmail Account 1 (repeat scenario for Account 2) |
| Folder | INBOX |
| Criteria | All emails |
| Max results | 10 |
| Mark as read | No (preserve email state) |

---

## Module 2 — Iterator (optional)
If Watch Emails returns multiple emails in one poll, add an Iterator module
to process each email individually through the rest of the scenario.

---

## Module 3 — HTTP POST to FastAPI

**App:** HTTP  
**Module:** Make a Request  

### Settings
| Field | Value |
|---|---|
| URL | `{{BASE_URL}}/capture/postmark` |
| Method | POST |
| Headers | Content-Type: application/json |
| Body type | Raw |
| Content type | JSON (application/json) |

### Request Body
```json
{
  "MessageID": "{{2.id}}",
  "From": "{{2.from.value[].address}}",
  "To": "{{2.to.value[].address}}",
  "Subject": "{{2.subject}}",
  "TextBody": "{{2.text}}",
  "HtmlBody": "{{2.html}}",
  "Date": "{{formatDate(2.date; \"YYYY-MM-DDTHH:mm:ssZ\")}}"
}
```

> Field references use Make.com module numbering. Adjust the module number
> (e.g. `2.`) to match your actual scenario module position.

---

## Module 4 — Error Handler
**App:** Flow Control  
**Module:** Resume  

Add a route that catches HTTP errors (non-2xx) and logs them:

| Field | Value |
|---|---|
| Log target | Make.com Data Store — table: `capture_errors` |
| Fields to log | Source, Subject, Error code, Timestamp |

---

## Scenario Settings
| Setting | Value |
|---|---|
| Name | PM — Gmail Capture |
| Active | Yes |
| Scheduling | Real-time (as emails arrive) |
| Max cycles per run | 10 |
| Timeout | 40 seconds |

---

## Notes
- Repeat this scenario for the second Gmail account with a separate connection.
- Do not mark emails as read in Gmail. The client reads emails independently.
- If the client wants to filter emails (e.g. only emails from hospital domains),
  add a Filter module between Watch Emails and the HTTP POST that checks
  `From` contains the target domain.
