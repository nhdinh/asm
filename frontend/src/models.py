from datetime import date
from typing import Optional


class User:
    id: Optional[int]
    username: str
    password_hash: str
    full_name: str
    role: str
    is_active: bool
    created_at: date


class Manager(User): ...


class Department:
    id: Optional[int]
    name: str
    description: str
    manager: Manager
    created_at: date


class Asset:
    id: Optional[int]
    code: str
    name: str
    description: str
    category: str
    value: float
    purchase_date: date
    current_department: Department
    status: str

    def __init__(self, **kwargs):
        self.id = kwargs.get("id", None)

        self.code = kwargs["code"]
        self.name = kwargs["name"]
        self.description = kwargs.get("description", "")
        self.category = kwargs.get("category", "")
        self.value = kwargs["value"]
        self.purchase_date = kwargs["purchase_date"]
        self.status = kwargs.get("status", "active")

        # parse department
