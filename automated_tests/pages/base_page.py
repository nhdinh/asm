import datetime
import os
import pickle
from selenium.webdriver.support import expected_conditions as EC


class BasePage:
    base_url = "http://localhost:8080/"

    def __init__(self, driver, wait):
        self.driver = driver
        self.wait = wait
        cookie_jar_file = "./cookie.pkl"

        if os.path.exists(cookie_jar_file):
            creation_timestamp = os.path.getctime(cookie_jar_file)
            creation_datetime = datetime.datetime.fromtimestamp(creation_timestamp)
            current_datetime = datetime.datetime.now()
            time_difference = current_datetime - creation_datetime

            # Check if the difference is greater than one day
            if time_difference < datetime.timedelta(days=1):
                with open(cookie_jar_file, "rb") as f:
                    cookies = pickle.load(f)
                    for cookie in cookies:
                        driver.add_cookie(cookie)

    def go_to_page(self, url):
        self.driver.get(url)

        # wait until page is completely loaded
        self.wait.until(
            lambda driver: driver.execute_script("return document.readyState")
            == "complete"
        )

    def go_to_page_authorized(self, url):
        self.go_to_page(url)

        if not self.page.is_authorized():
            ...

    def go_to_page_admin_authorized(self, url):
        self.go_to_page(url)

        if not self.page.is_admin_authorized():
            ...

    def get_title(self):
        return self.driver.title

    def logout(self): ...

    def is_authorized(self) -> bool:
        cookies = self.driver.get_cookies()
        print(cookies)
        return "session" in cookies

    def login_as_user(self): ...

    def login_as_admin(self): ...
