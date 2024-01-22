import os

import pytest
from selenium import webdriver
from unittest.mock import patch

from messager import AutoMessager, User, Group
from message_user import message_user
from private_config import (
    MESSAGE_TEMPLATES,
    USERNAME,
    PASSWORD,
    TEST_MY_GROUP_URL_NAME,
    TEST_GROUP_URL_NAME,
    TEST_MY_GROUP_NAME,
    TEST_USER_ID,
)

LOGIN_URL = "https://secure.meetup.com/login/"
SUCCESS_URL = "https://www.meetup.com/home/?suggested=true&source=EVENTS"


@pytest.fixture
def browser():
    driver = webdriver.Chrome()
    yield driver
    driver.quit()


@pytest.fixture
def auto_messager():
    messager = AutoMessager(
        USERNAME,
        PASSWORD,
        TEST_MY_GROUP_URL_NAME,
        ["test-group"],
        [MESSAGE_TEMPLATES[0]],
        "",
        "",
    )
    messager._seen_user_ids = set()
    return messager


def test_login_success(auto_messager, browser):
    auto_messager.browser = browser
    # TimeoutException will be raised if login fails
    auto_messager._login(auto_messager.username, auto_messager.password)


def test_get_user_ids_of_group(auto_messager):
    user_ids = auto_messager._get_user_ids_of_group(auto_messager.my_group_url_name)
    print(f"users in my group: {len(user_ids)}")
    assert len(user_ids) > 0
    assert all([isinstance(item, str) for item in user_ids])
    # check all care integers in string form
    [int(user_id) for user_id in user_ids]


def test_get_next_users_no_filter(auto_messager):
    users1 = auto_messager._get_page_users(TEST_GROUP_URL_NAME, 1)
    users2 = auto_messager._get_page_users(TEST_GROUP_URL_NAME, 2)

    intercection = set(users1).intersection(set(users2))

    assert len(users1) == 30
    assert len(users2) == 30
    assert all([isinstance(item, User) for item in users1])
    assert all([isinstance(item, User) for item in users2])
    assert intercection == set()


def test_filter_users(auto_messager):
    users = [User(id=str(i), name=f"User {i}") for i in range(1, 11)]

    auto_messager.seen_user_ids = {"1", "3", "7"}
    auto_messager.my_group_user_ids = {"4", "6", "9"}
    filtered_users = auto_messager._filter_users(users)

    assert filtered_users == [
        User("2", "User 2"),
        User("5", "User 5"),
        User("8", "User 8"),
        User("10", "User 10"),
    ]


def test_get_group_name(auto_messager, browser):
    auto_messager.browser = browser
    group_name = auto_messager._get_group_name(TEST_MY_GROUP_URL_NAME)
    assert group_name == TEST_MY_GROUP_NAME


@patch("messager.message_user")
@patch("messager.sleep")
def test_message_users(
    mock_sleep,
    mock_message_user,
    auto_messager,
    browser,
):
    MOCK_GROUP = Group("example-group", "Example Group")
    MOCK_USERS = [
        User(id=f"user{i}", name=f"User {i}") for i in range(1, 6)
    ]  # Creating 5 mock users

    auto_messager.browser = browser

    auto_messager._message_users(
        MOCK_USERS,
        MOCK_GROUP,
    )

    # Check if _message_user was called for each user
    assert mock_message_user.call_count == len(
        MOCK_USERS
    ), "Not all users were messaged"

    # Check if message_user was called with the correct arguments
    assert all(
        mock_message_user.call_args_list[i][0][0] == MOCK_USERS[i]
        for i in range(len(MOCK_USERS))
    ), "message_user was not called with the correct arguments"


@pytest.fixture()
def clearup_files():
    yield
    try:
        os.remove("seen_users_test.pkl")
        os.remove("last_pages_test.pkl")
    except FileNotFoundError:
        pass


@patch("messager.message_user")
@patch("messager.MESSAGE_LIMIT_PER_MINUTE", 1000)
def test_auto_messager(mock_message_user, clearup_files):
    messager = AutoMessager(
        USERNAME,
        PASSWORD,
        TEST_MY_GROUP_URL_NAME,
        [TEST_MY_GROUP_URL_NAME],
        MESSAGE_TEMPLATES[0],
        "seen_users_test.pkl",
        "last_pages_test.pkl",
    )
    messager._human_like_delay = lambda: 0
    messager._filter_users = lambda users: users
    messager.start()

    assert mock_message_user.call_count > 10
    assert len(messager.seen_user_ids) == mock_message_user.call_count
    users = [call_obj.args[0] for call_obj in mock_message_user.call_args_list]
    assert len(set(users)) == len(users)
    assert all([isinstance(user, User) for user in users])


# # This test is commented out because it actually sends a message to a user which needs
# # to be manually checked.
# def test_message_user(auto_messager, browser):
#     auto_messager.browser = browser
#     auto_messager._login(auto_messager.username, auto_messager.password)
#     message_user(
#         browser,
#         User(TEST_USER_ID, "Test User"),
#         "Other Meetup Group",
#         auto_messager.message_template,
#     )
