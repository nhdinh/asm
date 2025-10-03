#!/usr/bin/env python3
"""
Simple automated seed script to generate audit logs
"""

import sys
sys.path.insert(0, '/app/src')

from app import create_app
from models import db, User, Department, Asset, AssetTransfer, UserRole, AssetStatus
from audit_logger import audit_logger
from datetime import date

app = create_app()

print("\n" + "="*80)
print(" "*25 + "GENERATING TEST DATA & AUDIT LOGS")
print("="*80 + "\n")

with app.app_context():
    admin = User.query.filter_by(username='admin').first()

    # 1. Create Departments
    print("Creating Departments...")
    dept1 = Department(name="Phòng Nhân Sự", description="Quản lý nguồn nhân lực và tuyển dụng", user_count=0, asset_count=0, total_value=0)
    dept2 = Department(name="Phòng Kế Toán", description="Quản lý tài chính và kế toán công ty", user_count=0, asset_count=0, total_value=0)
    dept3 = Department(name="Phòng Marketing", description="Tiếp thị và phát triển thương hiệu", user_count=0, asset_count=0, total_value=0)

    db.session.add_all([dept1, dept2, dept3])
    db.session.flush()

    audit_logger.log(admin.id, admin.username, 'create', 'department', dept1.id, new_values=dept1.to_dict(), details=f"Created department {dept1.name}", ip_address='127.0.0.1')
    audit_logger.log(admin.id, admin.username, 'create', 'department', dept2.id, new_values=dept2.to_dict(), details=f"Created department {dept2.name}", ip_address='127.0.0.1')
    audit_logger.log(admin.id, admin.username, 'create', 'department', dept3.id, new_values=dept3.to_dict(), details=f"Created department {dept3.name}", ip_address='127.0.0.1')

    db.session.commit()
    print(f"  ✓ Created 3 departments (IDs: {dept1.id}, {dept2.id}, {dept3.id})\n")

    # 2. Create Users
    print("Creating Users...")
    user1 = User(username="nguyen_van_a", fullname="Nguyễn Văn A", email="nguyen.van.a@company.com", role=UserRole.MANAGER)
    user1.set_password("password123")
    user1.departments.append(dept1)

    user2 = User(username="tran_thi_b", fullname="Trần Thị B", email="tran.thi.b@company.com", role=UserRole.MANAGER)
    user2.set_password("password123")
    user2.departments.append(dept2)

    user3 = User(username="le_van_c", fullname="Lê Văn C", email="le.van.c@company.com", role=UserRole.VIEWER)
    user3.set_password("password123")
    user3.departments.append(dept3)

    db.session.add_all([user1, user2, user3])
    db.session.flush()

    audit_logger.log(admin.id, admin.username, 'create', 'user', user1.id, new_values=user1.to_dict(), details=f"Created user {user1.username}", ip_address='127.0.0.1')
    audit_logger.log(admin.id, admin.username, 'create', 'user', user2.id, new_values=user2.to_dict(), details=f"Created user {user2.username}", ip_address='127.0.0.1')
    audit_logger.log(admin.id, admin.username, 'create', 'user', user3.id, new_values=user3.to_dict(), details=f"Created user {user3.username}", ip_address='127.0.0.1')

    db.session.commit()
    print(f"  ✓ Created 3 users (IDs: {user1.id}, {user2.id}, {user3.id})\n")

    # 3. Create Assets
    print("Creating Assets...")
    asset1 = Asset(code="LT-2025-001", name="Laptop Dell XPS 15", category="Laptop", description="Laptop cao cấp cho nhân viên", purchase_date=date(2025,1,15), purchase_price=35000000, status=AssetStatus.ACTIVE, department_id=dept1.id)
    asset2 = Asset(code="PR-2025-001", name="Máy in HP LaserJet Pro", category="Printer", description="Máy in laser văn phòng", purchase_date=date(2025,1,20), purchase_price=8000000, status=AssetStatus.ACTIVE, department_id=dept2.id)
    asset3 = Asset(code="MH-2025-001", name="Màn hình Dell UltraSharp 27\"", category="Monitor", description="Màn hình 4K chuyên dụng", purchase_date=date(2025,1,25), purchase_price=12000000, status=AssetStatus.ACTIVE, department_id=dept3.id)

    db.session.add_all([asset1, asset2, asset3])
    db.session.flush()

    audit_logger.log(admin.id, admin.username, 'create', 'asset', asset1.id, new_values=asset1.to_dict(), details=f"Created asset {asset1.code}", ip_address='127.0.0.1')
    audit_logger.log(admin.id, admin.username, 'create', 'asset', asset2.id, new_values=asset2.to_dict(), details=f"Created asset {asset2.code}", ip_address='127.0.0.1')
    audit_logger.log(admin.id, admin.username, 'create', 'asset', asset3.id, new_values=asset3.to_dict(), details=f"Created asset {asset3.code}", ip_address='127.0.0.1')

    db.session.commit()
    print(f"  ✓ Created 3 assets (IDs: {asset1.id}, {asset2.id}, {asset3.id})\n")

    # 4. Update User
    print("Updating Data (generate update logs)...")
    old_user = user1.to_dict()
    user1.fullname = "Nguyễn Văn A (Updated)"
    db.session.flush()
    audit_logger.log(admin.id, admin.username, 'update', 'user', user1.id, old_values=old_user, new_values=user1.to_dict(), details=f"Updated user {user1.username}", ip_address='127.0.0.1')
    print(f"  ✓ Updated user {user1.username}")

    # 5. Update Department
    old_dept = dept1.to_dict()
    dept1.name = "Phòng Nhân Sự & Tổng Hợp"
    dept1.description = "Quản lý nguồn nhân lực, tuyển dụng và công việc tổng hợp"
    db.session.flush()
    audit_logger.log(admin.id, admin.username, 'update', 'department', dept1.id, old_values=old_dept, new_values=dept1.to_dict(), details=f"Updated department {dept1.name}", ip_address='127.0.0.1')
    print(f"  ✓ Updated department {dept1.name}")

    # 6. Update Asset
    old_asset = asset1.to_dict()
    asset1.name = "Laptop Dell XPS 15 (Upgraded)"
    asset1.description = "Laptop cao cấp cho nhân viên - Đã nâng cấp RAM"
    db.session.flush()
    audit_logger.log(admin.id, admin.username, 'update', 'asset', asset1.id, old_values=old_asset, new_values=asset1.to_dict(), details=f"Updated asset {asset1.code}", ip_address='127.0.0.1')
    print(f"  ✓ Updated asset {asset1.code}\n")

    # 7. Transfer Asset
    print("Transferring Asset...")
    transfer = AssetTransfer(
        asset_id=asset2.id,
        from_department_id=dept2.id,
        to_department_id=dept3.id,
        transferred_by=admin.id,
        reason="Điều chuyển do nhu cầu công việc",
        notes="Phòng Marketing cần máy in"
    )
    asset2.department_id = dept3.id
    db.session.add(transfer)
    db.session.flush()
    audit_logger.log(admin.id, admin.username, 'transfer', 'asset', asset2.id, old_values={'department_id': dept2.id}, new_values={'department_id': dept3.id, 'transfer_id': transfer.id}, details=f"Transferred asset {asset2.code} from dept {dept2.id} to {dept3.id}", ip_address='127.0.0.1')
    print(f"  ✓ Transferred {asset2.code} from {dept2.name} to {dept3.name}\n")

    db.session.commit()

    print("="*80)
    print(" "*30 + "SUMMARY")
    print("="*80)
    print(f"✓ Departments: 3 created, 1 updated")
    print(f"✓ Users: 3 created, 1 updated")
    print(f"✓ Assets: 3 created, 1 updated, 1 transferred")
    print(f"✓ Total audit logs: ~13 entries")
    print("\n" + "="*80)
    print("View audit logs at: http://localhost:3000/audit-logs")
    print("Login as admin to access the audit logs page")
    print("="*80 + "\n")
