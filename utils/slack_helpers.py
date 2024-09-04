from typing import Optional
import json
import urllib.request

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from utils.models import User, Channel


def get_member_channels(client: WebClient) -> list[Channel]:
    try:
        response = client.users_conversations(types="public_channel,private_channel", limit=999, exclude_archived=True)
        channels_raw = response.get('channels', [])

    except SlackApiError as e:
        print(f"Error fetching channels: {e.response['error']}")
        channels_raw = []

    return [Channel(c) for c in channels_raw if c['is_channel']]


def get_user_info(client: WebClient, user_id: str) -> dict:
    try:
        response = client.users_info(user=user_id)
        user_info = response.get('user', {})

    except SlackApiError as e:
        print(f"Error fetching member: {e.response['error']}")
        user_info = {}

    return user_info


def get_channel_users(client: WebClient, channel: Channel) -> list[User]:
    try:
        response = client.conversations_members(channel=channel.id)
        users_ids = response.get('members', [])
    
    except SlackApiError as e:
        print(f"Error fetching members: {e.response['error']}")
        users_ids = []
        
    users = []
    for user_id in users_ids:
        user_info = get_user_info(client, user_id)
        if not user_info or user_info.get('is_bot'):
            continue
        users.append(User(user_info))

    return users


def get_group_channel(client: WebClient, user_ids: list[str]) -> Channel:
    try:
        response = client.conversations_open(users=user_ids)
        return Channel(response['channel'])

    except SlackApiError as e:
        print(f"Error sending message: {e.response['error']}")
    

def send_channel_message(client: WebClient, channel: Channel, message: dict) -> None:
    try:
        client.chat_postMessage(channel=channel.id, **message)

    except SlackApiError as e:
        print(f"Error sending message: {e.response['error']}")


def respond_to_action(response_url: str, message: dict) -> None:
    data = json.dumps(message).encode('utf-8')
    req = urllib.request.Request(response_url, data=data, headers={'Content-Type': 'application/json'})
    urllib.request.urlopen(req)
    