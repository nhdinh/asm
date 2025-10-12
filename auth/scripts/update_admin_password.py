#!/usr/bin/env python3
"""
Script to update admin password in auth_db database
"""
import sys
import os
import bcrypt
import psycopg2
from getpass import getpass

def get_db_connection():
    """Get database connection"""
    # Read secrets
    with open('/run/secrets/postgres_user', 'r') as f:
        db_user = f.read().strip()

    with open('/run/secrets/postgres_password', 'r') as f:
        db_password = f.read().strip()

    db_host = os.getenv('POSTGRES_HOST', 'postgres')
    db_name = os.getenv('POSTGRES_DB', 'auth_db')

    return psycopg2.connect(
        host=db_host,
        database=db_name,
        user=db_user,
        password=db_password
    )

def hash_password(password):
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def update_password(username, new_password):
    """Update user password"""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Check if user exists
        cur.execute("SELECT id, username FROM users WHERE username = %s", (username,))
        user = cur.fetchone()

        if not user:
            print(f"Error: User '{username}' not found")
            return False

        user_id, user_name = user
        print(f"Found user: {user_name} (ID: {user_id})")

        # Hash new password
        password_hash = hash_password(new_password)

        # Update password
        cur.execute(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (password_hash, user_id)
        )

        conn.commit()
        print(f"✓ Password updated successfully for user '{username}'")
        return True

    except Exception as e:
        conn.rollback()
        print(f"Error updating password: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def main():
    """Main function"""
    print("=" * 50)
    print("Admin Password Update Script")
    print("=" * 50)
    print()

    # Get username (default to admin)
    username = input("Enter username (default: admin): ").strip() or "admin"

    # Get new password
    if len(sys.argv) > 1:
        new_password = sys.argv[1]
        print(f"Using password from command line argument")
    else:
        print("Enter new password (or press Enter for 'Admin@123456'): ")
        new_password = getpass("New password: ").strip()

        if not new_password:
            new_password = "Admin@123456"
            print("Using default password: Admin@123456")
        else:
            # Confirm password
            confirm_password = getpass("Confirm password: ").strip()
            if new_password != confirm_password:
                print("Error: Passwords do not match")
                return 1

    print()
    print(f"Updating password for user: {username}")
    print()

    # Update password
    if update_password(username, new_password):
        print()
        print("Password update completed!")
        return 0
    else:
        return 1

if __name__ == "__main__":
    sys.exit(main())
