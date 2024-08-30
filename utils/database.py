import json
import os
import boto3
from datetime import datetime

from utils.models import User, Channel


def save_matches(channel: Channel, paired_users: list[list[User]], paired_group_channels: list[Channel]) -> None:
    print(1)
    dynamodb = boto3.resource('dynamodb')
    print(2)
    table = dynamodb.Table('intros')
    print(3)
    for users, group_channel in zip(paired_users, paired_group_channels):
        item = {
            'channel': channel.id,
            'date': datetime.today().strftime('%Y-%m-%d'),
            'users': [u.id for u in users],
            'group_channel': group_channel.id,
            'did_meet': False
        }
        
        print(item)
        # table.put_item(Item=item)
        print(5)
        response = table.put_item(Item=item)
        print(response)


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
