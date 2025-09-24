# coding=utf-8
import pytest
from pages.department_page import DepartmentPage
from tests.base_test import BaseTest


class TestDepartmentPage(BaseTest):
    @pytest.fixture
    def load_page(self):
        self.page = DepartmentPage(self.driver, self.wait)
        self.page.go_to_page_authorized(self.url)

    def test_title(self, load_page):
        self.page.check_title("Quản lý phòng ban - Hệ thống Quản lý Tài sản")
