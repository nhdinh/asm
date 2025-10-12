"""
Initialize sample data for Asset Management System
- Creates departments
- Creates users and assigns them to departments (except admin)
- Creates assets
- Assigns 80% of assets to users
- Leaves 20% of assets unassigned to users but still in departments
"""

from app import create_app
from models import (
    db,
    User,
    Department,
    Asset,
    AssetCategory,
    UserRole,
    AssetStatus,
    ProfileDepartment,
)
import random
from datetime import datetime

# Sample data
DEPARTMENTS = [
    {
        "name": "Phòng Kỹ Thuật",
        "description": "Phòng ban phụ trách kỹ thuật và công nghệ",
    },
    {"name": "Phòng Nhân Sự", "description": "Phòng ban quản lý nguồn nhân lực"},
    {"name": "Phòng Kế Toán", "description": "Phòng ban tài chính và kế toán"},
    {"name": "Phòng Kinh Doanh", "description": "Phòng ban kinh doanh và phát triển"},
    {"name": "Phòng Hành Chính", "description": "Phòng ban hành chính tổng hợp"},
]

USERS = [
    {
        "username": "nguyen.van.a",
        "fullname": "Nguyễn Văn A",
        "email": "nguyen.van.a@company.com",
        "role": UserRole.USER,
    },
    {
        "username": "tran.thi.b",
        "fullname": "Trần Thị B",
        "email": "tran.thi.b@company.com",
        "role": UserRole.USER,
    },
    {
        "username": "le.van.c",
        "fullname": "Lê Văn C",
        "email": "le.van.c@company.com",
        "role": UserRole.USER,
    },
    {
        "username": "pham.thi.d",
        "fullname": "Phạm Thị D",
        "email": "pham.thi.d@company.com",
        "role": UserRole.USER,
    },
    {
        "username": "hoang.van.e",
        "fullname": "Hoàng Văn E",
        "email": "hoang.van.e@company.com",
        "role": UserRole.USER,
    },
    {
        "username": "vo.thi.f",
        "fullname": "Võ Thị F",
        "email": "vo.thi.f@company.com",
        "role": UserRole.USER,
    },
    {
        "username": "do.van.g",
        "fullname": "Đỗ Văn G",
        "email": "do.van.g@company.com",
        "role": UserRole.USER,
    },
    {
        "username": "bui.thi.h",
        "fullname": "Bùi Thị H",
        "email": "bui.thi.h@company.com",
        "role": UserRole.USER,
    },
    {
        "username": "dang.van.i",
        "fullname": "Đặng Văn I",
        "email": "dang.van.i@company.com",
        "role": UserRole.USER,
    },
    {
        "username": "ngo.thi.k",
        "fullname": "Ngô Thị K",
        "email": "ngo.thi.k@company.com",
        "role": UserRole.USER,
    },
]

ASSET_CATEGORIES = [
    {"name": "Laptop", "description": "Máy tính xách tay"},
    {"name": "Màn hình", "description": "Màn hình máy tính"},
    {"name": "Bàn phím", "description": "Bàn phím máy tính"},
    {"name": "Chuột", "description": "Chuột máy tính"},
    {"name": "Máy in", "description": "Máy in, máy photocopy"},
    {"name": "Máy chiếu", "description": "Máy chiếu, projector"},
    {"name": "Điện thoại", "description": "Điện thoại di động"},
    {"name": "Bàn làm việc", "description": "Bàn làm việc văn phòng"},
    {"name": "Ghế văn phòng", "description": "Ghế làm việc"},
    {"name": "Tủ tài liệu", "description": "Tủ đựng hồ sơ, tài liệu"},
]

ASSET_TEMPLATES = {
    "Laptop": [
        "Dell Latitude 5420",
        "HP EliteBook 840",
        "Lenovo ThinkPad T14",
        "MacBook Pro 14",
        "ASUS ZenBook",
    ],
    "Màn hình": [
        'Dell P2422H 24"',
        'LG 27UK850 27"',
        'Samsung S24R350 24"',
        'BenQ GW2480 24"',
    ],
    "Bàn phím": [
        "Logitech K380",
        "Keychron K2",
        "Microsoft Ergonomic",
        "Logitech MX Keys",
    ],
    "Chuột": ["Logitech MX Master 3", "Logitech M590", "Microsoft Bluetooth Mouse"],
    "Máy in": [
        "HP LaserJet Pro M404",
        "Canon imageCLASS LBP6230",
        "Brother HL-L2395DW",
    ],
    "Máy chiếu": ["Epson EB-X05", "BenQ MH535", "Optoma HD146X"],
    "Điện thoại": ["iPhone 13", "Samsung Galaxy S21", "Xiaomi Redmi Note 11"],
    "Bàn làm việc": ["Bàn 1m2x0.6m", "Bàn 1m4x0.7m", "Bàn 1m6x0.8m"],
    "Ghế văn phòng": ["Ghế xoay lưng lưới", "Ghế giám đốc da", "Ghế chân quỳ"],
    "Tủ tài liệu": ["Tủ sắt 2 cánh", "Tủ gỗ 3 ngăn", "Tủ hồ sơ 4 tầng"],
}


def init_sample_data():
    app = create_app()

    with app.app_context():
        print("Starting data initialization...")

        # Clear existing data (except admin user)
        print("Clearing existing data...")

        # Get users to keep
        admin_user = User.query.filter_by(username="admin").first()
        users_to_keep = []
        if admin_user:
            users_to_keep.append(admin_user.id)

        # Clear assets first
        Asset.query.delete()

        # Clear asset categories
        AssetCategory.query.delete()

        # Clear UserDepartment associations for users to be deleted
        if users_to_keep:
            ProfileDepartment.query.filter(
                ProfileDepartment.profile_id.notin_(users_to_keep)
            ).delete(synchronize_session=False)
        else:
            ProfileDepartment.query.delete()

        # Now we can safely delete users
        User.query.filter(User.username != "admin").delete(synchronize_session=False)

        # Clear departments
        Department.query.delete()

        db.session.commit()

        # Create asset categories
        print("\nCreating asset categories...")
        categories = []
        category_map = {}  # Map category name to AssetCategory object
        for cat_data in ASSET_CATEGORIES:
            category = AssetCategory(
                name=cat_data["name"], description=cat_data["description"]
            )
            db.session.add(category)
            categories.append(category)
            print(f"  - {category.name}: {category.description}")
        db.session.commit()

        # Build category map after commit (so we have IDs)
        for category in categories:
            category_map[category.name] = category

        # Create departments
        print("\nCreating departments...")
        departments = []
        for dept_data in DEPARTMENTS:
            dept = Department(
                name=dept_data["name"], description=dept_data["description"]
            )
            db.session.add(dept)
            departments.append(dept)
            print(f"  - {dept.name}")
        db.session.commit()

        # Create users and assign to departments using UserDepartment
        print("\nCreating users and assigning to departments...")
        users = []
        for user_data in USERS:
            user = User(
                username=user_data["username"],
                fullname=user_data["fullname"],
                email=user_data["email"],
                role=user_data["role"],
            )
            user.set_password("123456")  # Default password
            db.session.add(user)
            users.append(user)

        db.session.commit()

        # Now create UserDepartment associations
        for user in users:
            # Assign user to 1-2 random departments
            num_depts = random.randint(1, 2)
            assigned_depts = random.sample(departments, num_depts)

            # First department: user is a manager (is_manager=True)
            # Additional departments: user is not a manager (is_manager=False)
            for idx, dept in enumerate(assigned_depts):
                is_manager = idx == 0  # Only first department has manager role
                user_dept = ProfileDepartment(
                    user_id=user.id, department_id=dept.id, is_manager=is_manager
                )
                db.session.add(user_dept)

            dept_names = ", ".join(
                [
                    f"{d.name}{'*' if i == 0 else ''}"
                    for i, d in enumerate(assigned_depts)
                ]
            )
            print(
                f"  - {user.fullname} ({user.username}) -> {dept_names} (* = manager)"
            )

        db.session.commit()

        # Create assets
        print("\nCreating assets...")
        assets = []
        asset_counter = 1

        for category_name in category_map.keys():
            templates = ASSET_TEMPLATES[category_name]
            num_assets = random.randint(8, 15)  # Random number of assets per category

            for i in range(num_assets):
                asset_name = random.choice(templates)
                asset_code = f"AST{asset_counter:04d}"

                # Random purchase date in the last 3 years
                days_ago = random.randint(1, 1095)
                purchase_date = datetime.now().replace(
                    hour=0, minute=0, second=0, microsecond=0
                )

                # Random value between 1M and 50M VND based on category
                value_ranges = {
                    "Laptop": (15000000, 50000000),
                    "Màn hình": (3000000, 10000000),
                    "Bàn phím": (300000, 2000000),
                    "Chuột": (200000, 1500000),
                    "Máy in": (3000000, 15000000),
                    "Máy chiếu": (5000000, 20000000),
                    "Điện thoại": (5000000, 25000000),
                    "Bàn làm việc": (1000000, 5000000),
                    "Ghế văn phòng": (800000, 5000000),
                    "Tủ tài liệu": (1500000, 4000000),
                }
                min_val, max_val = value_ranges.get(category_name, (1000000, 10000000))
                value = random.randint(min_val // 100000, max_val // 100000) * 100000

                # Random status (90% ACTIVE, 8% DAMAGED, 2% DISPOSED)
                status_roll = random.random()
                if status_roll < 0.90:
                    status = AssetStatus.ACTIVE
                elif status_roll < 0.98:
                    status = AssetStatus.DAMAGED
                else:
                    status = AssetStatus.DISPOSED

                # Random location
                locations = [
                    "Tầng 1 - Phòng 101",
                    "Tầng 1 - Phòng 102",
                    "Tầng 2 - Phòng 201",
                    "Tầng 2 - Phòng 202",
                    "Tầng 3 - Phòng 301",
                    "Kho tầng hầm",
                ]
                location = random.choice(locations)

                # Create asset with category_id instead of category string
                asset = Asset(
                    code=asset_code,
                    name=asset_name,
                    category_id=category_map[category_name].id,
                    purchase_date=purchase_date,
                    purchase_value=value,
                    status=status,
                    description=f"{asset_name} - Mã tài sản {asset_code}",
                    location=location,
                    propose_for_liquidation=False,
                )

                db.session.add(asset)
                assets.append(asset)
                asset_counter += 1

        db.session.commit()
        print(f"  Created {len(assets)} assets")

        # Assign 80% of assets to users and departments
        # 20% remain unassigned to users but still in departments
        print("\nAssigning assets to users and departments...")
        num_to_assign = int(len(assets) * 0.8)
        assets_to_assign = random.sample(assets, num_to_assign)

        assigned_count = 0
        unassigned_count = 0

        for asset in assets:
            if asset in assets_to_assign:
                # Assign to random user
                user = random.choice(users)
                asset.assigned_to_user = user.id

                # Assign to one of the user's departments
                user_departments = [
                    assoc.department for assoc in user.department_associations
                ]
                if user_departments:
                    dept = random.choice(user_departments)
                    asset.assigned_to_department = dept.id
                    assigned_count += 1
            else:
                # 20% unassigned assets - randomly assign to a department but no user
                dept = random.choice(departments)
                asset.assigned_to_department = dept.id
                asset.assigned_to_user = None
                unassigned_count += 1

        db.session.commit()
        print(
            f"  Assigned {assigned_count} assets to users ({assigned_count/len(assets)*100:.1f}%)"
        )
        print(
            f"  {unassigned_count} assets in departments but not assigned to users ({unassigned_count/len(assets)*100:.1f}%)"
        )

        # Update department statistics
        print("\nUpdating department statistics...")
        for dept in departments:
            dept.asset_count = dept.assets.count()
            dept.user_count = dept.users().count()
            dept.total_value = sum(
                asset.purchase_value or 0 for asset in dept.assets.all()
            )
            print(
                f"  - {dept.name}: {dept.asset_count} assets, {dept.user_count} users, {dept.total_value:,.0f} VND"
            )
        db.session.commit()

        # Print summary
        print("\n" + "=" * 60)
        print("DATA INITIALIZATION COMPLETE")
        print("=" * 60)
        print(f"\nAsset categories created: {len(categories)}")
        print(f"Departments created: {len(departments)}")
        print(f"Users created: {len(users)} (+ admin)")
        print(f"Assets created: {len(assets)}")
        print(f"  - Assigned: {assigned_count} ({assigned_count/len(assets)*100:.1f}%)")
        print(
            f"  - Unassigned: {len(assets) - assigned_count} ({(len(assets)-assigned_count)/len(assets)*100:.1f}%)"
        )
        print(f"\nDefault password for all users: 123456")
        print(f"Admin credentials: admin / admin123")
        print(
            f"\nNote: Users marked with * are managers of their first listed department"
        )
        print("\n" + "=" * 60)


if __name__ == "__main__":
    init_sample_data()
