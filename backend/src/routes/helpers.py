from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt_identity

from models import Profile, ProfileRole


def require_admin_role(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        sess_username = get_jwt_identity()
        sess_profile = Profile.query.filter_by(username=sess_username).first()

        if sess_profile.role != ProfileRole.ADMIN:
            return jsonify({"message": "Unauthorized"}), 403

        kwargs["sess_profile"] = sess_profile

        return f(*args, **kwargs)

    return decorated_function


def require_manager_role(message: str):
    def decorator(func):
        def decorated_function(*args, **kwargs):
            sess_username = get_jwt_identity()
            sess_profile = Profile.query.filter_by(username=sess_username).first()

            # Regular users (non-managers) cannot create assets
            if sess_profile.role == ProfileRole.USER:
                # Check if user is a manager of any department
                is_manager = any(
                    assoc.is_manager for assoc in sess_profile.department_associations
                )
                if not is_manager:
                    return (
                        jsonify({"message": message}),
                        403,
                    )

            kwargs["sess_profile"] = sess_profile
            return func(*args, **kwargs)

        return decorated_function

    return decorator
