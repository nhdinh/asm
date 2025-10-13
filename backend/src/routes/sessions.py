from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import Profile, ProfileRole
from session_manager import session_manager
from datetime import datetime

sessions_bp = Blueprint("sessions", __name__)


@sessions_bp.route("", methods=["GET"])
@jwt_required()
def get_sessions():
    """Get all active sessions (admin only)"""
    current_profile_username = get_jwt_identity()
    current_profile = Profile.query.filter_by(username=current_profile_username).first()

    if current_profile.role != ProfileRole.ADMIN:
        return jsonify({"message": "Unauthorized - Admin access required"}), 403

    # Get query parameters
    include_inactive = request.args.get("include_inactive", "false").lower() == "true"
    user_id = request.args.get("user_id")

    # Get sessions from Redis
    if user_id:
        sessions = session_manager.get_user_sessions(int(user_id))
    else:
        sessions = session_manager.get_all_sessions(active_only=not include_inactive)

    # Enrich session data with user info
    enriched_sessions = []
    for session in sessions:
        user = Profile.query.get(session.get("user_id"))
        if user:
            session["username"] = user.username
            session["user_fullname"] = user.fullname
            session["user_email"] = user.email
        enriched_sessions.append(session)

    return (
        jsonify({"sessions": enriched_sessions, "total": len(enriched_sessions)}),
        200,
    )


@sessions_bp.route("/<token_jti>", methods=["DELETE"])
@jwt_required()
def terminate_session(token_jti):
    """Terminate a specific session (admin only)"""
    current_profile_username = get_jwt_identity()
    current_profile = Profile.query.filter_by(username=current_profile_username).first()

    if current_profile.role != ProfileRole.ADMIN:
        return jsonify({"message": "Unauthorized - Admin access required"}), 403

    # Get session info before terminating
    session = session_manager.get_session(token_jti)
    if not session:
        return jsonify({"message": "Session not found"}), 404

    # Terminate session in Redis
    if session_manager.terminate_session(token_jti):
        user = Profile.query.get(session.get("user_id"))
        username = user.username if user else "Unknown"
        return jsonify({"message": f"Session terminated for user {username}"}), 200
    else:
        return jsonify({"message": "Failed to terminate session"}), 500


@sessions_bp.route("/user/<int:user_id>", methods=["DELETE"])
@jwt_required()
def terminate_user_sessions(user_id):
    """Terminate all sessions for a specific user (admin only)"""
    current_profile_username = get_jwt_identity()
    current_profile = Profile.query.filter_by(username=current_profile_username).first()

    if current_profile.role != ProfileRole.ADMIN:
        return jsonify({"message": "Unauthorized - Admin access required"}), 403

    user = Profile.query.get_or_404(user_id)

    # Terminate all sessions in Redis
    terminated_count = session_manager.terminate_user_sessions(user_id)

    return (
        jsonify(
            {
                "message": f"Terminated {terminated_count} session(s) for user {user.username}",
                "terminated_count": terminated_count,
            }
        ),
        200,
    )


@sessions_bp.route("/stats", methods=["GET"])
@jwt_required()
def get_session_stats():
    """Get session statistics (admin only)"""
    current_profile_username = get_jwt_identity()
    current_profile = Profile.query.filter_by(username=current_profile_username).first()

    if current_profile.role != ProfileRole.ADMIN:
        return jsonify({"message": "Unauthorized - Admin access required"}), 403

    # Get statistics from Redis
    stats = session_manager.get_session_stats()

    return jsonify(stats), 200
