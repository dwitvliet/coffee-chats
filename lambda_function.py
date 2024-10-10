import os
import random
from datetime import datetime
import logging
from collections import defaultdict

from slack_bolt import App
from slack_bolt.adapter.aws_lambda import SlackRequestHandler
from slack_bolt.authorization import AuthorizeResult

from utils.messages import chats_scheduled_channel_message, chats_scheduled_dm_message, ask_if_chat_happened_message
from utils.database import Database
from utils.slack_helpers import (
    get_member_channels,
    get_channel_info,
    get_channel_users, 
    get_group_channel, 
    send_message,
    authenticate_new_install,
    respond_to_http_call
)


logging.basicConfig(level=logging.INFO)


# Initialize the Bolt app with your bot token and signing secret
db = Database(table_prefix=os.environ.get("TABLE_PREFIX"))
access_token = db.get_access_token(os.environ.get("SLACK_TEAM_ID"))

def authorize(enterprise_id, team_id, user_id):
    if team_id == os.environ.get("SLACK_TEAM_ID"):
        return AuthorizeResult(
            enterprise_id=enterprise_id,
            team_id=team_id,
            bot_token=db.get_access_token(team_id)
        )
    else:
        raise Exception(f"Unauthorized workspace: {team_id}")

app = App(
    token=access_token,
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET"),
    authorize=authorize,
    process_before_response=True 
)

def split_into_pairs(users: list[str]) -> list[list[str]]:
    random.shuffle(users)
    pairs = []
    for i in range(0, len(users) - 1, 2):
        pairs.append([users[i], users[i+1]])
    if len(users) % 2:
        pairs[-1].append(users[-1])
    return pairs


def _pair_users() -> None:
    print('Pairing users')
    
    ice_breaker_question = None

    for channel in get_member_channels(app.client):
        
        print(f'Pairing users in {channel}')

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
            logging.warning(f'Too few users in {channel}')
            continue
        paired_users = split_into_pairs(users)
        
        # Send intro messages.
        paired_group_channels = []
        for user_pair in paired_users:
            paired_group_channels.append(get_group_channel(app.client, ','.join(user_pair)))

        if ice_breaker_question is None:
            ice_breaker_question = db.get_ice_breaker_question()
            
        intros_were_saved = db.save_intros(channel, paired_users, paired_group_channels, ice_breaker_question)
        if not intros_were_saved:
            continue

        for user_pair, group_channel in zip(paired_users, paired_group_channels):

            schedule_coffee_chat_message = chats_scheduled_dm_message(channel, len(user_pair), ice_breaker_question['question'])
            send_message(app.client, group_channel, schedule_coffee_chat_message)

        send_message(app.client, channel, chats_scheduled_channel_message(len(paired_users), previous_intros_stats))


def _ask_for_engagement() -> None:
    print('Asking for engagement')
    
    db.expire_old_intros()

    active_intros = db.load_active_intros()

    for intro in active_intros:
        channel = intro['channel']
        print(channel)
        
        for group_channel, users in intro['intros'].items(): 

            send_message(
                app.client, 
                group_channel,
                ask_if_chat_happened_message(channel)
            )


@app.command('/coffee_pause')
@app.command('/coffee_resume')
def handle_command(ack, body, logger):
    ack()
    print(f"Command received: {body}")
    
    command = body['command']
    response_url = body['response_url']
    channel = body['channel_id']
    user = body['user_id']

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
        print(response_message)
        respond_to_http_call(response_url, response_message, 'ephemeral')


@app.action('meeting_happened')
@app.action('meeting_did_not_happen')
@app.action('meeting_will_happen')
def handle_command(ack, body, logger):
    ack()
    print(f"Action received: {body}")
    
    action = body['actions'][0]['action_id']
    response_url = body['response_url']
    channel = body['actions'][0]['value']
    group_channel = body['channel']['id']
    user = body['user']['id']

    # Store action.
    happened = action in ('meeting_happened', 'meeting_will_happen')
    update_success = db.update_intro_happened(channel, group_channel, happened)
    
    # Return response.
    response_message = None
    if not update_success:
        response_message = 'Response button expired.'
    elif action == 'meeting_happened':
        response_message = f'<@{user}> said that *you met*. Awesome!'
    elif action == 'meeting_did_not_happen':
        response_message = f'<@{user}> said that *you haven\'t met yet*.'
    elif action == 'meeting_will_happen':
        response_message = f'<@{user}> said that you haven\'t met yet, but *it\'s scheduled to happen*. That\'s great!'

    if response_message:
        respond_to_http_call(response_url, response_message, 'in_channel')
        
        
def _respond_to_action(event: dict, context) -> None:
    
    # Authenticate new app install.
    auth_code = event.get('queryStringParameters', {}).get('code', None)
    if auth_code and event.get('requestContext', {}).get('http', {}).get('method') == 'GET':
        auth_response = authenticate_new_install(auth_code)
        if auth_response['authentication'] == 'Authentification successful':
            db.save_access_token(auth_response['team_id'], auth_response['access_token'])
            return {'statusCode': 200, 'body': auth_response['authentication']}
        else:
            return {'statusCode': 400}
            

    return SlackRequestHandler(app=app).handle(event, context)


def lambda_handler(event, context):
    
    print(event)
    
    if event.get('source') == 'aws.events':
        
        print('Scheduled event')
        
        week = datetime.today().isocalendar().week
        weekday = datetime.today().isocalendar().weekday
        
        # Dev event.
        if event.get('force_pairing'):
            _pair_users()
        elif event.get('force_ask_for_engagement'):
            _ask_for_engagement()
        
        # Scheduled event
        elif (week % 3 == 2 and weekday == 1):
            # Every third Monday.
            _pair_users()

        elif (week % 3 == 1 and weekday == 1):
            # Two weeks after pairing.
            _ask_for_engagement()

        return
        
    # Non-scheduled event.
    return(_respond_to_action(event, context))
