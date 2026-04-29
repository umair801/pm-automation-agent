# Scenario 02 — Hospital Email Capture

## Purpose
Watch up to 4 hospital email accounts via IMAP and forward new emails
to the FastAPI capture pipeline. Used when direct Postmark forwarding
is not available for a hospital account.

---

## Trigger Module
**App:** Email (IMAP)  
**Module:** Watch Emails  
**Label:** Watch Hospital IMAP Inbox  

### Settings
| Field | Value |
|---|---|
| Connection | Hospital Email Account (IMAP connection) |
| Folder | INBOX |
| Criteria | Unread emails only |
| Max results | 5 |
| Mark as read | Yes (prevents duplicate processing) |

### IMAP Connection Setup
| Field | Value |
|---|---|
| Host | Hospital mail server hostname |
| Port | 993 (IMAP SSL) |
| Username | Hospital email address |
| Password | App password or IMAP credentials |
| TLS | Yes |

> Repeat this scenario for each of the 4 hospital email accounts.
> Each account gets its own Make.com scenario and IMAP connection.

---

## Module 2 — Filter
**App:** Flow Control  
**Module:** Filter  
**Label:** Skip auto-replies and delivery notices  

### Condition
```
Subject does not contain: "Auto-Reply"
AND Subject does not contain: "Delivery Status"
AND Subject does not contain: "Out of Office"
AND From does not contain: "mailer-daemon"
```

---

## Module 3 — HTTP POST to FastAPI

**App:** HTTP  
**Module:** Make a Request  

### Settings
| Field | Value |
|---|---|
| URL | `{{BASE_URL}}/capture/postmark` |
| Method | POST |
| Body type | Raw |
| Content type | JSON (application/json) |

### Request Body
```json
{
  "MessageID": "{{2.id}}",
  "From": "{{2.from}}",
  "To": "{{2.to}}",
  "Subject": "{{2.subject}}",
  "TextBody": "{{2.text}}",
  "HtmlBody": "{{2.html}}",
  "Date": "{{formatDate(2.date; \"YYYY-MM-DDTHH:mm:ssZ\")}}"
}
```

---

## Module 4 — Error Handler
| Field | Value |
|---|---|
| Log target | Make.com Data Store — table: `capture_errors` |
| Fields to log | Source (hospital_email), Subject, Error code, Timestamp |

---

## Scenario Settings
| Setting | Value |
|---|---|
| Name | PM — Hospital Email Capture (Account N) |
| Active | Yes |
| Scheduling | Every 5 minutes |
| Max cycles per run | 5 |
| Timeout | 40 seconds |

---

## Fallback: Manual Email Forward
If IMAP access is not available for a hospital account, the client can
set up an auto-forward rule in the hospital email client to Postmark's
inbound address. Postmark then delivers directly to `POST /capture/postmark`
with no Make.com scenario required.
