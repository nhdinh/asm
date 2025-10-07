from app import db
from datetime import datetime
from enum import Enum, StrEnum
import bcrypt


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    USER = "USER"


class AssetStatus(Enum):
    ACTIVE = "active"
    DAMAGED = "damaged"
    DISPOSED = "disposed"


class ActivityStatus(Enum):
    FAILED = "failed"
    SUCCESS = "success"


# Association object for many-to-many relationship between User and Department
class UserDepartment(db.Model):
    __tablename__ = "user_departments"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    department_id = db.Column(
        db.Integer, db.ForeignKey("departments.id"), primary_key=True
    )
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_manager = db.Column(
        db.Boolean, default=False
    )  # Indicates if user manages this department

    # Relationships
    user = db.relationship("User", back_populates="department_associations")
    department = db.relationship("Department", back_populates="user_associations")


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    fullname = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(
        db.Enum(
            UserRole,
            name="userrole",
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    must_change_password = db.Column(db.Boolean, default=False)
    items_per_page = db.Column(
        db.Integer, default=None
    )  # None means use system default
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)

    # Association object relationship
    department_associations = db.relationship(
        "UserDepartment", back_populates="user", cascade="all, delete-orphan"
    )

    # Convenience property to get departments
    @property
    def departments(self):
        return [assoc.department for assoc in self.department_associations]

    activities = db.relationship("UserActivity", backref="user", lazy="dynamic")

    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

    def check_password(self, password):
        return bcrypt.checkpw(
            password.encode("utf-8"), self.password_hash.encode("utf-8")
        )

    @classmethod
    def query_all(cls, include_deleted=False):
        """Query users with option to include soft-deleted records"""
        if include_deleted:
            return cls.query
        else:
            return cls.query.filter(cls.deleted_at.is_(None))

    def to_dict(self):
        # Build departments with is_manager flag, excluding soft-deleted departments
        departments_with_manager = []
        for assoc in self.department_associations:
            # Skip soft-deleted departments
            if assoc.department.deleted_at is not None:
                continue
            departments_with_manager.append(
                {
                    "id": assoc.department.id,
                    "name": assoc.department.name,
                    "is_manager": assoc.is_manager,
                }
            )

        return {
            "id": self.id,
            "username": self.username,
            "fullname": self.fullname,
            "email": self.email,
            "role": self.role.value,
            "must_change_password": self.must_change_password,
            "items_per_page": self.items_per_page,
            "departments": departments_with_manager,
            "created_at": self.created_at.isoformat(),
        }


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    asset_count = db.Column(db.Integer)
    user_count = db.Column(db.Integer)
    total_value = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)

    assets = db.relationship("Asset", backref="department", lazy="dynamic")

    # Association object relationship
    user_associations = db.relationship(
        "UserDepartment", back_populates="department", cascade="all, delete-orphan"
    )

    # to get users
    def users(self, include_deleted=False):
        """Return all users in this department"""

        # Return a query-like object for backward compatibility
        class UserList:
            def __init__(self, users):
                if include_deleted:
                    self._users = [u for u in users]
                else:
                    self._users = [u for u in users if u.deleted_at is None]

            def all(self):
                return self._users

            def count(self):
                return len(self._users)

        return UserList([assoc.user for assoc in self.user_associations])

    def managers(self, include_deleted=False):
        """Return users who have is_manager=True for this department"""
        if include_deleted:
            return [assoc.user for assoc in self.user_associations if assoc.is_manager]
        else:
            return [
                assoc.user
                for assoc in self.user_associations
                if assoc.is_manager and assoc.user.deleted_at is None
            ]

    @classmethod
    def query_all(cls, include_deleted=False):
        """Query departments with option to include soft-deleted records"""
        if include_deleted:
            return cls.query
        else:
            return cls.query.filter(cls.deleted_at.is_(None))

    def to_dict(self, include_details=False, include_deleted=False):
        # Calculate total value from actual assets
        total_value = sum(asset.purchase_value or 0 for asset in self.assets.all())

        # Get managers list (users with MANAGER role in this department)
        managers_list = self.managers(include_deleted)

        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "manager_names": (
                ", ".join([m.fullname for m in managers_list])
                if managers_list
                else None
            ),
            "created_at": self.created_at.isoformat(),
            "asset_count": self.assets.count(),
            "user_count": self.users(include_deleted).count(),
            "total_value": total_value,
        }

        if include_deleted:
            result["managers"] = [
                {"id": m.id, "fullname": m.fullname, "username": m.username}
                for m in managers_list
            ]
        else:
            result["managers"] = (
                [
                    {"id": m.id, "fullname": m.fullname, "username": m.username}
                    for m in managers_list
                    if (not include_deleted and m.deleted_at is None)
                ],
            )

        if include_details:
            # Include users list
            result["users"] = [
                {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role.value,
                }
                for user in self.users(include_deleted).all()
            ]

        return result


class AssetCategory(db.Model):
    __tablename__ = "asset_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationship to assets
    assets = db.relationship("Asset", backref="category_obj", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "asset_count": self.assets.count(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Asset(db.Model):
    __tablename__ = "assets"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))  # Keep for backward compatibility
    category_id = db.Column(
        db.Integer, db.ForeignKey("asset_categories.id"), nullable=True
    )  # New foreign key
    purchase_value = db.Column(db.Float)
    purchase_date = db.Column(db.Date)
    department_id = db.Column(
        db.Integer, db.ForeignKey("departments.id"), nullable=False
    )
    status = db.Column(db.Enum(AssetStatus), default=AssetStatus.ACTIVE)

    # New fields for asset assignment and condition
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    condition_notes = db.Column(db.Text)
    propose_for_liquidation = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    deleted_at = db.Column(db.DateTime, nullable=True)

    transfers = db.relationship("AssetTransfer", backref="asset", lazy="dynamic")
    assigned_to = db.relationship("User", foreign_keys=[assigned_to_id])

    @classmethod
    def query_all(cls, include_deleted=False):
        """Query assets with option to include soft-deleted records"""
        if include_deleted:
            return cls.query
        else:
            return cls.query.filter(cls.deleted_at.is_(None))

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "category": self.category,  # Backward compatibility
            "category_id": self.category_id,
            "category_name": (
                self.category_obj.name if self.category_obj else self.category
            ),
            "purchase_value": self.purchase_value,
            "purchase_date": (
                self.purchase_date.isoformat() if self.purchase_date else None
            ),
            "department_id": self.department_id,
            "department_name": self.department.name if self.department else None,
            "status": self.status.value,
            "assigned_to_id": self.assigned_to_id,
            "assigned_to_name": self.assigned_to.fullname if self.assigned_to else None,
            "condition_notes": self.condition_notes,
            "propose_for_liquidation": self.propose_for_liquidation,
            "created_at": self.created_at.isoformat(),
        }


class AssetTransfer(db.Model):
    __tablename__ = "asset_transfers"

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("assets.id"), nullable=False)
    from_department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    to_department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    assigned_to_id = db.Column(
        db.Integer, db.ForeignKey("users.id")
    )  # User receiving the asset
    transferred_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    transfer_date = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)

    from_department = db.relationship("Department", foreign_keys=[from_department_id])
    to_department = db.relationship("Department", foreign_keys=[to_department_id])
    assigned_to = db.relationship("User", foreign_keys=[assigned_to_id])
    transferred_by_user = db.relationship("User", foreign_keys=[transferred_by])

    def to_dict(self):
        return {
            "id": self.id,
            "asset_id": self.asset_id,
            "from_department": (
                self.from_department.name if self.from_department else None
            ),
            "to_department": self.to_department.name if self.to_department else None,
            "assigned_to": self.assigned_to.fullname if self.assigned_to else None,
            "assigned_to_username": (
                self.assigned_to.username if self.assigned_to else None
            ),
            "transferred_by": (
                self.transferred_by_user.username if self.transferred_by_user else None
            ),
            "transferred_by_fullname": (
                self.transferred_by_user.fullname if self.transferred_by_user else None
            ),
            "transfer_date": self.transfer_date.isoformat(),
            "notes": self.notes,
        }


class UserActivity(db.Model):
    __tablename__ = "user_activities"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    username = db.Column(db.String(50), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50))
    entity_id = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.Text)
    status = db.Column(db.Enum(ActivityStatus), default=ActivityStatus.FAILED)
    failed_count = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.username,
            "action": self.action,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
            "status": self.status.value if self.status else None,
            "failed_count": self.failed_count,
        }


class SystemSetting(db.Model):
    """System configuration settings"""

    __tablename__ = "system_settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    data_type = db.Column(db.String(20), default="string")  # string, int, float, bool
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id"))

    def to_dict(self):
        return {
            "id": self.id,
            "key": self.key,
            "value": self.value,
            "description": self.description,
            "data_type": self.data_type,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "updated_by": self.updated_by,
        }

    def get_typed_value(self):
        """Return value converted to appropriate type"""
        if self.data_type == "int":
            return int(self.value)
        elif self.data_type == "float":
            return float(self.value)
        elif self.data_type == "bool":
            return self.value.lower() in ["true", "1", "yes"]
        return self.value


class EmailConfig(db.Model):
    """Email server configuration"""

    __tablename__ = "email_config"

    id = db.Column(db.Integer, primary_key=True)
    # Provider selection: smtp or sendgrid
    provider = db.Column(db.String(20), default="smtp", nullable=False)
    # SMTP settings (for provider=smtp)
    smtp_host = db.Column(db.String(255))
    smtp_port = db.Column(db.Integer, default=587)
    smtp_username = db.Column(db.String(255))
    smtp_password = db.Column(db.String(255))
    use_tls = db.Column(db.Boolean, default=True)
    use_ssl = db.Column(db.Boolean, default=False)
    # SendGrid settings (for provider=sendgrid)
    sendgrid_api_key = db.Column(db.String(255))
    # Common settings
    from_email = db.Column(db.String(255), nullable=False)
    from_name = db.Column(db.String(255), default="Asset Management System")
    enabled = db.Column(db.Boolean, default=False)
    send_welcome_email = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id"))

    def to_dict(self, include_secrets=False):
        result = {
            "id": self.id,
            "provider": self.provider,
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port,
            "smtp_username": self.smtp_username,
            "from_email": self.from_email,
            "from_name": self.from_name,
            "use_tls": self.use_tls,
            "use_ssl": self.use_ssl,
            "enabled": self.enabled,
            "send_welcome_email": self.send_welcome_email,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "updated_by": self.updated_by,
        }
        if include_secrets:
            result["smtp_password"] = self.smtp_password
            result["sendgrid_api_key"] = self.sendgrid_api_key
        else:
            result["has_smtp_password"] = bool(self.smtp_password)
            result["has_sendgrid_api_key"] = bool(self.sendgrid_api_key)
        return result
