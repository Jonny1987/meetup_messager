import logging
import pickle


def get_seen_user_ids(seen_users_filepath, my_group_url_name):
    """
    Gets the seen_user_ids set from the file given by seen_users_filepath.
    """
    try:
        with open(seen_users_filepath, "rb") as seen_users_file:
            all_seen_user_ids = pickle.load(seen_users_file)

        return all_seen_user_ids[my_group_url_name]
    except FileNotFoundError:
        return set()


def save_seen_user_ids(seen_user_ids, seen_users_filepath, my_group_url_name):
    logging.info("saving seen user ids")
    all_seen_user_ids = {}
    try:
        with open(seen_users_filepath, "rb") as seen_users_file:
            all_seen_user_ids = pickle.load(seen_users_file)
    except FileNotFoundError:
        pass

    all_seen_user_ids[my_group_url_name] = seen_user_ids

    with open(seen_users_filepath, "wb") as seen_users_file:
        pickle.dump(all_seen_user_ids, seen_users_file)
