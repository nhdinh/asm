from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from enum import Enum
import bcrypt
from app import db


class UserType(str, Enum):
    """User authentication type"""

    LOCAL = "local"  # Local database authentication
    ACTIVE_DIRECTORY = "ad"  # Active Directory/LDAP authentication
    SSO = "sso"  # Single Sign-On (future support)


class User(db.Model):
    """User model - minimal subset for authentication"""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(
        db.String(255), nullable=True
    )  # Nullable for AD/SSO users
    email = db.Column(db.String(100), unique=True, nullable=False)
    fullname = db.Column(db.String(100))
    role = db.Column(db.String(20), nullable=False)

    # User type for authentication
    user_type = db.Column(
        db.Enum(
            UserType, native_enum=False, values_callable=lambda x: [e.value for e in x]
        ),
        default=UserType.LOCAL,
        nullable=False,
    )

    # Backward compatibility - deprecated, use user_type instead
    is_ad_user = db.Column(db.Boolean, default=False)

    deleted_at = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

    def check_password(self, password):
        """Verify password - only for local users"""
        if not self.password_hash:
            return False
        if self.user_type != UserType.LOCAL:
            return False  # Non-local users should authenticate via their auth provider
        return bcrypt.checkpw(
            password.encode("utf-8"), self.password_hash.encode("utf-8")
        )

    @property
    def is_local_user(self):
        """Check if user authenticates via local database"""
        return self.user_type == UserType.LOCAL

    @property
    def is_active_directory_user(self):
        """Check if user authenticates via Active Directory"""
        return self.user_type == UserType.ACTIVE_DIRECTORY

    @property
    def is_sso_user(self):
        """Check if user authenticates via SSO"""
        return self.user_type == UserType.SSO

    def requires_password(self):
        """Check if user type requires password hash"""
        return self.user_type == UserType.LOCAL

    def to_dict(self):
        """Convert user to dictionary"""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "fullname": self.fullname,
            "role": self.role,
            "user_type": (
                self.user_type.value
                if isinstance(self.user_type, UserType)
                else self.user_type
            ),
            "is_ad_user": self.is_ad_user,  # Backward compatibility
        }


class RefreshToken(db.Model):
    """Refresh token storage"""

    __tablename__ = "refresh_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    token_jti = db.Column(db.String(255), unique=True, nullable=False, index=True)
    access_token_jti = db.Column(db.String(255), nullable=False, index=True)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(512))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_revoked = db.Column(db.Boolean, default=False, nullable=False)
    revoked_at = db.Column(db.DateTime)

    user = db.relationship("User", backref=db.backref("refresh_tokens", lazy="dynamic"))


class LoginAttempt(db.Model):
    """Track failed login attempts"""

    __tablename__ = "login_attempts"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, index=True)
    ip_address = db.Column(db.String(45))
    success = db.Column(db.Boolean, default=False)
    attempt_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    failure_reason = db.Column(db.String(255))
