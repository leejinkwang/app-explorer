"""
Team management REST API endpoints for App Explorer Controller.

Flask blueprint providing CRUD operations for teams and member management.
Mount on the API server (port 5900).
"""

from flask import Blueprint, request, jsonify

team_bp = Blueprint("teams", __name__)

# TeamManager instance — set by register_team_api()
_team_manager = None


def register_team_api(app, team_manager):
    """Register the team blueprint with a Flask app and inject the TeamManager."""
    global _team_manager
    _team_manager = team_manager
    app.register_blueprint(team_bp)


def _error(message, status=400):
    return jsonify({"error": message}), status


# ------------------------------------------------------------------
# Team CRUD
# ------------------------------------------------------------------


@team_bp.route("/teams", methods=["POST"])
def create_team():
    """Create a new team.

    Body: {"name": "...", "owner_id": "...", "description": "..."}
    """
    data = request.get_json(silent=True) or {}

    name = data.get("name")
    owner_id = data.get("owner_id")
    description = data.get("description", "")

    if not name:
        return _error("'name' is required")
    if not owner_id:
        return _error("'owner_id' is required")

    try:
        team = _team_manager.create_team(name, owner_id, description)
    except ValueError as e:
        return _error(str(e))

    return jsonify(team), 201


@team_bp.route("/teams", methods=["GET"])
def list_teams():
    """List all teams, optionally filtered by user_id query param."""
    user_id = request.args.get("user_id")
    teams = _team_manager.list_teams(user_id=user_id)
    return jsonify({"teams": teams, "count": len(teams)})


@team_bp.route("/teams/<team_id>", methods=["GET"])
def get_team(team_id):
    """Get a single team by ID."""
    team = _team_manager.get_team(team_id)
    if team is None:
        return _error("Team not found", 404)
    return jsonify(team)


@team_bp.route("/teams/<team_id>", methods=["PUT"])
def update_team(team_id):
    """Update team name, description, or settings.

    Body: {"name": "...", "description": "...", "settings": {...}}
    """
    data = request.get_json(silent=True) or {}

    try:
        team = _team_manager.update_team(
            team_id,
            name=data.get("name"),
            description=data.get("description"),
            settings=data.get("settings"),
        )
    except ValueError as e:
        return _error(str(e))

    if team is None:
        return _error("Team not found", 404)
    return jsonify(team)


@team_bp.route("/teams/<team_id>", methods=["DELETE"])
def delete_team(team_id):
    """Delete a team."""
    deleted = _team_manager.delete_team(team_id)
    if not deleted:
        return _error("Team not found", 404)
    return jsonify({"deleted": True})


# ------------------------------------------------------------------
# Member management
# ------------------------------------------------------------------


@team_bp.route("/teams/<team_id>/members", methods=["GET"])
def list_members(team_id):
    """List all members of a team."""
    team = _team_manager.get_team(team_id)
    if team is None:
        return _error("Team not found", 404)
    return jsonify({"members": team["members"], "count": len(team["members"])})


@team_bp.route("/teams/<team_id>/members", methods=["POST"])
def add_member(team_id):
    """Add a member to a team.

    Body: {"user_id": "...", "role": "member"}
    """
    data = request.get_json(silent=True) or {}

    user_id = data.get("user_id")
    role = data.get("role", "member")

    if not user_id:
        return _error("'user_id' is required")

    try:
        team = _team_manager.add_member(team_id, user_id, role)
    except ValueError as e:
        return _error(str(e))

    if team is None:
        return _error("Team not found", 404)
    return jsonify(team), 201


@team_bp.route("/teams/<team_id>/members/<user_id>", methods=["DELETE"])
def remove_member(team_id, user_id):
    """Remove a member from a team."""
    try:
        team = _team_manager.remove_member(team_id, user_id)
    except ValueError as e:
        return _error(str(e))

    if team is None:
        return _error("Team not found", 404)
    return jsonify(team)


@team_bp.route("/teams/<team_id>/members/<user_id>", methods=["PUT"])
def update_member_role(team_id, user_id):
    """Update a member's role.

    Body: {"role": "admin"}
    """
    data = request.get_json(silent=True) or {}
    role = data.get("role")

    if not role:
        return _error("'role' is required")

    try:
        team = _team_manager.update_member_role(team_id, user_id, role)
    except ValueError as e:
        return _error(str(e))

    if team is None:
        return _error("Team not found", 404)
    return jsonify(team)


@team_bp.route("/teams/<team_id>/transfer-ownership", methods=["POST"])
def transfer_ownership(team_id):
    """Transfer ownership to another member.

    Body: {"current_owner_id": "...", "new_owner_id": "..."}
    """
    data = request.get_json(silent=True) or {}

    current_owner_id = data.get("current_owner_id")
    new_owner_id = data.get("new_owner_id")

    if not current_owner_id or not new_owner_id:
        return _error("'current_owner_id' and 'new_owner_id' are required")

    try:
        team = _team_manager.transfer_ownership(team_id, current_owner_id, new_owner_id)
    except ValueError as e:
        return _error(str(e))

    if team is None:
        return _error("Team not found", 404)
    return jsonify(team)
