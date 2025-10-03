#!/usr/bin/env python3
"""
Automated test scenario to generate audit logs
Runs inside the backend container using direct database access
"""

import sys
sys.path.insert(0, '/app/src')

from app import create_app
from models import db, User, Department, Asset, AssetTransfer, UserRole, AssetStatus
from audit_logger import audit_logger
from datetime import datetime, date
import time

# Create Flask app context
app = create_app()

def create_test_departments():
    """Create test departments"""
    print("=" * 60)
    print("CREATING DEPARTMENTS")
    print("=" * 60)

    departments_data = [
        {
            "name": "Phòng Nhân Sự",
            "description": "Quản lý nguồn nhân lực và tuyển dụng"
        },
        {
            "name": "Phòng Kế Toán",
            "description": "Quản lý tài chính và kế toán công ty"
        },
        {
            "name": "Phòng Marketing",
            "description": "Tiếp thị và phát triển thương hiệu"
        }
    ]

    dept_ids = []

    with app.app_context():
        # Get admin user for audit logs
        admin = User.query.filter_by(username='admin').first()

        for dept_data in departments_data:
            print(f"\nCreating: {dept_data['name']}")

            dept = Department(
                name=dept_data['name'],
                description=dept_data['description'],
                user_count=0,
                asset_count=0,
                total_value=0
            )

            db.session.add(dept)
            db.session.flush()

            # Create audit log
            audit_logger.log(
                user_id=admin.id,
                username=admin.username,
                action='create',
                entity_type='department',
                entity_id=dept.id,
                new_values=dept.to_dict(),
                details=f"Created department {dept.name}",
                ip_address='127.0.0.1'
            )

            dept_ids.append(dept.id)
            print(f"  ✓ Created department ID: {dept.id}")

        db.session.commit()
        print(f"\n✓ Total: {len(dept_ids)} departments created")

    return dept_ids

def create_test_users(dept_ids):
    """Create test users"""
    print("\n" + "=" * 60)
    print("CREATING USERS")
    print("=" * 60)

    users_data = [
        {
            "username": "nguyen_van_a",
            "fullname": "Nguyễn Văn A",
            "email": "nguyen.van.a@company.com",
            "password": "password123",
            "role": UserRole.MANAGER,
            "department_id": dept_ids[0] if dept_ids else None
        },
        {
            "username": "tran_thi_b",
            "fullname": "Trần Thị B",
            "email": "tran.thi.b@company.com",
            "password": "password123",
            "role": UserRole.MANAGER,
            "department_id": dept_ids[1] if len(dept_ids) > 1 else None
        },
        {
            "username": "le_van_c",
            "fullname": "Lê Văn C",
            "email": "le.van.c@company.com",
            "password": "password123",
            "role": UserRole.VIEWER,
            "department_id": dept_ids[2] if len(dept_ids) > 2 else None
        }
    ]

    user_ids = []

    with app.app_context():
        admin = User.query.filter_by(username='admin').first()

        for user_data in users_data:
            print(f"\nCreating: {user_data['fullname']} ({user_data['username']})")

            # Check if user exists
            existing = User.query.filter_by(username=user_data['username']).first()
            if existing:
                print(f"  ⚠ User already exists, skipping")
                user_ids.append(existing.id)
                continue

            user = User(
                username=user_data['username'],
                fullname=user_data['fullname'],
                email=user_data['email'],
                role=user_data['role']
            )
            user.set_password(user_data['password'])

            # Add to department
            if user_data['department_id']:
                dept = Department.query.get(user_data['department_id'])
                if dept:
                    user.departments.append(dept)

            db.session.add(user)
            db.session.flush()

            # Create audit log
            audit_logger.log(
                user_id=admin.id,
                username=admin.username,
                action='create',
                entity_type='user',
                entity_id=user.id,
                new_values=user.to_dict(),
                details=f"Created user {user.username}",
                ip_address='127.0.0.1'
            )

            user_ids.append(user.id)
            print(f"  ✓ Created user ID: {user.id}")

        db.session.commit()
        print(f"\n✓ Total: {len(user_ids)} users created")

    return user_ids

def create_test_assets(departments):
    """Create test assets"""
    print("\n" + "=" * 60)
    print("CREATING ASSETS")
    print("=" * 60)

    assets_data = [
        {
            "code": "LT-2025-001",
            "name": "Laptop Dell XPS 15",
            "category": "Laptop",
            "description": "Laptop cao cấp cho nhân viên",
            "purchase_date": date(2025, 1, 15),
            "purchase_price": 35000000,
            "status": AssetStatus.ACTIVE,
            "department_id": departments[0].id if departments else None
        },
        {
            "code": "PR-2025-001",
            "name": "Máy in HP LaserJet Pro",
            "category": "Printer",
            "description": "Máy in laser văn phòng",
            "purchase_date": date(2025, 1, 20),
            "purchase_price": 8000000,
            "status": AssetStatus.ACTIVE,
            "department_id": departments[1].id if departments else None
        },
        {
            "code": "MH-2025-001",
            "name": "Màn hình Dell UltraSharp 27\"",
            "category": "Monitor",
            "description": "Màn hình 4K chuyên dụng",
            "purchase_date": date(2025, 1, 25),
            "purchase_price": 12000000,
            "status": AssetStatus.ACTIVE,
            "department_id": departments[2].id if departments else None
        }
    ]

    created_assets = []

    with app.app_context():
        admin = User.query.filter_by(username='admin').first()

        for asset_data in assets_data:
            print(f"\nCreating: {asset_data['name']} ({asset_data['code']})")

            # Check if asset exists
            existing = Asset.query.filter_by(code=asset_data['code']).first()
            if existing:
                print(f"  ⚠ Asset already exists, skipping")
                created_assets.append(existing)
                continue

            asset = Asset(
                code=asset_data['code'],
                name=asset_data['name'],
                category=asset_data['category'],
                description=asset_data['description'],
                purchase_date=asset_data['purchase_date'],
                purchase_price=asset_data['purchase_price'],
                status=asset_data['status'],
                department_id=asset_data['department_id']
            )

            db.session.add(asset)
            db.session.flush()

            # Create audit log
            audit_logger.log(
                user_id=admin.id,
                username=admin.username,
                action='create',
                entity_type='asset',
                entity_id=asset.id,
                new_values=asset.to_dict(),
                details=f"Created asset {asset.code}",
                ip_address='127.0.0.1'
            )

            created_assets.append(asset)
            print(f"  ✓ Created asset ID: {asset.id}")

        db.session.commit()
        print(f"\n✓ Total: {len(created_assets)} assets created")

    return created_assets

def update_test_data(users, departments, assets):
    """Update some data to generate update audit logs"""
    print("\n" + "=" * 60)
    print("UPDATING DATA (Generate Update Logs)")
    print("=" * 60)

    with app.app_context():
        admin = User.query.filter_by(username='admin').first()

        # Update user
        if users:
            user = User.query.get(users[0].id)
            if user:
                print(f"\nUpdating user: {user.username}")
                old_values = user.to_dict()

                user.fullname = "Nguyễn Văn A (Updated)"

                db.session.flush()

                audit_logger.log(
                    user_id=admin.id,
                    username=admin.username,
                    action='update',
                    entity_type='user',
                    entity_id=user.id,
                    old_values=old_values,
                    new_values=user.to_dict(),
                    details=f"Updated user {user.username}",
                    ip_address='127.0.0.1'
                )
                print(f"  ✓ Updated user ID: {user.id}")

        # Update department
        if departments:
            dept = Department.query.get(departments[0].id)
            if dept:
                print(f"\nUpdating department: {dept.name}")
                old_values = dept.to_dict()

                dept.name = "Phòng Nhân Sự & Tổng Hợp"
                dept.description = "Quản lý nguồn nhân lực, tuyển dụng và công việc tổng hợp"

                db.session.flush()

                audit_logger.log(
                    user_id=admin.id,
                    username=admin.username,
                    action='update',
                    entity_type='department',
                    entity_id=dept.id,
                    old_values=old_values,
                    new_values=dept.to_dict(),
                    details=f"Updated department {dept.name}",
                    ip_address='127.0.0.1'
                )
                print(f"  ✓ Updated department ID: {dept.id}")

        # Update asset
        if assets:
            asset = Asset.query.get(assets[0].id)
            if asset:
                print(f"\nUpdating asset: {asset.code}")
                old_values = asset.to_dict()

                asset.name = "Laptop Dell XPS 15 (Upgraded)"
                asset.description = "Laptop cao cấp cho nhân viên - Đã nâng cấp RAM"

                db.session.flush()

                audit_logger.log(
                    user_id=admin.id,
                    username=admin.username,
                    action='update',
                    entity_type='asset',
                    entity_id=asset.id,
                    old_values=old_values,
                    new_values=asset.to_dict(),
                    details=f"Updated asset {asset.code}",
                    ip_address='127.0.0.1'
                )
                print(f"  ✓ Updated asset ID: {asset.id}")

        db.session.commit()
        print("\n✓ Updates completed")

def transfer_asset(assets, departments):
    """Transfer an asset to generate transfer audit log"""
    print("\n" + "=" * 60)
    print("TRANSFERRING ASSET")
    print("=" * 60)

    if len(assets) < 2 or len(departments) < 3:
        print("⚠ Not enough data for transfer")
        return

    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        asset = Asset.query.get(assets[1].id)

        if not asset:
            print("⚠ Asset not found")
            return

        from_dept_id = asset.department_id
        to_dept_id = departments[2].id

        print(f"\nTransferring asset: {asset.code}")
        print(f"  From: Department {from_dept_id}")
        print(f"  To: Department {to_dept_id}")

        # Create transfer record
        transfer = AssetTransfer(
            asset_id=asset.id,
            from_department_id=from_dept_id,
            to_department_id=to_dept_id,
            transferred_by=admin.id,
            reason="Điều chuyển do nhu cầu công việc",
            notes="Phòng Marketing cần máy in để in tài liệu quảng cáo"
        )

        # Update asset department
        asset.department_id = to_dept_id

        db.session.add(transfer)
        db.session.flush()

        # Create audit log
        audit_logger.log(
            user_id=admin.id,
            username=admin.username,
            action='transfer',
            entity_type='asset',
            entity_id=asset.id,
            old_values={'department_id': from_dept_id},
            new_values={'department_id': to_dept_id, 'transfer_id': transfer.id},
            details=f"Transferred asset {asset.code} from dept {from_dept_id} to {to_dept_id}",
            ip_address='127.0.0.1'
        )

        db.session.commit()
        print(f"  ✓ Transfer completed ID: {transfer.id}")

def main():
    print("\n" + "=" * 80)
    print(" " * 20 + "AUTOMATED TEST SCENARIO")
    print(" " * 15 + "Generate Audit Logs for Testing")
    print("=" * 80 + "\n")

    try:
        # Create departments
        departments = create_test_departments()
        time.sleep(1)

        # Create users
        users = create_test_users(departments)
        time.sleep(1)

        # Create assets
        assets = create_test_assets(departments)
        time.sleep(1)

        # Update data
        update_test_data(users, departments, assets)
        time.sleep(1)

        # Transfer asset
        transfer_asset(assets, departments)

        # Summary
        print("\n" + "=" * 80)
        print(" " * 30 + "SUMMARY")
        print("=" * 80)
        print(f"✓ Departments created: {len(departments)}")
        print(f"✓ Users created: {len(users)}")
        print(f"✓ Assets created: {len(assets)}")
        print(f"✓ Updates performed: 3 (user, department, asset)")
        print(f"✓ Transfers performed: 1")
        print(f"\n✓ Total audit logs generated: ~{3 + 3 + 3 + 3 + 1} = 13+ logs")
        print("\n" + "=" * 80)
        print("You can now check audit logs at: http://localhost:3000/audit-logs")
        print("Login as admin to view the logs")
        print("=" * 80 + "\n")

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
