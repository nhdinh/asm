# coding=utf-8
import pytest
from pages.department_page import DepartmentPage
from tests.base_test import BaseTest
from selenium.webdriver.support import expected_conditions as EC


class TestDepartmentPage(BaseTest):
    @pytest.fixture
    def load_page(self):
        self.page = DepartmentPage(self.driver, self.wait)
        self.page.go_to_page_authorized(self.page.url)

    def test_title(self, load_page):
        self.page.check_title("Quản lý phòng ban - Hệ thống Quản lý Tài sản")

    def test_add_new_department(self, load_page):
        self.page.add_new_department()
