#!/usr/bin/env python3
"""
Script to seed data and generate audit logs for testing
This will create users, departments, and assets via API calls
"""

import requests
import json
import time

# Configuration
API_BASE_URL = "http://localhost:5000/api"

# Admin credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

def login(username, password):
    """Login and get access token"""
    response = requests.post(
        f"{API_BASE_URL}/auth/login",
        json={"username": username, "password": password}
    )
    if response.status_code == 200:
        data = response.json()
        return data["access_token"]
    else:
        print(f"Login failed: {response.text}")
        return None

def get_headers(token):
    """Get authorization headers"""
    return {"Authorization": f"Bearer {token}"}

def create_users(token):
    """Create test users"""
    headers = get_headers(token)

    users = [
        {
            "username": "nguyen_van_a",
            "fullname": "Nguyễn Văn A",
            "email": "nguyen.van.a@company.com",
            "password": "password123",
            "role": "manager",
            "department_ids": []
        },
        {
            "username": "tran_thi_b",
            "fullname": "Trần Thị B",
            "email": "tran.thi.b@company.com",
            "password": "password123",
            "role": "manager",
            "department_ids": []
        },
        {
            "username": "le_van_c",
            "fullname": "Lê Văn C",
            "email": "le.van.c@company.com",
            "password": "password123",
            "role": "viewer",
            "department_ids": []
        },
        {
            "username": "pham_thi_d",
            "fullname": "Phạm Thị D",
            "email": "pham.thi.d@company.com",
            "password": "password123",
            "role": "viewer",
            "department_ids": []
        }
    ]

    created_users = []
    for user_data in users:
        print(f"Creating user: {user_data['fullname']} ({user_data['username']})")
        response = requests.post(
            f"{API_BASE_URL}/auth/register",
            headers=headers,
            json=user_data
        )
        if response.status_code == 201:
            user = response.json()
            created_users.append(user)
            print(f"  ✓ Created user ID: {user['id']}")
        else:
            print(f"  ✗ Failed: {response.text}")
        time.sleep(0.5)

    return created_users

def create_departments(token):
    """Create test departments"""
    headers = get_headers(token)

    departments = [
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
        },
        {
            "name": "Phòng Công Nghệ",
            "description": "Phát triển và bảo trì hệ thống công nghệ"
        }
    ]

    created_depts = []
    for dept_data in departments:
        print(f"Creating department: {dept_data['name']}")
        response = requests.post(
            f"{API_BASE_URL}/departments",
            headers=headers,
            json=dept_data
        )
        if response.status_code == 201:
            dept = response.json()
            created_depts.append(dept)
            print(f"  ✓ Created department ID: {dept['id']}")
        else:
            print(f"  ✗ Failed: {response.text}")
        time.sleep(0.5)

    return created_depts

def create_assets(token, departments):
    """Create test assets"""
    headers = get_headers(token)

    if not departments:
        print("No departments available, skipping asset creation")
        return []

    assets = [
        {
            "code": "LT-2025-001",
            "name": "Laptop Dell XPS 15",
            "category": "Laptop",
            "description": "Laptop cao cấp cho nhân viên",
            "purchase_date": "2025-01-15",
            "purchase_price": 35000000,
            "status": "active",
            "department_id": departments[0]['id']
        },
        {
            "code": "LT-2025-002",
            "name": "Laptop HP ProBook 450",
            "category": "Laptop",
            "description": "Laptop văn phòng",
            "purchase_date": "2025-02-01",
            "purchase_price": 22000000,
            "status": "active",
            "department_id": departments[1]['id']
        },
        {
            "code": "PC-2025-001",
            "name": "Máy tính để bàn HP EliteDesk",
            "category": "PC",
            "description": "Máy tính để bàn cho kế toán",
            "purchase_date": "2025-01-20",
            "purchase_price": 18000000,
            "status": "active",
            "department_id": departments[1]['id']
        },
        {
            "code": "MH-2025-001",
            "name": "Màn hình Dell UltraSharp 27\"",
            "category": "Monitor",
            "description": "Màn hình 4K chuyên dụng",
            "purchase_date": "2025-02-10",
            "purchase_price": 12000000,
            "status": "active",
            "department_id": departments[2]['id']
        },
        {
            "code": "PR-2025-001",
            "name": "Máy in HP LaserJet Pro",
            "category": "Printer",
            "description": "Máy in laser văn phòng",
            "purchase_date": "2025-01-25",
            "purchase_price": 8000000,
            "status": "active",
            "department_id": departments[0]['id']
        },
        {
            "code": "TB-2025-001",
            "name": "Bàn làm việc điều chỉnh độ cao",
            "category": "Furniture",
            "description": "Bàn làm việc thông minh",
            "purchase_date": "2025-02-05",
            "purchase_price": 6500000,
            "status": "active",
            "department_id": departments[3]['id']
        }
    ]

    created_assets = []
    for asset_data in assets:
        print(f"Creating asset: {asset_data['name']} ({asset_data['code']})")
        response = requests.post(
            f"{API_BASE_URL}/assets",
            headers=headers,
            json=asset_data
        )
        if response.status_code == 201:
            asset = response.json()
            created_assets.append(asset)
            print(f"  ✓ Created asset ID: {asset['id']}")
        else:
            print(f"  ✗ Failed: {response.text}")
        time.sleep(0.5)

    return created_assets

def update_some_data(token, users, departments, assets):
    """Perform some updates to generate more audit logs"""
    headers = get_headers(token)

    print("\n--- Performing updates to generate audit logs ---\n")

    # Update a user
    if users:
        user_id = users[0]['id']
        print(f"Updating user ID {user_id}")
        response = requests.put(
            f"{API_BASE_URL}/users/{user_id}",
            headers=headers,
            json={
                "fullname": "Nguyễn Văn A (Updated)",
                "email": users[0]['email'],
                "role": "manager",
                "department_ids": [departments[0]['id']] if departments else []
            }
        )
        if response.status_code == 200:
            print(f"  ✓ Updated user")
        else:
            print(f"  ✗ Failed: {response.text}")
        time.sleep(0.5)

    # Update a department
    if departments:
        dept_id = departments[0]['id']
        print(f"Updating department ID {dept_id}")
        response = requests.put(
            f"{API_BASE_URL}/departments/{dept_id}",
            headers=headers,
            json={
                "name": "Phòng Nhân Sự & Tổng Hợp",
                "description": "Quản lý nguồn nhân lực, tuyển dụng và công việc tổng hợp",
                "user_ids": [users[0]['id'], users[2]['id']] if users else []
            }
        )
        if response.status_code == 200:
            print(f"  ✓ Updated department")
        else:
            print(f"  ✗ Failed: {response.text}")
        time.sleep(0.5)

    # Update an asset
    if assets:
        asset_id = assets[0]['id']
        print(f"Updating asset ID {asset_id}")
        response = requests.put(
            f"{API_BASE_URL}/assets/{asset_id}",
            headers=headers,
            json={
                "code": assets[0]['code'],
                "name": "Laptop Dell XPS 15 (Upgraded)",
                "category": "Laptop",
                "description": "Laptop cao cấp cho nhân viên - Đã nâng cấp RAM",
                "purchase_date": assets[0]['purchase_date'],
                "purchase_price": 35000000,
                "status": "active",
                "department_id": assets[0]['department_id']
            }
        )
        if response.status_code == 200:
            print(f"  ✓ Updated asset")
        else:
            print(f"  ✗ Failed: {response.text}")
        time.sleep(0.5)

    # Transfer an asset
    if len(assets) >= 2 and len(departments) >= 2:
        asset_id = assets[1]['id']
        from_dept = assets[1]['department_id']
        to_dept = departments[2]['id']
        print(f"Transferring asset ID {asset_id} from dept {from_dept} to dept {to_dept}")
        response = requests.post(
            f"{API_BASE_URL}/assets/{asset_id}/transfer",
            headers=headers,
            json={
                "from_department_id": from_dept,
                "to_department_id": to_dept,
                "reason": "Điều chuyển do nhu cầu công việc",
                "notes": "Asset được chuyển sang phòng Marketing"
            }
        )
        if response.status_code == 201:
            print(f"  ✓ Transferred asset")
        else:
            print(f"  ✗ Failed: {response.text}")
        time.sleep(0.5)

def main():
    print("=" * 60)
    print("SEED DATA AND GENERATE AUDIT LOGS")
    print("=" * 60)
    print()

    # Login as admin
    print("Logging in as admin...")
    token = login(ADMIN_USERNAME, ADMIN_PASSWORD)
    if not token:
        print("Failed to login. Exiting.")
        return
    print("✓ Logged in successfully\n")

    # Create users
    print("--- Creating Users ---\n")
    users = create_users(token)
    print(f"\nCreated {len(users)} users\n")

    # Create departments
    print("--- Creating Departments ---\n")
    departments = create_departments(token)
    print(f"\nCreated {len(departments)} departments\n")

    # Create assets
    print("--- Creating Assets ---\n")
    assets = create_assets(token, departments)
    print(f"\nCreated {len(assets)} assets\n")

    # Perform updates
    update_some_data(token, users, departments, assets)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Users created: {len(users)}")
    print(f"Departments created: {len(departments)}")
    print(f"Assets created: {len(assets)}")
    print("\nAudit logs have been generated for all operations.")
    print("You can now check the audit logs in the web interface at /audit-logs")
    print("=" * 60)

if __name__ == "__main__":
    main()
