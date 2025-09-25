from config import BasicConfig
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity,
)
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from sqlalchemy import or_, and_
from sqlalchemy.sql import func
import os
import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__)
app.config.from_object(BasicConfig)
basedir = os.path.abspath(os.path.dirname(__file__))

# Configuration
app.config["JWT_SECRET_KEY"] = os.getenv(
    "JWT_SECRET_KEY", "your-secret-key-change-this-in-production"
)
app.config["JWT_VERIFY_SUB"] = False
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=8)

# Enable CORS for all origins
CORS(app)

# Setup logging
if not app.debug:
    if not os.path.exists("logs"):
        os.mkdir("logs")
    file_handler = RotatingFileHandler(
        "logs/backend.log", maxBytes=10240, backupCount=10
    )
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
        )
    )
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info("Asset Management API startup")

db = SQLAlchemy(app)
jwt = JWTManager(app)


# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # 'admin' or 'manager'
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    manager_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Asset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50), nullable=False)  # 'asset' or 'tool'
    value = db.Column(db.Float, nullable=False)
    purchase_date = db.Column(db.Date, nullable=False)
    current_department_id = db.Column(
        db.Integer, db.ForeignKey("department.id"), nullable=False
    )
    status = db.Column(
        db.String(50), default="active"
    )  # active, inactive, damaged, disposed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    current_department = db.relationship("Department", backref="assets")
    transfers = db.relationship("AssetTransfer", backref="asset", lazy="dynamic")


class AssetTransfer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"), nullable=False)
    from_department_id = db.Column(db.Integer, db.ForeignKey("department.id"))
    to_department_id = db.Column(
        db.Integer, db.ForeignKey("department.id"), nullable=False
    )
    transfer_date = db.Column(db.DateTime, default=datetime.utcnow)
    reason = db.Column(db.Text)
    transferred_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    notes = db.Column(db.Text)

    # Relationships
    from_department = db.relationship("Department", foreign_keys=[from_department_id])
    to_department = db.relationship("Department", foreign_keys=[to_department_id])
    user = db.relationship("User", backref="transfers")


# Health check endpoint
@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify(
        {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
        }
    )


# Auth Routes
@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    user = User.query.filter_by(username=username, is_active=True).first()

    if user and check_password_hash(user.password_hash, password):
        access_token = create_access_token(
            identity=user.id,
            additional_claims={
                "username": user.username,
                "role": user.role,
                "full_name": user.full_name,
            },
        )

        app.logger.info("User " + username + " logged in success")
        return jsonify(
            {
                "success": True,
                "access_token": access_token,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "full_name": user.full_name,
                    "role": user.role,
                },
            }
        )

    app.logger.debug("User " + username + " login failed")
    return jsonify({"success": False, "message": "Invalid credentials"}), 401


# User Routes
@app.route("/api/users", methods=["GET"])
@jwt_required()
def get_users():
    users = User.query.filter_by(is_active=True).all()
    return jsonify(
        [
            {
                "id": u.id,
                "username": u.username,
                "full_name": u.full_name,
                "role": u.role,
                "created_at": u.created_at.isoformat(),
            }
            for u in users
        ]
    )


@app.route("/api/users", methods=["POST"])
@jwt_required()
def create_user():
    data = request.get_json()

    # Check if user already exists
    if User.query.filter_by(username=data["username"]).first():
        return jsonify({"success": False, "message": "Username already exists"}), 400

    user = User(
        username=data["username"],
        password_hash=generate_password_hash(data["password"]),
        full_name=data["full_name"],
        role=data["role"],
    )

    db.session.add(user)
    db.session.commit()

    return jsonify({"success": True, "message": "User created successfully"})


@app.route("/api/departments", methods=["GET"])
@jwt_required()
def get_departments():
    try:
        departments = Department.query.all()
        result = []

        for dept in departments:
            # Count assets for this department
            asset_count = Asset.query.filter_by(current_department_id=dept.id).count()

            # Get manager info if exists
            manager_info = None
            if dept.manager_id:
                manager = User.query.get(dept.manager_id)
                if manager:
                    manager_info = {
                        "id": manager.id,
                        "full_name": manager.full_name,
                        "username": manager.username,
                    }

            result.append(
                {
                    "id": dept.id,
                    "name": dept.name,
                    "description": dept.description,
                    "manager_id": dept.manager_id,
                    "manager": manager_info,
                    "asset_count": asset_count,
                    "created_at": dept.created_at.isoformat(),
                }
            )

        return jsonify(result)
    except Exception as e:
        app.logger.error(f"Error getting departments: {str(e)}")
        return jsonify({"success": False, "message": "Server error"}), 500


@app.route("/api/departments", methods=["POST"])
@jwt_required()
def create_department():
    try:
        # Check if user is admin
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)

        if not current_user or current_user.role != "admin":
            return jsonify({"success": False, "message": "Unauthorized"}), 403

        data = request.get_json()

        # Validate required fields
        if not data or not data.get("name"):
            return (
                jsonify({"success": False, "message": "Department name is required"}),
                400,
            )

        # Check if department name already exists
        existing_dept = Department.query.filter_by(name=data["name"]).first()
        if existing_dept:
            return (
                jsonify(
                    {"success": False, "message": "Department name already exists"}
                ),
                400,
            )

        app.logger.info("existing dept ")

        # Validate manager_id if provided
        manager_id = data.get("manager_id")
        # if manager_id:
        #     manager = User.query.get(manager_id)
        #     if not manager:
        #         return jsonify({"success": False, "message": "Invalid manager ID"}), 400
        #     if manager.role not in ["admin", "manager"]:
        #         return (
        #             jsonify(
        #                 {
        #                     "success": False,
        #                     "message": "Selected user cannot be a manager",
        #                 }
        #             ),
        #             400,
        #         )

        # Create new department
        department = Department(
            name=data["name"].strip(),
            description=data.get("description", "").strip(),
            manager_id=manager_id if manager_id else None,
        )

        db.session.add(department)
        db.session.commit()

        app.logger.info(
            f"Department '{department.name}' created by user {current_user.username}"
        )

        return jsonify(
            {
                "success": True,
                "message": "Department created successfully",
                "department": {
                    "id": department.id,
                    "name": department.name,
                    "description": department.description,
                    "manager_id": department.manager_id,
                },
            }
        )

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error creating department: {str(e)}")
        return jsonify({"success": False, "message": "Server error"}), 500


@app.route("/api/departments/<int:dept_id>", methods=["PUT"])
@jwt_required()
def update_department(dept_id):
    try:
        # Check if user is admin
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)

        if not current_user or current_user.role != "admin":
            return jsonify({"success": False, "message": "Unauthorized"}), 403

        department = Department.query.get_or_404(dept_id)
        data = request.get_json()

        # Validate required fields
        if not data or not data.get("name"):
            return (
                jsonify({"success": False, "message": "Department name is required"}),
                400,
            )

        # Check if new name conflicts with existing department (excluding current)
        existing_dept = Department.query.filter(
            Department.name == data["name"], Department.id != dept_id
        ).first()

        if existing_dept:
            return (
                jsonify(
                    {"success": False, "message": "Department name already exists"}
                ),
                400,
            )

        # Validate manager_id if provided
        manager_id = data.get("manager_id")
        if manager_id:
            manager = User.query.get(manager_id)
            if not manager:
                return jsonify({"success": False, "message": "Invalid manager ID"}), 400
            if manager.role not in ["admin", "manager"]:
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "Selected user cannot be a manager",
                        }
                    ),
                    400,
                )

        # Update department
        old_name = department.name
        department.name = data["name"].strip()
        department.description = data.get("description", "").strip()
        department.manager_id = manager_id if manager_id else None

        db.session.commit()

        app.logger.info(
            f"Department '{old_name}' updated to '{department.name}' by user {current_user.username}"
        )

        return jsonify({"success": True, "message": "Department updated successfully"})

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error updating department: {str(e)}")
        return jsonify({"success": False, "message": "Server error"}), 500


@app.route("/api/departments/<int:dept_id>", methods=["DELETE"])
@jwt_required()
def delete_department(dept_id):
    try:
        # Check if user is admin
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)

        if not current_user or current_user.role != "admin":
            return jsonify({"success": False, "message": "Unauthorized"}), 403

        department = Department.query.get_or_404(dept_id)

        # Check if department has assets
        asset_count = Asset.query.filter_by(current_department_id=dept_id).count()
        if asset_count > 0:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": f"Cannot delete department with {asset_count} assets. Please transfer assets first.",
                    }
                ),
                400,
            )

        # Check if department has asset transfer history
        transfer_count = AssetTransfer.query.filter(
            or_(
                AssetTransfer.from_department_id == dept_id,
                AssetTransfer.to_department_id == dept_id,
            )
        ).count()

        if transfer_count > 0:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Cannot delete department with transfer history.",
                    }
                ),
                400,
            )

        dept_name = department.name
        db.session.delete(department)
        db.session.commit()

        app.logger.info(
            f"Department '{dept_name}' deleted by user {current_user.username}"
        )

        return jsonify({"success": True, "message": "Department deleted successfully"})

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting department: {str(e)}")
        return jsonify({"success": False, "message": "Server error"}), 500


@app.route("/api/departments/<int:dept_id>/report", methods=["GET"])
@jwt_required()
def get_department_report(dept_id):
    try:
        department = Department.query.get_or_404(dept_id)

        # Get all assets for this department
        assets = Asset.query.filter_by(current_department_id=dept_id).all()

        # Calculate statistics
        total_assets = len(assets)
        total_value = sum(asset.value for asset in assets)

        # Group by category
        assets_by_category = {"asset": 0, "tool": 0}
        for asset in assets:
            assets_by_category[asset.category] = (
                assets_by_category.get(asset.category, 0) + 1
            )

        # Group by status
        assets_by_status = {"active": 0, "inactive": 0, "damaged": 0, "disposed": 0}
        for asset in assets:
            assets_by_status[asset.status] = assets_by_status.get(asset.status, 0) + 1

        # Get recent transfers
        recent_transfers = (
            AssetTransfer.query.filter(
                or_(
                    AssetTransfer.from_department_id == dept_id,
                    AssetTransfer.to_department_id == dept_id,
                )
            )
            .order_by(AssetTransfer.transfer_date.desc())
            .limit(10)
            .all()
        )

        # Format transfer data
        transfers_data = []
        for transfer in recent_transfers:
            asset = Asset.query.get(transfer.asset_id)
            transfers_data.append(
                {
                    "asset_name": asset.name if asset else "N/A",
                    "asset_code": asset.code if asset else "N/A",
                    "from_department": (
                        transfer.from_department.name
                        if transfer.from_department
                        else "N/A"
                    ),
                    "to_department": transfer.to_department.name,
                    "transfer_date": transfer.transfer_date.isoformat(),
                    "reason": transfer.reason,
                }
            )

        # Get assets by purchase year
        assets_by_year = {}
        for asset in assets:
            year = asset.purchase_date.year
            assets_by_year[year] = assets_by_year.get(year, 0) + 1

        return jsonify(
            {
                "department": {
                    "id": department.id,
                    "name": department.name,
                    "description": department.description,
                },
                "statistics": {
                    "total_assets": total_assets,
                    "total_value": float(total_value),
                    "assets": assets_by_category.get("asset", 0),
                    "tools": assets_by_category.get("tool", 0),
                    "active": assets_by_status.get("active", 0),
                    "inactive": assets_by_status.get("inactive", 0),
                    "damaged": assets_by_status.get("damaged", 0),
                    "disposed": assets_by_status.get("disposed", 0),
                },
                "recent_transfers": transfers_data,
                "assets_by_year": assets_by_year,
            }
        )

    except Exception as e:
        app.logger.error(f"Error getting department report: {str(e)}")
        return jsonify({"success": False, "message": "Server error"}), 500


@app.route("/api/departments/<int:dept_id>/assets", methods=["GET"])
@jwt_required()
def get_department_assets(dept_id):
    try:
        department = Department.query.get_or_404(dept_id)

        # Get pagination parameters
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)

        # Get filter parameters
        search = request.args.get("search", "")
        category = request.args.get("category", "")
        status = request.args.get("status", "")

        # Build query
        query = Asset.query.filter_by(current_department_id=dept_id)

        if search:
            query = query.filter(
                or_(
                    Asset.code.contains(search),
                    Asset.name.contains(search),
                    Asset.description.contains(search),
                )
            )

        if category:
            query = query.filter_by(category=category)

        if status:
            query = query.filter_by(status=status)

        # Execute query with pagination
        assets_pagination = query.paginate(
            page=page, per_page=per_page, error_out=False
        )

        # Format response
        assets_data = []
        for asset in assets_pagination.items:
            assets_data.append(
                {
                    "id": asset.id,
                    "code": asset.code,
                    "name": asset.name,
                    "description": asset.description,
                    "category": asset.category,
                    "value": float(asset.value),
                    "purchase_date": asset.purchase_date.isoformat(),
                    "status": asset.status,
                    "created_at": asset.created_at.isoformat(),
                    "updated_at": asset.updated_at.isoformat(),
                }
            )

        return jsonify(
            {
                "department": {"id": department.id, "name": department.name},
                "assets": assets_data,
                "total": assets_pagination.total,
                "pages": assets_pagination.pages,
                "current_page": page,
                "per_page": per_page,
            }
        )

    except Exception as e:
        app.logger.error(f"Error getting department assets: {str(e)}")
        return jsonify({"success": False, "message": "Server error"}), 500


# Department Statistics API
@app.route("/api/departments/statistics", methods=["GET"])
@jwt_required()
def get_departments_statistics():
    try:
        # Get all departments with asset counts
        departments_stats = []
        departments = Department.query.all()

        total_departments = len(departments)
        total_assets = 0
        departments_with_managers = 0

        for dept in departments:
            asset_count = Asset.query.filter_by(current_department_id=dept.id).count()
            total_assets += asset_count

            if dept.manager_id:
                departments_with_managers += 1

            departments_stats.append(
                {
                    "id": dept.id,
                    "name": dept.name,
                    "asset_count": asset_count,
                    "has_manager": dept.manager_id is not None,
                }
            )

        # Calculate average assets per department
        avg_assets_per_dept = (
            total_assets / total_departments if total_departments > 0 else 0
        )

        return jsonify(
            {
                "total_departments": total_departments,
                "total_assets": total_assets,
                "departments_with_managers": departments_with_managers,
                "average_assets_per_department": round(avg_assets_per_dept, 1),
                "departments": departments_stats,
            }
        )

    except Exception as e:
        app.logger.error(f"Error getting departments statistics: {str(e)}")
        return jsonify({"success": False, "message": "Server error"}), 500


# Asset Routes
@app.route("/api/assets", methods=["GET"])
@jwt_required()
def get_assets():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    search = request.args.get("search", "")
    category = request.args.get("category", "")
    status = request.args.get("status", "")
    department_id = request.args.get("department_id", type=int)

    query = Asset.query

    # Apply filters
    if search:
        query = query.filter(
            or_(
                Asset.code.contains(search),
                Asset.name.contains(search),
                Asset.description.contains(search),
            )
        )

    if category:
        query = query.filter_by(category=category)

    if status:
        query = query.filter_by(status=status)

    if department_id:
        query = query.filter_by(current_department_id=department_id)

    assets = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify(
        {
            "assets": [
                {
                    "id": a.id,
                    "code": a.code,
                    "name": a.name,
                    "description": a.description,
                    "category": a.category,
                    "value": a.value,
                    "purchase_date": a.purchase_date.isoformat(),
                    "current_department": {
                        "id": a.current_department.id,
                        "name": a.current_department.name,
                    },
                    "status": a.status,
                    "created_at": a.created_at.isoformat(),
                    "updated_at": a.updated_at.isoformat(),
                }
                for a in assets.items
            ],
            "total": assets.total,
            "pages": assets.pages,
            "current_page": page,
        }
    )


@app.route("/api/assets", methods=["POST"])
@jwt_required()
def create_asset():
    data = request.get_json()

    # Check if asset code already exists
    if Asset.query.filter_by(code=data["code"]).first():
        return jsonify({"success": False, "message": "Asset code already exists"}), 400

    asset = Asset(
        code=data["code"],
        name=data["name"],
        description=data.get("description", ""),
        category=data["category"],
        value=data["value"],
        purchase_date=datetime.strptime(data["purchase_date"], "%Y-%m-%d").date(),
        current_department_id=data["current_department_id"],
        status=data.get("status", "active"),
    )

    db.session.add(asset)
    db.session.commit()

    return jsonify({"success": True, "message": "Asset created successfully"})


@app.route("/api/assets/<int:asset_id>", methods=["PUT"])
@jwt_required()
def update_asset(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    data = request.get_json()

    # Check if new code conflicts with existing asset
    if data["code"] != asset.code and Asset.query.filter_by(code=data["code"]).first():
        return jsonify({"success": False, "message": "Asset code already exists"}), 400

    asset.code = data["code"]
    asset.name = data["name"]
    asset.description = data.get("description", "")
    asset.category = data["category"]
    asset.value = data["value"]
    asset.purchase_date = datetime.strptime(data["purchase_date"], "%Y-%m-%d").date()
    asset.status = data.get("status", asset.status)

    db.session.commit()

    return jsonify({"success": True, "message": "Asset updated successfully"})


# Asset Transfer Routes
@app.route("/api/assets/<int:asset_id>/transfer", methods=["POST"])
@jwt_required()
def transfer_asset(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    data = request.get_json()
    user_id = get_jwt_identity()

    transfer = AssetTransfer(
        asset_id=asset_id,
        from_department_id=asset.current_department_id,
        to_department_id=data["to_department_id"],
        reason=data.get("reason", ""),
        transferred_by=user_id,
        notes=data.get("notes", ""),
    )

    # Update asset's current department
    asset.current_department_id = data["to_department_id"]

    db.session.add(transfer)
    db.session.commit()

    return jsonify({"success": True, "message": "Asset transferred successfully"})


@app.route("/api/assets/<int:asset_id>/transfers", methods=["GET"])
@jwt_required()
def get_asset_transfers(asset_id):
    transfers = (
        AssetTransfer.query.filter_by(asset_id=asset_id)
        .order_by(AssetTransfer.transfer_date.desc())
        .all()
    )

    return jsonify(
        [
            {
                "id": t.id,
                "from_department": (
                    {"id": t.from_department.id, "name": t.from_department.name}
                    if t.from_department
                    else None
                ),
                "to_department": {
                    "id": t.to_department.id,
                    "name": t.to_department.name,
                },
                "transfer_date": t.transfer_date.isoformat(),
                "reason": t.reason,
                "transferred_by": {"id": t.user.id, "full_name": t.user.full_name},
                "notes": t.notes,
            }
            for t in transfers
        ]
    )


# Reports Routes
@app.route("/api/reports/assets-by-purchase-date", methods=["GET"])
@jwt_required()
def assets_by_purchase_date():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    query = Asset.query
    if start_date:
        query = query.filter(
            Asset.purchase_date >= datetime.strptime(start_date, "%Y-%m-%d").date()
        )
    if end_date:
        query = query.filter(
            Asset.purchase_date <= datetime.strptime(end_date, "%Y-%m-%d").date()
        )

    assets = query.order_by(Asset.purchase_date.desc()).all()

    return jsonify(
        [
            {
                "code": a.code,
                "name": a.name,
                "category": a.category,
                "value": a.value,
                "purchase_date": a.purchase_date.isoformat(),
                "department": a.current_department.name,
                "status": a.status,
            }
            for a in assets
        ]
    )


@app.route("/api/reports/assets-by-department", methods=["GET"])
@jwt_required()
def assets_by_department():
    departments = Department.query.all()

    report = []
    for dept in departments:
        assets = Asset.query.filter_by(current_department_id=dept.id).all()
        report.append(
            {
                "department_name": dept.name,
                "total_assets": len(assets),
                "total_value": sum(a.value for a in assets),
                "by_category": {
                    "assets": len([a for a in assets if a.category == "asset"]),
                    "tools": len([a for a in assets if a.category == "tool"]),
                },
                "by_status": {
                    "active": len([a for a in assets if a.status == "active"]),
                    "inactive": len([a for a in assets if a.status == "inactive"]),
                    "damaged": len([a for a in assets if a.status == "damaged"]),
                    "disposed": len([a for a in assets if a.status == "disposed"]),
                },
            }
        )

    return jsonify(report)


@app.route("/api/reports/assets-by-status", methods=["GET"])
@jwt_required()
def assets_by_status():
    statuses = ["active", "inactive", "damaged", "disposed"]

    report = []
    for status in statuses:
        assets = Asset.query.filter_by(status=status).all()
        report.append(
            {
                "status": status,
                "count": len(assets),
                "total_value": sum(a.value for a in assets),
                "assets": [
                    {
                        "code": a.code,
                        "name": a.name,
                        "category": a.category,
                        "value": a.value,
                        "department": a.current_department.name,
                    }
                    for a in assets
                ],
            }
        )

    return jsonify(report)


# Initialize database
def create_tables():
    with app.app_context():
        db.create_all()

        # Create default admin user if not exists
        if not User.query.filter_by(username="admin").first():
            admin = User(
                username="admin",
                password_hash=generate_password_hash("admin123"),
                full_name="System Administrator",
                role="admin",
            )
            db.session.add(admin)

            # Create default departments
            it_dept = Department(
                name="IT Department", description="Information Technology"
            )
            hr_dept = Department(name="HR Department", description="Human Resources")
            finance_dept = Department(
                name="Finance Department", description="Finance and Accounting"
            )

            db.session.add_all([it_dept, hr_dept, finance_dept])

            try:
                db.session.commit()
                app.logger.info("Database initialized with default data")
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"Error initializing database: {str(e)}")


if __name__ == "__main__":
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    os.makedirs("logs", exist_ok=True)

    # Initialize database
    create_tables()

    # Run the application
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_ENV") == "development"

    app.run(debug=debug, host="0.0.0.0", port=port)
