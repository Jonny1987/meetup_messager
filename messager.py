# TODO: Make browser headless and check if timings can be reduced by timing them
import pickle
import logging
from time import sleep
from random import random

from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from private_config import (
    GROUPS_LIST,
    MESSAGE_TEMPLATES,
    USERNAME,
    PASSWORD,
    MY_GROUP_URL_NAME,
)
from utils.message_user import message_user
from models import Group
from utils.seen_user_ids import get_seen_user_ids, save_seen_user_ids

logging.basicConfig(level=logging.INFO)

LAST_PAGES_FILEPATH = "last_pages.pickle"
SEEN_USERS_FILEPATH = "seen_users.pickle"
LAST_MESSAGE_TEMPLATE_INDEX_FILEPATH = "last_message_template_index.pickle"
GROUP_URL = "https://www.meetup.com/{group_url_name}/"
LOGIN_URL = "https://secure.meetup.com/login/"
LOGIN_SUCCESS_URL = "https://www.meetup.com/home/?suggested=true&source=EVENTS"

MESSAGE_LIMIT_PER_MINUTE = 1


class NoMoreUsersException(Exception):
    pass


class AutoMessager:
    def __init__(
        self,
        username,
        password,
        my_group_url_name,
        groups_list,
        message_templates,
        seen_users_filepath,
        last_pages_filepath,
    ):
        self.username = username
        self.password = password
        self.my_group_url_name = my_group_url_name
        self.my_group_user_ids = set()
        self.groups_list = groups_list
        self.message_templates = message_templates
        self.seen_users_filepath = seen_users_filepath
        self.last_pages_filepath = last_pages_filepath
        self._get_state()

    def _get_state(self):
        self.last_pages = self._get_last_pages(self.last_pages_filepath)
        self.seen_user_ids = get_seen_user_ids(
            self.seen_users_filepath,
            self.my_group_url_name,
        )
        self.last_message_template_index = self._get_last_message_template_index()

    def _get_last_message_template_index(self):
        """
        Gets the last message template index from the file given by seen_users_filepath.
        """
        try:
            with open(
                LAST_MESSAGE_TEMPLATE_INDEX_FILEPATH, "rb"
            ) as last_message_template_index_file:
                last_message_template_index = pickle.load(
                    last_message_template_index_file
                )

            return last_message_template_index
        except FileNotFoundError:
            return 0

    def _get_last_pages(self, last_pages_filepath):
        """
        Gets the last_pages from the file given by LAST_PAGES_FILEPATH
        """
        last_pages = {group_name: 1 for group_name in self.groups_list}
        try:
            with open(last_pages_filepath, "rb") as last_pages_file:
                saved_last_pages = pickle.load(last_pages_file)

            last_pages.update(saved_last_pages)
        except FileNotFoundError:
            pass

        return last_pages

    def start(self):
        """
        Login and message users
        """
        logging.info("starting...")
        options = ChromeOptions()
        options.add_argument("--headless=new")
        self.browser = Chrome(options=options)
        self._login(self.username, self.password)
        self.my_group_user_ids = self._get_user_ids(self.my_group_url_name)
        self._message_all_users(self.groups_list)

    def _login(self, username, password):
        """
        Logs in to meetup.com
        """
        logging.info("logging in...")
        self.browser.get(LOGIN_URL)
        username_box = self.browser.find_element(By.ID, "email")
        password_box = self.browser.find_element(By.ID, "current-password")
        submit_button = self.browser.find_element(
            By.XPATH, '//button[@name="submitButton"]'
        )

        username_box.send_keys(username)
        password_box.send_keys(password)
        submit_button.click()
        WebDriverWait(self.browser, 10).until(EC.url_to_be(LOGIN_SUCCESS_URL))
        logging.info("successfully logged in")

    def _message_all_users(self, groups_list):
        """
        Messages users in all groups.
        """
        logging.info("messaging all users...")
        try:
            for group_url_name in groups_list:
                self._message_group_users(group_url_name)
        finally:
            self._save_state()

    def _message_group_users(self, group_url_name):
        """
        Messages all users in a particular group.
        """
        logging.info("messaging users in group {}".format(group_url_name))
        group_name = self._get_group_name(group_url_name)
        group = Group(group_url_name, group_name)
        while True:
            try:
                self._message_next_page_users(group)
            except NoMoreUsersException:
                break

    def _get_group_name(self, group_url_name):
        logging.info("getting group name for {}".format(group_url_name))
        self.browser.get(GROUP_URL.format(group_url_name=group_url_name))
        group_name = self.browser.find_element(
            By.XPATH, "//a[@id='group-name-link']/h1"
        ).text
        return group_name

    def _message_next_page_users(self, group):
        """
        Messages the next page of users in a particular group.
        """
        page = self.last_pages[group.url_name]
        users = self._get_page_users(group.url_name, page)
        if not users:
            raise NoMoreUsersException()
        self._message_users(users, group)
        self._increase_last_page(group)

    def _human_like_delay(self):
        """
        Delays for a random amount of time between 0 and 5 seconds.
        """
        sleep(random() * 5)

    def _get_next_message_template(self):
        """
        Gets the next message template
        """
        # Dont actually increase last_message_template_index here, as this is done
        # in _message_users to ensure that it is only updates straight after a message
        # is sent
        next_index = (self.last_message_template_index + 1) % len(
            self.message_templates
        )
        return self.message_templates[next_index]

    def _increase_last_message_template_index(self):
        self.last_message_template_index = (self.last_message_template_index + 1) % len(
            self.message_templates
        )

    def _message_users(self, users, group):
        """
        Messages all users in the given list, pausing after MESSAGE_LIMIT for
        PAUSE_DURATION so as not to bypass the rate limit.

        Saves last_seen_users and last_pages to file on error or when finished.
        """
        logging.info("messaging users...")
        ERROR_MARGIN = 1
        MESSAGE_CYCLE_DURATION = 60 / MESSAGE_LIMIT_PER_MINUTE + ERROR_MARGIN
        for user in users:
            logging.info("messaging user {}".format(user.id))
            message_template = self._get_next_message_template()
            message_user(user, group.name, message_template, self.browser)
            self.seen_user_ids.add(user.id)
            self._increase_last_message_template_index()
            sleep(MESSAGE_CYCLE_DURATION)
            self._human_like_delay()

    def _increase_last_page(self, group):
        """
        Increases the last page for a particular group.
        """
        self.last_pages.setdefault(group.url_name, -1)
        self.last_pages[group.url_name] += 1

    def _save_state(self):
        save_seen_user_ids(
            self.seen_user_ids,
            self.seen_users_filepath,
            self.my_group_url_name,
        )
        self._save_last_pages(self.last_pages)
        self._save_last_message_template_index()

    def _save_last_pages(self, last_pages):
        logging.info("saving last pages")
        with open(self.last_pages_filepath, "wb") as last_pages_file:
            pickle.dump(last_pages, last_pages_file)

    def _save_last_message_template_index(self):
        logging.info("saving last message template index")
        with open(
            LAST_MESSAGE_TEMPLATE_INDEX_FILEPATH, "wb"
        ) as last_message_template_index_file:
            pickle.dump(
                self.last_message_template_index, last_message_template_index_file
            )


if __name__ == "__main__":
    AutoMessager(
        USERNAME,
        PASSWORD,
        MY_GROUP_URL_NAME,
        GROUPS_LIST,
        MESSAGE_TEMPLATES,
        SEEN_USERS_FILEPATH,
        LAST_PAGES_FILEPATH,
    ).start()
