# Team Management Specification

Team management allows multiple users to collaborate within shared workspaces. Teams group users with role-based access control and shared session visibility.

## Components

```
controller/
├── team.py              ← TeamManager class (CRUD + member management)
├── team_api.py          ← Flask blueprint (REST endpoints on :5900)
└── TEAM_SPEC.md         ← You are here
```

---

## Data Model

### Team Object

```python
{
    "team_id": "team_a1b2c3d4",
    "name": "Engineering",
    "description": "Engineering automation team",
    "owner_id": "user_001",
    "members": [
        {"user_id": "user_001", "role": "owner",  "joined_at": "2025-02-10T14:30:22+00:00"},
        {"user_id": "user_002", "role": "admin",  "joined_at": "2025-02-10T15:00:00+00:00"},
        {"user_id": "user_003", "role": "member", "joined_at": "2025-02-10T15:10:00+00:00"}
    ],
    "created_at": "2025-02-10T14:30:22+00:00",
    "updated_at": "2025-02-10T15:10:00+00:00",
    "settings": {
        "default_max_turns": 200,
        "auto_confirm": false,
        "shared_sessions": true
    }
}
```

### Roles

| Role | Permissions |
|------|-------------|
| `owner` | Full control. Create/delete team, manage all members, transfer ownership. One per team. |
| `admin` | Manage members (add/remove/update roles except owner). Update team settings. |
| `member` | View team, view shared sessions. Cannot manage members or settings. |

---

## Storage

JSON file-based persistence at `data/teams.json`. Thread-safe with `threading.Lock`. Atomic writes via temp file + `os.replace()`.

```
data/
└── teams.json           ← All teams stored here
```

---

## REST API Endpoints

All endpoints are on the Controller API server (port 5900).

### Team CRUD

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/teams` | Create team |
| `GET` | `/teams` | List teams (`?user_id=` to filter) |
| `GET` | `/teams/:id` | Get team by ID |
| `PUT` | `/teams/:id` | Update team |
| `DELETE` | `/teams/:id` | Delete team |

### Member Management

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/teams/:id/members` | List members |
| `POST` | `/teams/:id/members` | Add member |
| `PUT` | `/teams/:id/members/:user_id` | Update member role |
| `DELETE` | `/teams/:id/members/:user_id` | Remove member |
| `POST` | `/teams/:id/transfer-ownership` | Transfer ownership |

---

## API Examples

### Create Team

```bash
curl -X POST http://localhost:5900/teams \
  -H "Content-Type: application/json" \
  -d '{"name": "Engineering", "owner_id": "user_001", "description": "Automation team"}'
```

### List Teams for a User

```bash
curl http://localhost:5900/teams?user_id=user_001
```

### Add Member

```bash
curl -X POST http://localhost:5900/teams/team_abc123/members \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user_002", "role": "admin"}'
```

### Update Member Role

```bash
curl -X PUT http://localhost:5900/teams/team_abc123/members/user_002 \
  -H "Content-Type: application/json" \
  -d '{"role": "member"}'
```

### Remove Member

```bash
curl -X DELETE http://localhost:5900/teams/team_abc123/members/user_002
```

### Transfer Ownership

```bash
curl -X POST http://localhost:5900/teams/team_abc123/transfer-ownership \
  -H "Content-Type: application/json" \
  -d '{"current_owner_id": "user_001", "new_owner_id": "user_002"}'
```

---

## Integration with Controller

Register the team blueprint in `controller.py`:

```python
from team import TeamManager
from team_api import register_team_api

team_manager = TeamManager(data_dir="./data")
register_team_api(app, team_manager)
```

---

## Error Handling

All errors return JSON with an `error` field:

```json
{"error": "Team not found"}
```

| Status | When |
|--------|------|
| `400` | Validation error (missing fields, invalid role, duplicate member) |
| `404` | Team not found |
| `201` | Created (team or member) |
| `200` | Success (get, update, delete) |

---

## Constraints

- Team names must be non-empty
- One owner per team (enforced)
- Owner cannot be removed (must transfer ownership first)
- Owner role cannot be assigned via add_member (must use transfer-ownership)
- Duplicate members are rejected
- Valid roles: `owner`, `admin`, `member`
