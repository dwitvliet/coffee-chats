import os
import random
import base64
import json
import hashlib
import hmac
import time
from datetime import datetime
import urllib.parse
import logging

from slack_bolt import App
from slack_sdk import WebClient

from utils.models import User, Channel
from utils.messages import (
    schedule_coffee_chat_message, 
    chats_scheduled_channel_message, 
    ask_if_chat_happened_message, 
    message_response_to_action
)
from utils.slack_helpers import (
    get_member_channels, 
    get_channel_users, 
    get_group_channel, 
    send_channel_message,
    respond_to_action
)
from utils.database import (
    save_matches, 
    expire_old_matches, 
    load_matches,
    update_match_did_meet
)


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
    if len(users) % 2:
        pairs[-1].append(users[-1])
    return pairs


def _pair_users() -> None:

    # Get users to pair.
    for channel in get_member_channels(app.client):
        logging.info(f'Pairing users in {channel}')

        users = get_channel_users(app.client, channel)
        if len(users) < 2:
            logging.warning('Too few users')
            continue

        paired_users = split_into_pairs(users)
        
        paired_group_channels = []
        for user_pair in paired_users:
            paired_group_channels.append(get_group_channel(app.client, ','.join([u.id for u in user_pair])))


        previous_intros_stats = None
        previous_matches = load_matches(channel)
        if previous_matches:
            previous_intros_stats = {
                'intros_count': len(previous_matches[0]['intros']),
                'meetings_count': sum([m['did_meet'] for m in previous_matches[0]['intros'].values()])
            }
            
        matches_was_saved = save_matches(channel, paired_users, paired_group_channels)
        if not matches_was_saved:
            continue

        for user_pair, group_channel in zip(paired_users, paired_group_channels):
            send_channel_message(app.client, group_channel, schedule_coffee_chat_message(user_pair, channel))

        send_channel_message(app.client, channel, chats_scheduled_channel_message(len(paired_users), previous_intros_stats))


def _ask_for_engagement() -> None:
    
    expire_old_matches()

    matches = load_matches()

    for match in matches:
        
        channel = Channel({'id': match['channel']})
        
        for group_channel_id, users in match['intros'].items(): 

            group_channel = Channel({'id': group_channel_id})
            
            send_channel_message(
                app.client, 
                group_channel,
                ask_if_chat_happened_message(channel)
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
    
    channel = Channel({'id': payload['actions'][0]['value']})
    group_channel = Channel({'id': payload['channel']['id']})
    user = User({'id': payload['user']['id']})

    # Store action.
    did_meet = action in ('meeting_happened', 'meeting_will_happen')
    update_success = update_match_did_meet(channel, group_channel, did_meet)
    if not update_success:
        action = 'expired'

    # Return response.
    response_message = message_response_to_action(user, action)
    if response_message:
        respond_to_action(response_url, response_message)

    return {'statusCode': 200}


def lambda_handler(event, context):

    if event.get('source') == 'aws.events':
        # Scheduled event
        week = datetime.today().isocalendar().week
        weekday = datetime.today().isocalendar().weekday

        if (week % 2 and weekday == 1) or event.get('force_pairing'):
            # Monday.
            _pair_users()

        elif (not week % 2 and weekday == 3) or event.get('force_ask_for_engagement'):
            # Wednesday.
            _ask_for_engagement()

        return
        
    # Non-scheduled event.
    return(_respond_to_action(event))

