# PM Automation Agent

A multi-source AI-driven project management system built by [Datawebify](https://datawebify.com).

Captures action items from 8+ sources, runs them through 6 Claude API agents, and writes structured output into a Notion workspace with 6 linked databases.

---

## Deployment

Live at **[pm.datawebify.com](https://pm.datawebify.com)**. Deployed on Railway with Docker. Health check at `/health`.

---

## Architecture

**Input Sources**
- 2 Gmail accounts
- 4 Hospital email accounts (IMAP / Postmark forward)
- GroupMe (webhook)
- Slack (webhook)
- Google Calendar (Make.com)
- OpenPhone (webhook)
- Asana (read-only, sunsetting)
- REIReply CRM (Make.com)

**Capture Endpoints**
- Postmark inbound email
- Twilio SMS bot
- Raycast hotkey (JSON POST)
- iOS Shortcut voice memo (Whisper transcription)
- Granola meeting transcript

**Claude API Agents**
1. Triage Agent — classify source, extract intent, tag item type
2. Prioritizer Agent — score urgency and importance, assign priority
3. Delegator Agent — assign to person from People DB
4. Weekly Reviewer Agent — generate weekly digest across all projects
5. Daily Pruner Agent — identify and flag stale or duplicate items
6. Project Assistant Agent — on-demand Q&A against Notion workspace

**Notion Databases**
- Items DB
- Projects DB
- People DB
- Decisions DB
- SOPs DB
- Scorecard DB

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Uvicorn |
| AI | Claude API (Anthropic SDK) |
| Workspace | Notion API |
| Orchestration | Make.com |
| Email capture | Postmark |
| SMS | Twilio |
| Voice transcription | Whisper API |
| Database | Supabase (PostgreSQL) |
| Deployment | Docker + Railway |
| Language | Python 3.12 |

---

## Project Structure

```
app/
  agents/         # 6 Claude API agents
  api/            # FastAPI routers (capture, webhooks, notion, health)
  clients/        # Claude and Notion SDK wrappers
  models/         # Pydantic v2 data models
  services/       # Whisper, digest, and scorecard services
  utils/          # Config and logger
make/             # Make.com scenario documentation (8 scenarios)
supabase/         # Database schema SQL
tests/            # Pytest test suite (44 tests)
```

---

```
POST /capture/postmark     — Inbound email
POST /capture/twilio       — Inbound SMS
POST /capture/raycast      — Quick capture
POST /capture/ios-voice    — Voice memo
POST /capture/granola      — Meeting transcript
POST /webhooks/groupme     — GroupMe events
POST /webhooks/slack       — Slack events
POST /webhooks/openphone   — OpenPhone events
POST /notion/ask           — Project assistant Q&A
POST /notion/digest/daily  — Trigger daily pruner
POST /notion/digest/weekly — Trigger weekly review
POST /notion/scorecard     — Write scorecard entry
GET  /notion/items         — Query Items DB
GET  /health               — Health check
```

---

Built by [Muhammad Umair](https://datawebify.com) — Agentic AI Specialist
