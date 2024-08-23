from typing import Optional

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


def send_group_message(client: WebClient, user_ids: list[str], message: dict, group_channel: Optional[Channel] = None) -> Channel:
    try:
        if group_channel is None:
            response = client.conversations_open(users=user_ids)
            group_channel = Channel(response['channel'])

        client.chat_postMessage(channel=group_channel.id, **message)

        return group_channel

    except SlackApiError as e:
        print(f"Error sending message: {e.response['error']}")


def send_channel_message(client: WebClient, channel: Channel, message: dict) -> None:
    try:
        client.chat_postMessage(channel=channel.id, **message)

    except SlackApiError as e:
        print(f"Error sending message: {e.response['error']}")
