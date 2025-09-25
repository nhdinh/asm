import datetime
import os
import pickle
from selenium.webdriver.support import expected_conditions as EC

from data.locators import BasePageLocators
from dotenv import load_dotenv


class BasePage:
    base_url = "http://localhost:8080/"
    cookie_jar_file = "./cookie.pkl"
    screenshot_dir = "./screenshots/"

    def __init__(self, driver, wait):
        load_dotenv()

        self.driver = driver
        self.wait = wait
        self.locators = BasePageLocators

        # make screenshot dir
        os.makedirs(self.screenshot_dir, exist_ok=True)

    def go_to_page(self, url):
        self.driver.get(url)

        # wait until page is completely loaded
        self.wait_page_loaded()

    def go_to_page_authorized(self, url):
        self.go_to_page(url)

        if not self.is_authorized():
            # self.driver.save_screenshot(self.screenshot_dir + "unauthorized.png")

            # check and load cookies
            if not self.load_cookie():
                self.login_as_user(os.getenv("user"), os.getenv("user_password"))

            self.go_to_page(url)

    def go_to_page_admin_authorized(self, url):
        self.go_to_page(url)

        if not self.is_admin_authorized():
            if not self.load_cookie():
                self.login_as_user(os.getenv("admin"), os.getenv("admin_password"))

            self.go_to_page(url)

    def get_title(self):
        return self.driver.title

    def logout(self):
        self.go_to_page(self.base_url + "logout")

    def is_authorized(self) -> bool:
        self.driver.get_cookies() == []

    def login_as_user(self, username: str, password: str):
        if not username or not password:
            raise "Username or Password is empty"

        username_input = self.wait.until(
            EC.visibility_of_element_located(self.locators.LOGIN_USERNAME_INPUT)
        )
        password_input = self.wait.until(
            EC.visibility_of_element_located(self.locators.LOGIN_PASSWORD_INPUT)
        )
        username_input.clear()
        username_input.send_keys(username)
        password_input.clear()
        password_input.send_keys(password)

        login_button = self.wait.until(
            EC.element_to_be_clickable(self.locators.LOGIN_BUTTON)
        )
        login_button.click()

        self.wait_page_loaded()

        # assert that the user has been logged in
        self.driver.save_screenshot(self.screenshot_dir + "after_click_login.png")

        self.save_cookie()

    def wait_page_loaded(self):
        self.wait.until(
            lambda driver: driver.execute_script("return document.readyState")
            == "complete"
        )

    def save_cookie(self):
        # then pickle the cookies
        cookies = self.driver.get_cookies()
        with open(self.cookie_jar_file, "wb") as f:
            pickle.dump(self.driver.get_cookies(), f)

    def load_cookie(self) -> bool:
        if os.path.exists(self.cookie_jar_file):
            creation_timestamp = os.path.getctime(self.cookie_jar_file)
            creation_datetime = datetime.datetime.fromtimestamp(creation_timestamp)
            current_datetime = datetime.datetime.now()
            time_difference = current_datetime - creation_datetime

            # Check if the difference is greater than one day
            if time_difference < datetime.timedelta(days=1):
                with open(self.cookie_jar_file, "rb") as f:
                    cookies = pickle.load(f)
                    for cookie in cookies:
                        self.driver.add_cookie(cookie)

                return True

        return False
