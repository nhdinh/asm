from selenium.webdriver.support import expected_conditions as EC
from pages.base_page import BasePage
from data.locators import DepartmentPageLocators


class DepartmentPage(BasePage):
    def __init__(self, driver, wait):
        super().__init__(driver, wait)

        self.url = self.base_url + "departments"

        self.locators = DepartmentPageLocators

    def go_to_department_page(self):
        self.go_to_page(self.url)

    def check_title(self, title):
        self.wait.until(EC.title_contains(title))

    def add_new_department(self):
        button_new = self.wait.until(
            EC.element_to_be_clickable(self.locators.ADD_NEW_BUTTON)
        )
        button_new.click()

        name_input = self.wait.until(
            EC.visibility_of_element_located(self.locators.MODAL_NAME_INPUT)
        )
        # desc_input = self.wait.until(
        #     EC.visibility_of_element_located(self.locators.MODAL_DESC_INPUT)
        # )
        name_input.clear()
        # desc_input.clear()

        name_input.send_keys("Phofng ABC")
        # desc_input.send_keys("Phofng ABC")

        submit_btn = self.wait.until(
            EC.element_to_be_clickable(self.locators.MODAL_SUBM_BUTTON)
        )
        submit_btn.click()

        self.wait_page_loaded()

    # def make_a_search(self, input_text):
    #     search_input = self.wait.until(
    #         EC.visibility_of_element_located(self.locators.SEARCH_INPUT)
    #     )
    #     search_input.clear()
    #     search_input.send_keys(input_text)

    #     search_button = self.wait.until(
    #         EC.element_to_be_clickable(self.locators.SEARCH_BUTTON)
    #     )
    #     search_button.click()

    #     self.wait.until(EC.presence_of_all_elements_located(self.locators.RESULTS))
    #     self.driver.save_screenshot("results/results.png")
