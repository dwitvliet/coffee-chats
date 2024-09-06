import os
import json
import base64
import hashlib
import hmac
import time
import urllib.request
import urllib.parse
import logging
from typing import Optional

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


def process_http_call(event: dict) -> dict:

    # Check that request was sent from the slack application.
    if 'headers' not in event or 'body' not in event:
        return

    if event.get('isBase64Encoded'):
        body = base64.b64decode(event['body']).decode('utf-8')
    else:
        body = event['body']

    slack_signature = event['headers'].get('x-slack-signature', '')
    slack_timestamp = event['headers'].get('x-slack-request-timestamp', '')
    slack_signing_secret = os.environ['SLACK_SIGNING_SECRET']

    sig_basestring = f"v0:{slack_timestamp}:{body}"
    my_signature = "v0=" + hmac.new(
        slack_signing_secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(my_signature, slack_signature):
        return
    
    parsed_body = urllib.parse.parse_qs(body)
    
    if 'payload' in parsed_body:
        # Actions like button clicks.
        return json.loads(urllib.parse.parse_qs(body)['payload'][0])
        
    return parsed_body


def respond_to_http_call(response_url: str, message: str, response_type: str) -> None:
    data = json.dumps({
        'response_type': response_type,
        'text': message,
    }).encode('utf-8')
    req = urllib.request.Request(response_url, data=data, headers={'Content-Type': 'application/json'})
    urllib.request.urlopen(req)
    