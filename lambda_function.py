import os
import random
from datetime import datetime
import logging
from collections import defaultdict

from slack_bolt import App
from slack_sdk import WebClient

from utils.messages import chats_scheduled_channel_message, ask_if_chat_happened_message
from utils.database import Database
from utils.slack_helpers import (
    get_member_channels,
    get_channel_info,
    get_channel_users, 
    get_group_channel, 
    send_message,
    process_http_call,
    respond_to_http_call
)


# Initialize the Bolt app with your bot token and signing secret
app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)
db = Database()

def split_into_pairs(users: list[str]) -> list[list[str]]:
    random.shuffle(users)
    pairs = []
    for i in range(0, len(users) - 1, 2):
        pairs.append([users[i], users[i+1]])
    if len(users) % 2:
        pairs[-1].append(users[-1])
    return pairs


def _pair_users() -> None:

    for channel in get_member_channels(app.client):
        logging.info(f'Pairing users in {channel}')

        # Get users to pair.
        users = get_channel_users(app.client, channel)
        paused_users = db.get_paused_intros(channel)
        users = [u for u in users if u not in paused_users]

        # Calculate stats for previous intro.
        recent_intros = db.load_recent_intros(channel)
        if recent_intros and recent_intros[0]['is_active']:
            previous_intros_stats = {
                'intros_count': len(recent_intros[0]['intros']),
                'meetings_count': sum([m['happened'] for m in recent_intros[0]['intros'].values()])
            }
        else:
            previous_intros_stats = None
            
        # Determine which users need to be skipped due to inactivity.
        missed_intros = defaultdict(int)
        for round in recent_intros:
            for intro in round['intros'].values():
                if intro['happened']:
                    continue
                for user in intro['users']:
                    missed_intros[user] += 1
        
        skipped_users = []
        for user in users:
            if missed_intros[user] >= 2:
                db.pause_intros(channel, user)
                send_message(app.client, user, {'text': f'Intros have been paused for you in <#{channel}> due to inactivity (missing your last two intros). To be included in the next round of intros, run `/coffee_resume` in the channel at any time.'})
                skipped_users.append(user)
                
        users = [u for u in users if u not in skipped_users]
                
        # Randomize users.
        if len(users) < 2:
            logging.warning('Too few users')
            continue
        paired_users = split_into_pairs(users)
        
        # Send intro messages.
        paired_group_channels = []
        for user_pair in paired_users:
            paired_group_channels.append(get_group_channel(app.client, ','.join(user_pair)))

        intros_were_saved = db.save_intros(channel, paired_users, paired_group_channels)
        if not intros_were_saved:
            continue

        for user_pair, group_channel in zip(paired_users, paired_group_channels):
            user_pair_count = 'two' if len(user_pair) == 2 else 'three'
            schedule_coffee_chat_message = {
                'text': f'Hi, you {user_pair_count} have been paired this week in <#{channel}>! Please set up a calendar invite to have a fun chat!'
            }
            send_message(app.client, group_channel, schedule_coffee_chat_message)

        send_message(app.client, channel, chats_scheduled_channel_message(len(paired_users), previous_intros_stats))


def _ask_for_engagement() -> None:
    
    db.expire_old_intros()

    active_intros = db.load_active_intros()

    for intro in active_intros:
        
        channel = intro['channel']
        
        for group_channel, users in intro['intros'].items(): 

            send_message(
                app.client, 
                group_channel,
                ask_if_chat_happened_message(channel)
            )


def _respond_to_action(event: dict) -> None:
    
    event_body = process_http_call(event)
    if not event_body:
        return {'statusCode': 400}
    
    # Button clicks.
    if event_body.get('type') == 'block_actions':
        action = event_body['actions'][0]['action_id']
        response_url = event_body['response_url']
        
        channel = event_body['actions'][0]['value']
        group_channel = event_body['channel']['id']
        user = event_body['user']['id']
    
        # Store action.
        happened = action in ('meeting_happened', 'meeting_will_happen')
        update_success = db.update_intro_happened(channel, group_channel, happened)
        
        # Return response.
        response_message = None
        if not update_success:
            response_message = f'Response button expired.'
        elif action == 'meeting_happened':
            response_message = f'<@{user}> said that *you met*. Awesome!'
        elif action == 'meeting_did_not_happen':
            response_message = f'<@{user}> said that *you haven\'t met yet*.'
        elif action == 'meeting_will_happen':
            response_message = f'<@{user}> said that you haven\'t met yet, but *it\'s scheduled to happen*. That\'s great!'

        if response_message:
            respond_to_http_call(response_url, response_message, 'in_channel')

        return {'statusCode': 200}
        
    # Slash commands.
    if 'command' in event_body:
        command = event_body['command'][0]
        response_url = event_body['response_url'][0]
        
        channel = event_body['channel_id'][0]
        user = event_body['user_id'][0]
        
        channel_info = get_channel_info(app.client, channel)
        
        response_message = None
        if not channel_info.get('is_member'):
            response_message = f'{command} only works in channels that I have been added to!'
        elif command == '/coffee_pause':
            db.pause_intros(channel, user)
            response_message = f'Intros have been paused for you in <#{channel}>. To be included in intros again, you can run `/coffee_resume` here at any time.'
        elif command == '/coffee_resume':
            db.resume_intros(channel, user)
            response_message = f'Intros have been resumed for you in <#{channel}>. You will be included in the next round of intros!'
                
        
        if response_message:
            respond_to_http_call(response_url, response_message, 'ephemeral')
        
        return {'statusCode': 200}
        
        

    return {'statusCode': 400}

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
