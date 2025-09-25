from selenium.webdriver.common.by import By


class BasePageLocators:
    LOGIN_FORM = (By.ID, "login_box")
    LOGIN_USERNAME_INPUT = (By.XPATH, "//*[@id='login_box']//input[@id='username']")
    LOGIN_PASSWORD_INPUT = (By.XPATH, "//*[@id='login_box']//input[@id='password']")
    LOGIN_BUTTON = (By.XPATH, "//*[@id='login_box']//button[@type='submit']")


class DepartmentPageLocators:
    ADD_NEW_BUTTON = (
        By.XPATH,
        "//button[@data-bs-target='#addDepartmentModal']",
    )

    MODAL_NAME_INPUT = (By.XPATH, "//input[@id='addName']")
    MODAL_DESC_INPUT = (By.XPATH, "//textarea[@id='addDescription]")
    MODAL_SUBM_BUTTON = (By.XPATH, "//button[@type='submit']")
