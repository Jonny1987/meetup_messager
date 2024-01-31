import logging
from time import sleep
import requests

from models import User


USERS_API_PAUSE_DURATION = 0.1
MESSAGES_PER_PAGE = 30

GROUP_USERS_TEMPLATE_URL = "https://www.meetup.com/mu_api/urlname/members?queries=(endpoint:groups/{group_url_name}/members,list:(dynamicRef:list_groupMembers_{group_url_name}_all,merge:(isReverse:!f)),meta:(method:get),params:(filter:all,page:{page}),ref:groupMembers_{group_url_name}_all)"


def get_user_ids(group_url_name):
    logging.info("getting user ids of group {}".format(group_url_name))
    group_user_ids = set()
    page = 0
    while True:
        users = _get_page_users(group_url_name, page, filter=False)
        user_ids = {user.id for user in users}
        group_user_ids.update(user_ids)
        if len(users) < MESSAGES_PER_PAGE:
            break
        sleep(USERS_API_PAUSE_DURATION)
        page += 1
    return group_user_ids


def _get_page_users(group_url_name, page, filter=True):
    """
    Gets the next page of users for a particular group.
    """
    logging.info("getting page {} of users for group {}".format(page, group_url_name))
    group_users_url = GROUP_USERS_TEMPLATE_URL.format(
        group_url_name=group_url_name, page=page
    )
    res = requests.get(group_users_url)
    data = res.json()
    user_data = data["responses"][0]["value"]["value"]
    users = [User(user["id"], user["name"]) for user in user_data if user["role"] == ""]
    logging.info("got {} users".format(len(users)))
    if filter:
        users = _filter_users(users)
        logging.info("filtered to {} users".format(len(users)))
    return users


def _filter_users(self, users):
    """
    Filters out users that have already been seen or who are already in my group.
    """
    users = [
        user
        for user in users
        if user.id not in self.seen_user_ids and user.id not in self.my_group_user_ids
    ]
    return users
