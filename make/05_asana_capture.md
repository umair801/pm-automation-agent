# Scenario 05 — Asana Capture (Sunsetting)

## Purpose
Read-only watch of Asana tasks for migration into the Notion Items DB.
This scenario is temporary and will be deactivated once all active Asana
tasks have been migrated. No new tasks are created in Asana after migration.

---

## Status
**SUNSETTING.** This scenario is active only during the migration window.
Deactivate after confirming all Asana tasks are captured in Notion.

---

## Trigger Module
**App:** Asana  
**Module:** Watch Tasks  
**Label:** Watch Asana for New or Updated Tasks  

### Settings
| Field | Value |
|---|---|
| Connection | Client Asana account (read-only token) |
| Workspace | Client workspace |
| Project | All projects (or specify migration scope) |
| Watch | New tasks only |
| Max results | 20 |

---

## Module 2 — Filter
**App:** Flow Control  
**Module:** Filter  
**Label:** Skip completed tasks  

### Condition
```
Completed does not equal: true
AND Name is not empty
```

---

## Module 3 — HTTP POST to FastAPI

**App:** HTTP  
**Module:** Make a Request  

| Field | Value |
|---|---|
| URL | `{{BASE_URL}}/capture/raycast` |
| Method | POST |
| Body type | Raw |
| Content type | JSON (application/json) |

### Request Body
```json
{
  "text": "Asana task: {{2.name}}\nProject: {{2.projects[].name}}\nAssignee: {{2.assignee.name}}\nDue: {{formatDate(2.due_on; \"YYYY-MM-DD\")}}\nNotes: {{2.notes}}",
  "source": "asana",
  "project_hint": "{{2.projects[1].name}}",
  "tags": ["asana", "migration"]
}
```

---

## Module 4 — Asana Mark Task (Optional)
After successful capture, add a tag to the Asana task to mark it as migrated.

**App:** Asana  
**Module:** Update a Task  

| Field | Value |
|---|---|
| Task ID | `{{2.id}}` |
| Tags | Add tag: "migrated-to-notion" |

---

## Scenario Settings
| Setting | Value |
|---|---|
| Name | PM — Asana Capture (Migration) |
| Active | Yes — during migration window only |
| Scheduling | Every 30 minutes during migration |
| Max cycles per run | 20 |
| Timeout | 60 seconds |
| Deactivate after | All Asana tasks confirmed in Notion Items DB |

---

## Migration Checklist
- [ ] Run scenario once manually to verify payload format
- [ ] Confirm items appear in Notion Items DB after first run
- [ ] Run daily for one week to catch all active tasks
- [ ] Export Asana task list and cross-check against Notion Items DB
- [ ] Deactivate scenario
- [ ] Archive Asana project (client decision)
