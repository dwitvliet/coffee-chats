import os
import json
import base64
import hashlib
import hmac
import urllib.request
import urllib.parse
import logging

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


def get_member_channels(client: WebClient) -> list[str]:
    try:
        response = client.users_conversations(types="public_channel,private_channel", limit=999, exclude_archived=True)
        return [c['id'] for c in response.get('channels', [])]

    except SlackApiError as e:
        logging.error(f"Error fetching channels: {e.response['error']}")
        return []



def get_channel_info(client: WebClient, channel: str) -> dict:
    try:
        response = client.conversations_info(channel=channel)
        return response.get('channel', {})

    except SlackApiError as e:
        logging.info(f"Error fetching channel info: {e.response['error']}")
        return {}
    

def get_user_info(client: WebClient, user: str) -> dict:
    try:
        response = client.users_info(user=user)
        return response.get('user', {})

    except SlackApiError as e:
        logging.error(f"Error fetching member: {e.response['error']}")
        return {}


def get_channel_users(client: WebClient, channel: str) -> list[str]:
    try:
        response = client.conversations_members(channel=channel)
        users = response.get('members', [])
    
    except SlackApiError as e:
        logging.error(f"Error fetching members: {e.response['error']}")
        users = []
        
    users_excl_bots = []
    for user in users:
        user_info = get_user_info(client, user)
        if not user_info or user_info.get('is_bot'):
            continue
        users_excl_bots.append(user)

    return users_excl_bots


def get_group_channel(client: WebClient, users: list[str]) -> str:
    try:
        response = client.conversations_open(users=users)
        return response['channel']['id']

    except SlackApiError as e:
        logging.error(f"Error sending message: {e.response['error']}")
        return
    

def send_message(client: WebClient, channel: str, message: dict) -> None:
    try:
        client.chat_postMessage(channel=channel, **message)

    except SlackApiError as e:
        logging.error(f"Error sending message: {e.response['error']}")


def authenticate_new_install(code):
    
    url = 'https://slack.com/api/oauth.v2.access'
    params = {
        'client_id': os.environ.get("SLACK_CLIENT_ID"),
        'client_secret': os.environ.get("SLACK_CLIENT_SECRET"),
        'code': code,
        'redirect_uri': os.environ.get("FUNCTION_URL")
    }

    data = urllib.parse.urlencode(params).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='POST')
    
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode('utf-8'))
        
    if not result.get('ok', False):
        return {'authentication': 'Authentification failed'}

    return {
        'authentication': 'Authentification successful',
        'team_id': result['team']['id'],
        'access_token': result['access_token']
    }


def respond_to_http_call(response_url: str, message: str, response_type: str) -> None:
    data = json.dumps({
        'response_type': response_type,
        'text': message,
    }).encode('utf-8')
    req = urllib.request.Request(response_url, data=data, headers={'Content-Type': 'application/json'})
    urllib.request.urlopen(req)
    