# Make.com Scenarios — PM Automation Agent
## Master Overview

This document is the complete reference for all Make.com scenarios in this project.
Make.com is the sole workflow orchestrator. It handles all scheduled triggers,
input source polling, and calls to the FastAPI backend.

---

## Scenario Index

| # | Scenario Name | Trigger | Calls | Schedule |
|---|---|---|---|---|
| 1 | Gmail Capture | Gmail Watch Emails | POST /capture/postmark | Real-time |
| 2 | Hospital Email Capture | IMAP Watch Emails | POST /capture/postmark | Real-time |
| 3 | Google Calendar Capture | Calendar Watch Events | POST /capture/raycast | Real-time |
| 4 | REIReply CRM Capture | REIReply Watch Records | POST /capture/postmark | Real-time |
| 5 | Asana Capture (Sunsetting) | Asana Watch Tasks | POST /capture/raycast | Real-time |
| 6 | Daily Pruner Trigger | Schedule | POST /notion/digest/daily | Daily 07:00 ET |
| 7 | Weekly Review Trigger | Schedule | POST /notion/digest/weekly | Monday 08:00 ET |
| 8 | Scorecard Aggregator | Schedule | POST /notion/scorecard | Monday 08:30 ET |

---

## Architecture Notes

- All FastAPI endpoints are deployed on Railway at `https://<your-railway-domain>.railway.app`
- All HTTP calls from Make.com use the `Content-Type: application/json` header
- GroupMe, Slack, and OpenPhone deliver directly to FastAPI via webhook (no Make.com scenario needed)
- Postmark delivers inbound email directly to FastAPI via webhook (no Make.com scenario needed)
- Twilio delivers inbound SMS directly to FastAPI via webhook (no Make.com scenario needed)
- Raycast and iOS Shortcut deliver directly to FastAPI via POST (no Make.com scenario needed)
- Granola delivers meeting transcripts directly to FastAPI via POST (no Make.com scenario needed)

---

## Base URL Variable

In every Make.com scenario, set a custom variable or use a Data Store entry:

```
BASE_URL = https://<your-railway-domain>.railway.app
```

Replace `<your-railway-domain>` with your actual Railway subdomain after deployment.

---

## Shared HTTP Module Settings

All HTTP POST calls to FastAPI use these shared settings:

| Setting | Value |
|---|---|
| Method | POST |
| Headers | Content-Type: application/json |
| Parse response | Yes |
| Timeout | 30 seconds |
| Follow redirect | Yes |
| Error handling | Resume + log to Data Store |
