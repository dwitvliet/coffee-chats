import json
import os
from datetime import datetime

from utils.models import User, Channel


def save_matches(channel: Channel, paired_users: list[list[User]], paired_group_channels: list[Channel]) -> None:

    today = datetime.today().strftime('%Y-%m-%d')
    path = f'.data/{today}/'
    fname = f'{channel.id}.json'

    json_to_save = json.dumps(
        [{'users': u, 'group_channel': c} for u, c in zip(paired_users, paired_group_channels)], 
        default=lambda o: o.__dict__,
        indent=2,
    )
    
    if not os.path.exists(path):
        os.makedirs(path)

    with open(os.path.join(path, fname), 'w') as f:
        f.write(json_to_save)


def load_matches() -> dict:

    path_start = f'.data/'

    if not os.path.exists(path_start) or len(os.listdir(path_start)) == 0:
        return {}

    path_end = sorted(os.listdir(path_start))[-1]
    path = os.path.join(path_start, path_end)

    matches = {}

    for fname in os.listdir(path):

        channel_id = fname.split('.')[0]

        with open(os.path.join(path, fname), 'r') as f:
            json_to_load = json.loads(f.read())
        channel_matches = [{'users': [User(u) for u in pairs['users']], 'group_channel': Channel(pairs['group_channel'])} for pairs in json_to_load]
        
        matches[channel_id] = channel_matches

    return matches