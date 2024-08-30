import os
import random
import base64
import json
import hashlib
import hmac
import time
from datetime import datetime
import urllib.parse
import urllib.request

from slack_bolt import App
from slack_sdk import WebClient

from utils.messages import schedule_coffee_chat_message, chats_scheduled_channel_message, ask_if_chat_happened_message
from utils.models import User, Channel
from utils.slack_helpers import get_member_channels, get_channel_users, send_group_message, send_channel_message
from utils.database import save_matches, load_matches


# Initialize the Bolt app with your bot token and signing secret
app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

def split_into_pairs(users: list[User]) -> list[list[User]]:
    random.shuffle(users)
    pairs = []
    for i in range(0, len(users) - 1, 2):
        pairs.append([users[i], users[i+1]])
    if not len(pairs) % 2:
        pairs[-1].append(users[-1])
    return pairs


def _pair_users() -> None:
    # Get users to pair.
    for channel in get_member_channels(app.client):
        print(channel)

        users = get_channel_users(app.client, channel)
        if len(users) < 2:
            print('Too few users')
            continue

        paired_users = split_into_pairs(users)
        print(paired_users)

        paired_group_channels = []
        for user_pair in paired_users:
            group_channel = send_group_message(
                app.client, 
                ','.join([u.id for u in user_pair]), 
                schedule_coffee_chat_message(user_pair, channel)
            )
            paired_group_channels.append(group_channel)

        save_matches(channel, paired_users, paired_group_channels)

        send_channel_message(app.client, channel, chats_scheduled_channel_message(len(paired_users)))


def _ask_for_engagement() -> None:

    matches = load_matches()

    for channel_id, channel_matches in matches.items():
        for channel_match in channel_matches:
            users = channel_match['users']
            group_channel = channel_match['group_channel']

            print(users, group_channel)

            group_channel = send_group_message(
                app.client, 
                ','.join([u.id for u in users]), 
                ask_if_chat_happened_message(),
                group_channel
            )


def _respond_to_action(event: dict) -> None:

    # Check that request was sent from the slack application.
    if 'headers' not in event or 'body' not in event:
        return {'statusCode': 403}

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
        return {'statusCode': 400}

    # Get message.
    payload = json.loads(urllib.parse.parse_qs(body)['payload'][0])
    action = payload['actions'][0]['action_id']
    response_url = payload['response_url']
    channel_id = payload['channel']['id']
    user_id = payload['user']['id']

    # Store action.


    # Return response.
    message = {
        "response_type": "in_channel", 
        "text": f"<@{user_id}> clicked button {action}!" #TODO: make into messsages.py, e.g. "User said that you met"
    }

    data = json.dumps(message).encode('utf-8')
    req = urllib.request.Request(response_url, data=data, headers={'Content-Type': 'application/json'})
    urllib.request.urlopen(req)

    return {'statusCode': 200}


def lambda_handler(event, context):

    if event.get('source') == 'aws.events':
        # Scheduled event
        week = datetime.today().isocalendar().week
        weekday = datetime.today().isocalendar().weekday

        if (week % 2 and weekday == 1) or event.get('force_pairing'):
            # Monday.
            _pair_users()

        if (not week % 2 and weekday == 3) or event.get('force_ask_for_engagement'):
            # Wednesday.
            _ask_for_engagement()

        return
        
    # Nons-scheduled event.
    return(_respond_to_action(event))

