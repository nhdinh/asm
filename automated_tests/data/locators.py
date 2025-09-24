from selenium.webdriver.common.by import By


class BasePageLocators:
    LOGIN_FORM = (By.ID, "login_box")
    LOGIN_USERNAME_INPUT = (By.XPATH, "//*[@id='login_box']//*[@id='username']")
    LOGIN_PASSWORD_INPUT = (By.XPATH, "//*[@id='login_box']//*[@id='password']")
    LOGIN_BUTTON = (By.XPATH, "//*[@id='login_box']//*[@type='submit']")


class DepartmentPageLocators:
    SEARCH_INPUT = (By.ID, "searchbox_input")
    SEARCH_BUTTON = (By.XPATH, "//*[@id='searchbox_homepage']//*[@type='submit']")
    RESULTS = (By.XPATH, "//*[@data-testid='mainline']//*[@data-testid='result']")
