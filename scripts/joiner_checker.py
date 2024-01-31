from argparse import ArgumentParser

from private_config import MY_GROUP_URL_NAME
from utils.get_users import get_user_ids
from utils.seen_user_ids import get_seen_user_ids

parser = ArgumentParser()
parser.add_argument("--index", help="The index of the group whose seen_users to check")

SEEN_USERS_FILEPATH = "seen_users.pickle"
seen_user_ids = get_seen_user_ids(SEEN_USERS_FILEPATH, MY_GROUP_URL_NAME)

group_user_ids = get_user_ids(MY_GROUP_URL_NAME)
users_joined = [user_id for user_id in group_user_ids if user_id in seen_user_ids]

print(f"users joined: {len(users_joined)}/{len(group_user_ids)}")
print("user ids:")
for user_id in users_joined:
    print(user_id)
