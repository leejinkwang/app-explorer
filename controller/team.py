"""
Team management module for App Explorer Controller.

Handles team CRUD operations, member management, and role-based access.
Data is persisted to a JSON file on disk.
"""

import json
import os
import time
import uuid
import threading
from datetime import datetime, timezone


VALID_ROLES = ("owner", "admin", "member")


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _generate_id(prefix="team"):
    short = uuid.uuid4().hex[:8]
    return f"{prefix}_{short}"


class TeamManager:
    """Manages teams with JSON file-based persistence.

    Thread-safe: all mutations are protected by a lock.
    """

    def __init__(self, data_dir="./data"):
        self._data_dir = data_dir
        self._teams_file = os.path.join(data_dir, "teams.json")
        self._lock = threading.Lock()
        self._teams = {}  # team_id -> team dict
        os.makedirs(data_dir, exist_ok=True)
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self):
        if os.path.exists(self._teams_file):
            with open(self._teams_file, "r", encoding="utf-8") as f:
                self._teams = json.load(f)

    def _save(self):
        tmp = self._teams_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._teams, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self._teams_file)

    # ------------------------------------------------------------------
    # Team CRUD
    # ------------------------------------------------------------------

    def create_team(self, name, owner_id, description=""):
        """Create a new team. The creator becomes the owner.

        Returns the created team dict.
        """
        if not name or not name.strip():
            raise ValueError("Team name is required")
        if not owner_id or not owner_id.strip():
            raise ValueError("Owner ID is required")

        team_id = _generate_id("team")
        now = _now_iso()

        team = {
            "team_id": team_id,
            "name": name.strip(),
            "description": description.strip() if description else "",
            "owner_id": owner_id.strip(),
            "members": [
                {
                    "user_id": owner_id.strip(),
                    "role": "owner",
                    "joined_at": now,
                }
            ],
            "created_at": now,
            "updated_at": now,
            "settings": {
                "default_max_turns": 200,
                "auto_confirm": False,
                "shared_sessions": True,
            },
        }

        with self._lock:
            self._teams[team_id] = team
            self._save()

        return team

    def get_team(self, team_id):
        """Return a team by ID or None if not found."""
        with self._lock:
            team = self._teams.get(team_id)
        if team is None:
            return None
        return dict(team)

    def list_teams(self, user_id=None):
        """List all teams, optionally filtered by member user_id."""
        with self._lock:
            teams = list(self._teams.values())
        if user_id:
            teams = [
                t for t in teams
                if any(m["user_id"] == user_id for m in t["members"])
            ]
        return teams

    def update_team(self, team_id, name=None, description=None, settings=None):
        """Update team name, description, or settings.

        Returns the updated team or None if not found.
        """
        with self._lock:
            team = self._teams.get(team_id)
            if team is None:
                return None
            if name is not None:
                if not name.strip():
                    raise ValueError("Team name cannot be empty")
                team["name"] = name.strip()
            if description is not None:
                team["description"] = description.strip()
            if settings is not None:
                team["settings"].update(settings)
            team["updated_at"] = _now_iso()
            self._save()
            return dict(team)

    def delete_team(self, team_id):
        """Delete a team. Returns True if deleted, False if not found."""
        with self._lock:
            if team_id not in self._teams:
                return False
            del self._teams[team_id]
            self._save()
            return True

    # ------------------------------------------------------------------
    # Member management
    # ------------------------------------------------------------------

    def add_member(self, team_id, user_id, role="member"):
        """Add a member to a team.

        Returns the updated team or None if team not found.
        Raises ValueError for invalid role or duplicate member.
        """
        if role not in VALID_ROLES:
            raise ValueError(f"Invalid role: {role}. Must be one of {VALID_ROLES}")

        with self._lock:
            team = self._teams.get(team_id)
            if team is None:
                return None

            # Check for duplicate
            for m in team["members"]:
                if m["user_id"] == user_id:
                    raise ValueError(f"User {user_id} is already a member of this team")

            # Only one owner allowed
            if role == "owner":
                raise ValueError("Cannot add another owner. Use transfer_ownership instead.")

            team["members"].append({
                "user_id": user_id,
                "role": role,
                "joined_at": _now_iso(),
            })
            team["updated_at"] = _now_iso()
            self._save()
            return dict(team)

    def remove_member(self, team_id, user_id):
        """Remove a member from a team.

        Returns the updated team or None if team not found.
        Raises ValueError if trying to remove the owner.
        """
        with self._lock:
            team = self._teams.get(team_id)
            if team is None:
                return None

            member = next((m for m in team["members"] if m["user_id"] == user_id), None)
            if member is None:
                raise ValueError(f"User {user_id} is not a member of this team")
            if member["role"] == "owner":
                raise ValueError("Cannot remove the team owner. Transfer ownership first.")

            team["members"] = [m for m in team["members"] if m["user_id"] != user_id]
            team["updated_at"] = _now_iso()
            self._save()
            return dict(team)

    def update_member_role(self, team_id, user_id, new_role):
        """Update a member's role.

        Returns the updated team or None if team not found.
        """
        if new_role not in VALID_ROLES:
            raise ValueError(f"Invalid role: {new_role}. Must be one of {VALID_ROLES}")
        if new_role == "owner":
            raise ValueError("Use transfer_ownership to change the owner")

        with self._lock:
            team = self._teams.get(team_id)
            if team is None:
                return None

            member = next((m for m in team["members"] if m["user_id"] == user_id), None)
            if member is None:
                raise ValueError(f"User {user_id} is not a member of this team")
            if member["role"] == "owner":
                raise ValueError("Cannot change the owner's role. Transfer ownership first.")

            member["role"] = new_role
            team["updated_at"] = _now_iso()
            self._save()
            return dict(team)

    def transfer_ownership(self, team_id, current_owner_id, new_owner_id):
        """Transfer team ownership from current owner to another member.

        The current owner becomes an admin.
        Returns the updated team or None if team not found.
        """
        with self._lock:
            team = self._teams.get(team_id)
            if team is None:
                return None

            current = next((m for m in team["members"] if m["user_id"] == current_owner_id), None)
            if current is None or current["role"] != "owner":
                raise ValueError("Only the current owner can transfer ownership")

            new_owner = next((m for m in team["members"] if m["user_id"] == new_owner_id), None)
            if new_owner is None:
                raise ValueError(f"User {new_owner_id} is not a member of this team")

            current["role"] = "admin"
            new_owner["role"] = "owner"
            team["owner_id"] = new_owner_id
            team["updated_at"] = _now_iso()
            self._save()
            return dict(team)

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_member(self, team_id, user_id):
        """Get a specific member from a team, or None."""
        with self._lock:
            team = self._teams.get(team_id)
            if team is None:
                return None
            return next((m for m in team["members"] if m["user_id"] == user_id), None)

    def get_user_role(self, team_id, user_id):
        """Get user's role in a team, or None if not a member."""
        member = self.get_member(team_id, user_id)
        return member["role"] if member else None

    def is_member(self, team_id, user_id):
        """Check if user is a member of the team."""
        return self.get_member(team_id, user_id) is not None

    def get_teams_for_user(self, user_id):
        """Get all teams where user is a member."""
        return self.list_teams(user_id=user_id)
