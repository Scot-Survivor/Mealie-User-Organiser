

from dotenv import load_dotenv

load_dotenv()

import os
import logging
import requests
import sched
import time
import traceback

LOGGING_LEVEL = os.getenv('LOGGING_LEVEL', 'INFO').upper()
API_KEY = os.getenv('MEALIE_API_KEY')
MEALIE_URL = os.getenv('MEALIE_URL', 'http://localhost:9000')
POLL_INTERVAL_IN_MS = int(os.getenv('POLLING_INTERVAL', 1000))
MEALIE_API_PER_PAGE = int(os.getenv('MEALIE_API_PER_PAGE', 100))

HEADERS = {
    'Authorization': f'Bearer {API_KEY}',
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'Encoding': 'utf-8'
}

if not API_KEY:
    logging.error('MEALIE_API_KEY is not set')
    exit(1)

logging.basicConfig(level=logging.getLevelNamesMapping().get(LOGGING_LEVEL),
                    format='%(asctime)s - %(levelname)s - %(message)s')


def get_all_groups():
    try:
        response = requests.get(f'{MEALIE_URL}/api/admin/groups?perPage={MEALIE_API_PER_PAGE}', headers=HEADERS)
        response.raise_for_status()
        group_data = response.json()
        names = [group['name'] for group in group_data['items']]
        return {group['name']: group for group in group_data['items']}
    except Exception as e:
        if LOGGING_LEVEL == 'DEBUG':
            raise e
        logging.error(f'Failed to get groups: {e}')
        return []


def create_new_group(group_name):
    resp = requests.post(f'{MEALIE_URL}/api/admin/groups', headers=HEADERS, json={'name': group_name})
    resp.raise_for_status()
    logging.debug(f'Created group {group_name}')
    return resp.json()


def update_user_group(group_name, user_id, group_id, user_data):
    data = user_data
    data['group'] = group_name
    data['groupSlug'] = group_name.lower().replace(' ', '-')
    data['group_id'] = group_id
    resp = requests.put(f'{MEALIE_URL}/api/admin/users/{user_id}', headers=HEADERS, json=data)
    resp.raise_for_status()
    logging.info(f'Updated user {user_data["username"]} to group {group_name}')
    return resp.json()


def poll_for_users(scheduler):
    scheduler.enter(POLL_INTERVAL_IN_MS / 1000, 1, poll_for_users, (scheduler,))
    logging.debug('Polling for users...')

    groups = get_all_groups()
    groups_names = groups.keys()

    try:
        response = requests.get(f'{MEALIE_URL}/api/groups/members', headers=HEADERS)
        response.raise_for_status()
        users = response.json()
        logging.debug(f'Found {len(users)} users')

        current_group_data = requests.get(f'{MEALIE_URL}/api/groups/self', headers=HEADERS).json()
        group_name = current_group_data.get('name')

        if group_name not in groups_names:
            raise Exception(f'Group {group_name} not found in groups this shouldn\'t be possible')

        for user in users:
            if user['username'] in group_name:
                continue

            user_uuid = user['id']

            new_group_name = f"{user['username']}'s Group"
            if new_group_name not in groups_names:
                create_new_group(new_group_name)
                groups = get_all_groups()
            group_id = groups[new_group_name]['id']
            sanity_data = update_user_group(new_group_name, user_uuid, group_id, user)
            if sanity_data['group'] != new_group_name:
                raise Exception(f'Failed to update user {user["username"]}')
    except Exception as e:
        if LOGGING_LEVEL == 'DEBUG':
            raise e
        logging.error(f'Failed to get users: {e}')
        return


def main():
    app_scheduler = sched.scheduler(time.time, time.sleep)
    app_scheduler.enter(POLL_INTERVAL_IN_MS / 1000, 1, poll_for_users, (app_scheduler,))
    app_scheduler.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Exiting...")
        exit(0)
    except Exception as e:
        logging.error(e)
        logging.error(traceback.format_exc())
