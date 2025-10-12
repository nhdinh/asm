from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import Profile, ProfileRole
from audit_logger import audit_logger
from datetime import datetime
import os
import glob

audit_logs_bp = Blueprint("audit_logs", __name__)


@audit_logs_bp.route("", methods=["GET"])
@jwt_required()
def get_audit_logs():
    """Get audit logs from Redis (recent logs)"""
    current_profile_id = get_jwt_identity()
    current_profile = Profile.query.get(current_profile_id)

    # Only admin can view audit logs
    if current_profile.role != ProfileRole.ADMIN:
        return jsonify({"message": "Unauthorized"}), 403

    # Get query parameters
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")
    user_id = request.args.get("user_id", type=int)
    action = request.args.get("action")
    entity_type = request.args.get("entity_type")
    limit = request.args.get("limit", default=100, type=int)
    offset = request.args.get("offset", default=0, type=int)

    # Parse dates
    start_date = None
    end_date = None

    if start_date_str:
        try:
            start_date = datetime.fromisoformat(start_date_str)
        except:
            pass

    if end_date_str:
        try:
            end_date = datetime.fromisoformat(end_date_str)
        except:
            pass

    # Get logs from Redis
    logs = audit_logger.get_logs(
        start_date=start_date,
        end_date=end_date,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        limit=limit,
        offset=offset,
    )

    # Get count
    total_count = audit_logger.get_count()

    return jsonify(
        {
            "logs": logs,
            "total_count": total_count,
            "showing": len(logs),
            "limit": limit,
            "offset": offset,
        }
    )


@audit_logs_bp.route("/archived", methods=["GET"])
@jwt_required()
def get_archived_logs():
    """Get list of archived log files"""
    current_profile_id = get_jwt_identity()
    current_profile = Profile.query.get(current_profile_id)

    # Only admin can view audit logs
    if current_profile.role != ProfileRole.ADMIN:
        return jsonify({"message": "Unauthorized"}), 403

    archive_dir = "/app/logs/audit"

    if not os.path.exists(archive_dir):
        return jsonify({"files": []})

    # Get all archive files
    archive_files = glob.glob(os.path.join(archive_dir, "audit_logs_*.jsonl"))

    files_info = []
    for filepath in sorted(archive_files, reverse=True):
        filename = os.path.basename(filepath)
        file_size = os.path.getsize(filepath)
        file_mtime = os.path.getmtime(filepath)

        files_info.append(
            {
                "filename": filename,
                "filepath": filepath,
                "size": file_size,
                "modified_date": datetime.fromtimestamp(file_mtime).isoformat(),
            }
        )

    return jsonify({"files": files_info})


@audit_logs_bp.route("/archived/<filename>", methods=["GET"])
@jwt_required()
def get_archived_log_content(filename):
    """Read content from an archived log file"""
    current_profile_id = get_jwt_identity()
    current_profile = Profile.query.get(current_profile_id)

    # Only admin can view audit logs
    if current_profile.role != ProfileRole.ADMIN:
        return jsonify({"message": "Unauthorized"}), 403

    archive_dir = "/app/logs/audit"
    filepath = os.path.join(archive_dir, filename)

    # Security check - prevent path traversal
    if not filepath.startswith(archive_dir):
        return jsonify({"message": "Invalid filename"}), 400

    if not os.path.exists(filepath):
        return jsonify({"message": "File not found"}), 404

    # Get filters from query params
    filters = {}
    if request.args.get("user_id"):
        filters["user_id"] = int(request.args.get("user_id"))
    if request.args.get("action"):
        filters["action"] = request.args.get("action")
    if request.args.get("entity_type"):
        filters["entity_type"] = request.args.get("entity_type")

    limit = request.args.get("limit", default=100, type=int)

    # Read logs from file
    logs = audit_logger.read_archived_logs(filepath, filters, limit)

    return jsonify({"filename": filename, "logs": logs, "showing": len(logs)})


@audit_logs_bp.route("/archive", methods=["POST"])
@jwt_required()
def trigger_archive():
    """Manually trigger archival of old logs"""
    current_profile_id = get_jwt_identity()
    current_profile = Profile.query.get(current_profile_id)

    # Only admin can trigger archive
    if current_profile.role != ProfileRole.ADMIN:
        return jsonify({"message": "Unauthorized"}), 403

    days = request.json.get("days", 30)

    archived_count = audit_logger.archive_old_logs(days=days)

    return jsonify(
        {
            "message": f"Archived {archived_count} logs older than {days} days",
            "count": archived_count,
        }
    )


@audit_logs_bp.route("/stats", methods=["GET"])
@jwt_required()
def get_audit_stats():
    """Get statistics about audit logs"""
    current_profile_id = get_jwt_identity()
    current_profile = Profile.query.get(current_profile_id)

    # Only admin can view audit logs
    if current_profile.role != ProfileRole.ADMIN:
        return jsonify({"message": "Unauthorized"}), 403

    # Get count from Redis
    redis_count = audit_logger.get_count()

    # Get archived files info
    archive_dir = "/app/logs/audit"
    archived_files = 0
    archived_size = 0

    if os.path.exists(archive_dir):
        files = glob.glob(os.path.join(archive_dir, "audit_logs_*.jsonl"))
        archived_files = len(files)
        archived_size = sum(os.path.getsize(f) for f in files)

    return jsonify(
        {
            "redis_logs": redis_count,
            "archived_files": archived_files,
            "archived_size_bytes": archived_size,
            "archived_size_mb": round(archived_size / (1024 * 1024), 2),
        }
    )
