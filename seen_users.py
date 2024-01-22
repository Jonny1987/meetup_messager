import pickle
from argparse import ArgumentParser

from private_config import MY_GROUP_URL_NAME


def add_user_to_seen(user_id):
    with open("seen_users.pickle", "rb") as seen_users_file:
        seen_users = pickle.load(seen_users_file)
    seen_users[MY_GROUP_URL_NAME].add(user_id)

    with open("seen_users.pickle", "wb") as seen_users_file:
        pickle.dump(seen_users, seen_users_file)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--add", help="user id to add to seen_users.pickle")

    args = parser.parse_args()

    if args.add:
        add_user_to_seen(args.add)
    else:
        with open("seen_users.pickle", "rb") as seen_users_file:
            seen_users = pickle.load(seen_users_file)
        print(seen_users)
