# TODO: Make browser headless and check if timings can be reduced by timing them
from dataclasses import dataclass
import pickle
import logging
from time import sleep
import os
from random import random

import requests
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from dotenv import load_dotenv

from config import (
    MESSAGE_LIMIT_PER_MINUTE,
    MESSAGES_PER_PAGE,
    USERS_API_PAUSE_DURATION,
)
from message_user import message_user

print("imports done")

load_dotenv()


logging.basicConfig(level=logging.INFO)

LAST_PAGES_FILEPATH = "last_pages.pickle"
SEEN_USERS_FILEPATH = "seen_users.pickle"
GROUP_USERS_TEMPLATE_URL = "https://www.meetup.com/mu_api/urlname/members?queries=(endpoint:groups/{group_url_name}/members,list:(dynamicRef:list_groupMembers_{group_url_name}_all,merge:(isReverse:!f)),meta:(method:get),params:(filter:all,page:{page}),ref:groupMembers_{group_url_name}_all)"
GROUP_URL = "https://www.meetup.com/{group_url_name}/"
LOGIN_URL = "https://secure.meetup.com/login/"
LOGIN_SUCCESS_URL = "https://www.meetup.com/home/?suggested=true&source=EVENTS"
MESSAGE_TEMPLATE = os.environ["MESSAGE_TEMPLATE"].replace("\n", "").replace("\\n", "\n")


class NoMoreUsersException(Exception):
    pass


@dataclass(frozen=True)
class User:
    id: str
    name: str


@dataclass(frozen=True)
class Group:
    url_name: str
    name: str


class AutoMessager:
    def __init__(
        self,
        username,
        password,
        my_group_url_name,
        groups_list,
        message_template,
        seen_users_filepath,
        last_pages_filepath,
    ):
        self.username = username
        self.password = password
        self.my_group_url_name = my_group_url_name
        self.my_group_user_ids = set()
        self.groups_list = groups_list
        self.message_template = message_template
        self.seen_users_filepath = seen_users_filepath
        self.last_pages_filepath = last_pages_filepath
        self.last_pages = self._get_last_pages(last_pages_filepath)
        self.seen_user_ids = self._get_seen_user_ids(seen_users_filepath)

    def _get_seen_user_ids(self, seen_users_filepath):
        """
        Gets the seen_user_ids set from the file given by seen_users_filepath.
        """
        try:
            with open(seen_users_filepath, "rb") as seen_users_file:
                all_seen_user_ids = pickle.load(seen_users_file)

            return all_seen_user_ids[self.my_group_url_name]
        except FileNotFoundError:
            return set()

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
        self.browser = webdriver.Chrome()
        self._login(self.username, self.password)
        self.my_group_user_ids = self._get_user_ids_of_group(self.my_group_url_name)
        self._message_all_users(self.groups_list, self.message_template)

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

    def _get_user_ids_of_group(self, group_url_name):
        logging.info("getting user ids of group {}".format(group_url_name))
        group_user_ids = set()
        page = 0
        while True:
            users = self._get_page_users(group_url_name, page, filter=False)
            user_ids = {user.id for user in users}
            group_user_ids.update(user_ids)
            if len(users) < MESSAGES_PER_PAGE:
                break
            sleep(USERS_API_PAUSE_DURATION)
            page += 1
        return group_user_ids

    def _message_all_users(self, groups_list, message_template):
        """
        Messages users in all groups.
        """
        logging.info("messaging all users...")
        try:
            for group_url_name in groups_list:
                self._message_group_users(group_url_name, message_template)
        finally:
            self._save_seen_user_ids(self.seen_user_ids)
            self._save_last_pages(self.last_pages)

    def _message_group_users(self, group_url_name, message_template):
        """
        Messages all users in a particular group.
        """
        logging.info("messaging users in group {}".format(group_url_name))
        group_name = self._get_group_name(group_url_name)
        group = Group(group_url_name, group_name)
        while True:
            try:
                self._message_next_page_users(group, message_template)
            except NoMoreUsersException:
                break

    def _get_group_name(self, group_url_name):
        logging.info("getting group name for {}".format(group_url_name))
        self.browser.get(GROUP_URL.format(group_url_name=group_url_name))
        group_name = self.browser.find_element(
            By.XPATH, "//a[@id='group-name-link']/h1"
        ).text
        return group_name

    def _message_next_page_users(self, group, message_template):
        """
        Messages the next page of users in a particular group.
        """
        page = self.last_pages[group.url_name]
        users = self._get_page_users(group.url_name, page)
        if not users:
            raise NoMoreUsersException()
        self._message_users(users, group, message_template)
        self._increase_last_page(group)

    def _get_page_users(self, group_url_name, page, filter=True):
        """
        Gets the next page of users for a particular group.
        """
        logging.info(
            "getting page {} of users for group {}".format(page, group_url_name)
        )
        group_users_url = GROUP_USERS_TEMPLATE_URL.format(
            group_url_name=group_url_name, page=page
        )
        res = requests.get(group_users_url)
        data = res.json()
        user_data = data["responses"][0]["value"]["value"]
        users = [User(user["id"], user["name"]) for user in user_data]
        logging.info("got {} users".format(len(users)))
        if filter:
            users = self._filter_users(users)
            logging.info("filtered to {} users".format(len(users)))
        return users

    def _filter_users(self, users):
        """
        Filters out users that have already been seen or who are already in my group.
        """
        users = [
            user
            for user in users
            if user.id not in self.seen_user_ids
            and user.id not in self.my_group_user_ids
        ]
        return users

    def _human_like_delay(self):
        """
        Delays for a random amount of time between 1 and 2 seconds.
        """
        sleep(random() + 1)

    def _message_users(self, users, group, message_template):
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
            message_user(user, group.name, message_template)
            sleep(MESSAGE_CYCLE_DURATION)
            self._human_like_delay()
            self.seen_user_ids.add(user.id)

    def _increase_last_page(self, group):
        """
        Increases the last page for a particular group.
        """
        self.last_pages.setdefault(group.url_name, -1)
        self.last_pages[group.url_name] += 1

    def _save_last_pages(self, last_pages):
        logging.info("saving last pages")
        with open(self.last_pages_filepath, "wb") as last_pages_file:
            pickle.dump(last_pages, last_pages_file)

    def _save_seen_user_ids(self, seen_user_ids):
        logging.info("saving seen user ids")
        all_seen_user_ids = {}
        try:
            with open(self.seen_users_filepath, "rb") as seen_users_file:
                all_seen_user_ids = pickle.load(seen_users_file)
        except FileNotFoundError:
            pass

        all_seen_user_ids[self.my_group_url_name] = seen_user_ids

        with open(self.seen_users_filepath, "wb") as seen_users_file:
            pickle.dump(all_seen_user_ids, seen_users_file)


if __name__ == "__main__":
    AutoMessager(
        os.environ["USERNAME"],
        os.environ["PASSWORD"],
        os.environ["MY_GROUP_URL_NAME"],
        os.environ["GROUPS_LIST"],
        MESSAGE_TEMPLATE,
        SEEN_USERS_FILEPATH,
        LAST_PAGES_FILEPATH,
    ).start()
