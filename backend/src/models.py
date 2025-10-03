from app import db
from datetime import datetime
from enum import Enum
import bcrypt


class UserRole(Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    VIEWER = "viewer"


class AssetStatus(Enum):
    ACTIVE = "active"
    DAMAGED = "damaged"
    DISPOSED = "disposed"


class ActivityStatus(Enum):
    FAILED = "failed"
    SUCCESS = "success"


# Association table for many-to-many relationship between User and Department
user_departments = db.Table('user_departments',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('department_id', db.Integer, db.ForeignKey('departments.id'), primary_key=True),
    db.Column('assigned_at', db.DateTime, default=datetime.utcnow)
)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    fullname = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(UserRole, name='userrole', values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Many-to-many relationship with Department
    departments = db.relationship(
        "Department",
        secondary=user_departments,
        backref=db.backref("users", lazy="dynamic")
    )
    activities = db.relationship("UserActivity", backref="user", lazy="dynamic")

    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

    def check_password(self, password):
        return bcrypt.checkpw(
            password.encode("utf-8"), self.password_hash.encode("utf-8")
        )

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "fullname": self.fullname,
            "email": self.email,
            "role": self.role.value,
            "departments": [{"id": dept.id, "name": dept.name} for dept in self.departments],
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

    assets = db.relationship("Asset", backref="department", lazy="dynamic")

    def to_dict(self, include_details=False):
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "asset_count": self.assets.count(),
            "user_count": self.users.count(),
            "total_value": self.total_value,
        }

        if include_details:
            # Include users list
            result["users"] = [
                {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role.value
                }
                for user in self.users.all()
            ]

        return result


class Asset(db.Model):
    __tablename__ = "assets"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))
    purchase_value = db.Column(db.Float)
    purchase_date = db.Column(db.Date)
    department_id = db.Column(
        db.Integer, db.ForeignKey("departments.id"), nullable=False
    )
    status = db.Column(db.Enum(AssetStatus), default=AssetStatus.ACTIVE)

    # New fields for asset assignment and condition
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    condition_notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    transfers = db.relationship("AssetTransfer", backref="asset", lazy="dynamic")
    assigned_to = db.relationship("User", foreign_keys=[assigned_to_id])

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "purchase_value": self.purchase_value,
            "purchase_date": (
                self.purchase_date.isoformat() if self.purchase_date else None
            ),
            "department_id": self.department_id,
            "department_name": self.department.name if self.department else None,
            "status": self.status.value,
            "assigned_to_id": self.assigned_to_id,
            "assigned_to_name": self.assigned_to.username if self.assigned_to else None,
            "condition_notes": self.condition_notes,
            "created_at": self.created_at.isoformat(),
        }


class AssetTransfer(db.Model):
    __tablename__ = "asset_transfers"

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("assets.id"), nullable=False)
    from_department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    to_department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("users.id"))  # User receiving the asset
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
            "assigned_to_username": self.assigned_to.username if self.assigned_to else None,
            "transferred_by": self.transferred_by_user.username if self.transferred_by_user else None,
            "transferred_by_fullname": self.transferred_by_user.fullname if self.transferred_by_user else None,
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
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
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
