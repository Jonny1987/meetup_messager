import logging

from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

logging.getLogger(__name__)

USER_TEMPLATE_URL = "https://www.meetup.com/members/{}"


def _open_user_profile_page(browser, user):
    user_url = USER_TEMPLATE_URL.format(user.id)
    browser.get(user_url)


def _open_compose_message_page(browser, original_window):
    wait = WebDriverWait(browser, 10)

    compose_message_button = wait.until(
        EC.presence_of_element_located(
            (By.XPATH, '//button[@data-event-label="other_profile_message_click"]')
        )
    )
    compose_message_button.click()

    wait.until(EC.number_of_windows_to_be(2))

    # Loop through until we find a new window handle
    for window_handle in browser.window_handles:
        if window_handle != original_window:
            browser.switch_to.window(window_handle)
            break


def _send_message(browser, user, group_name, message_template):
    wait = WebDriverWait(browser, 10)

    textarea = wait.until(EC.element_to_be_clickable((By.ID, "messaging-new-convo")))

    first_name = user.name.split()[0]
    message = message_template.format(first_name=first_name, group_name=group_name)
    textarea.send_keys(message)

    send_message_button = browser.find_element(By.ID, "messaging-new-send")
    send_message_button.click()

    wait.until(EC.url_contains("convo_id="))


def message_user(browser, user, group_name, message_template):
    """
    Messages a particular user using the message_template.
    """
    logging.info("sending message to user {}".format(user.id))
    _open_user_profile_page(browser, user)
    original_window = browser.current_window_handle
    _open_compose_message_page(browser, original_window)
    _send_message(browser, user, group_name, message_template)
