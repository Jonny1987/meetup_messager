from config import username, password, groups_list, limit, message_template

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pickle
import logging
from time import sleep

logging.basicConfig(level=logging.INFO)


class AutoMessager():
    group_users_template_url = "https://www.meetup.com/{}/members/?offset={}&sort=name&desc=1"
    user_template_url = "https://www.meetup.com/{}/members/{}"
    def __init__(self, username, password, groups_list, message_template, seen_users_filepath):
        self.username = username
        self.password = password
        self.groups_list = groups_list
        self.message_template = message_template
        self.last_offsets_filepath = "last_offsets.pickle"
        self.last_offsets = self._get_last_offsets(self.last_offsets_filepath)
        self.seen_users_filepath = seen_users_filepath
        self.seen_user_ids = self._get_seen_user_ids(seen_users_filepath)
        self.max_number = 10
        self.pause_duration = 600
        self.users_per_page = 10

    def _get_seen_user_ids(self, seen_users_filepath):
        """
        Gets the seen_user_ids from the file given by seen_users_filepath.
        """
        with open(seen_users_filepath, 'r') as seen_users_file:
            seen_user_ids = seen_users_file.read().splitlines()

        return seen_user_ids

    def _get_last_offsets(self, last_offsets_filepath):
        """
        Gets the last_offsets from the file given by last_offsets_filepath
        """
        last_offsets = {group_name: -1 for group_name in self.groups_list}
        try:
            with open(last_offsets_filepath, 'r') as last_offsets_file:
                saved_last_offsets = pickle.load(last_offsets_file)

            last_offsets.update(saved_last_offsets)
            return last_offsets

        except IOError:
            return {group: -1 for group in self.groups_list}

    def start(self, limit):
        """
        Login and message users
        """
        self.browser = webdriver.Chrome()
        self._login(self.username, self.password)
        self._message_users(self.groups_list, self.message_template, limit)

    def _login(self, username, password):
        logging.info("logging in...")
        self.browser.get("https://secure.meetup.com/login/")
        username_box = self.browser.find_element_by_id('email')
        password_box = self.browser.find_element_by_id('password')
        submit_button = self.browser.find_element_by_xpath('//input[@name="submitButton"]')

        username_box.send_keys(username)
        password_box.send_keys(password)
        submit_button.click()
        WebDriverWait(self.browser, 10).until(
            EC.url_to_be("https://www.meetup.com/")
        )
        logging.info("successfully logged in")

    def _message_users(self, groups_list, message_template, limit):
        logging.info("messaging users...")
        group_limits = self._split_groups_equally(groups_list, limit)
        group_users = self._get_user_ids(group_limits, self.last_offsets)

        message_count = 0
        try:
            for group_name, user_ids in group_users.iteritems():
                for user_id in user_ids:
                    if message_count == self.max_number:
                        logging.info("Pausing for {} minutes before continuing".format(self.pause_duration/60))
                        sleep(self.pause_duration)
                        logging.info("Pause finished, resuming messaging")
                        message_count = 0

                    self._message_user(user_id, group_name, self.message_template)
                    message_count += 1
                    self.seen_user_ids.append(user_id)
                    self.last_offsets[group_name] += 1

        finally:
            self._save_seen_user_ids(self.seen_user_ids)
            self._save_last_offsets(self.last_offsets)

    def _split_groups_equally(self, groups_list, limit):
        """
        Returns a dict with groups for the keys and limit (number of people to message for that group)
        as the values
        """
        limit1 = limit//len(groups_list)
        count1 = len(groups_list) - (limit % len(groups_list))

        group_limits = {}
        for group in groups_list:
            group_limits[group] = limit1 + int(count1 <= 0)
            count1 -= 1

        return group_limits

    def _get_user_ids(self, group_limits, last_offsets):
        group_user_ids = {}
        for group_name, group_limit in group_limits.iteritems():
            group_user_ids[group_name] = self._get_group_user_ids(group_name, last_offsets, group_limit)

        return group_user_ids

    def _get_group_user_ids(self, group_name, last_offsets, group_limit):
        """
        Gets the n user ids for a particular group, where n=group_limit, and where the
        starting user is given by last_offsets
        """
        start_offset = last_offsets[group_name] + 1
        current_offset = start_offset
        unseen_user_ids = {}

        while current_offset < start_offset + group_limit:
            page = current_offset / self.users_per_page
            page_item = current_offset % self.users_per_page

            group_users_url = AutoMessager.group_users_template_url.format(group_name, page)
            self.browser.get(group_users_url)
            li_elements = self.browser.find_elements_by_xpath("//ul[@id=\"memberList\"]/li")
            page_user_ids = [str(element.get_attribute("data-memid")) for element in li_elements]

            no_remaining_users = start_offset + group_limit - current_offset
            unseen_page_user_ids = page_user_ids[page_user_ids:no_remaining_users]
            unseen_user_ids += unseen_page_user_ids
            current_offset += len(unseen_page_user_ids)

        return unseen_user_ids

    def _message_user(self, user_id, group_name, message_template):
        """
        Messages a particular user (given by the user_id) using the message_template.
        """
        logging.info("sending message to user {}".format(user_id))
        user_url = AutoMessager.user_template_url.format(group_name, user_id)
        self.browser.get(user_url)
        member_name = self.browser.find_elements_by_xpath("//span[contains(@class, 'memName')]")[0].text
        compose_message_button = self.browser.find_elements_by_xpath("//li[contains(@class, 'contactMember')]/a")[0]
        compose_message_button.click()
        first_name = member_name.split()[0]
        message = message_template.format(first_name=first_name, group_name=group_name)
        textarea = self.browser.find_element_by_id("messaging-new-convo")
        try:
            textarea.send_keys(message)
        except WebDriverException:
            logging.info("not sending message to {} due to WebDriver error when pasting message".format(user_id))
            return

        send_message_button = self.browser.find_element_by_id("messaging-new-send")
        # send_message_button.click()

    def _save_last_offsets(self, last_offsets):
        with open(self.last_offsets_filepath, 'w') as last_offsets_file:
            pickle.dump(last_offsets, last_offsets_file)

    def _save_seen_user_ids(self, seen_user_ids):
        with open(self.seen_users_filepath, 'w') as seen_users_file:
            seen_users_file.writelines(seen_user_ids)


message_template = unicode(message_template)
seen_users_filepath = "seen_users.txt"
results = AutoMessager(username, password, groups_list, message_template, seen_users_filepath).start(limit)


