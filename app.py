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





if __name__ == "__main__":

    event = {
        'version': '2.0', 
        'routeKey': '$default', 
        'rawPath': '/', 
        'rawQueryString': '', 
        'headers': {
            'content-length': '2246', 
            'x-amzn-tls-version': 'TLSv1.3', 
            'x-forwarded-proto': 'https', 
            'x-forwarded-port': '443', 
            'x-forwarded-for': '54.158.13.6', 
            'accept': 'application/json,*/*', 
            'x-amzn-tls-cipher-suite': 'TLS_AES_128_GCM_SHA256', 
            'x-amzn-trace-id': 'Root=1-66c8d3ef-41f164411192858916a95794', 
            'host': 'j5pfkapzftf2w3ky7yyiimxfzm0nwqic.lambda-url.us-east-1.on.aws', 
            'content-type': 'application/x-www-form-urlencoded', 
            'x-slack-request-timestamp': '1724437487', 
            'x-slack-signature': 'v0=11fb11cf0bad6cb4c73e08aae32db96b1f157709aa6d18e4292d9fd53dc20da3', 
            'accept-encoding': 'gzip,deflate', 
            'user-agent': 'Slackbot 1.0 (+https://api.slack.com/robots)'
        }, 
        'requestContext': {
            'accountId': 'anonymous', 
            'apiId': 'j5pfkapzftf2w3ky7yyiimxfzm0nwqic', 
            'domainName': 'j5pfkapzftf2w3ky7yyiimxfzm0nwqic.lambda-url.us-east-1.on.aws', 
            'domainPrefix': 'j5pfkapzftf2w3ky7yyiimxfzm0nwqic', 
            'http': {
                'method': 'POST', 
                'path': '/', 
                'protocol': 'HTTP/1.1', 
                'sourceIp': '54.158.13.6', 
                'userAgent': 'Slackbot 1.0 (+https://api.slack.com/robots)'
            }, 
            'requestId': '2c815d74-bde1-47eb-958a-1163758cd955', 
            'routeKey': '$default', 
            'stage': '$default', 
            'time': '23/Aug/2024:18:24:47 +0000', 
            'timeEpoch': 1724437487941
        }, 
        'body': 'cGF5bG9hZD0lN0IlMjJ0eXBlJTIyJTNBJTIyYmxvY2tfYWN0aW9ucyUyMiUyQyUyMnVzZXIlMjIlM0ElN0IlMjJpZCUyMiUzQSUyMlUwNTFVTFRIRlBDJTIyJTJDJTIydXNlcm5hbWUlMjIlM0ElMjJkYW5pZWwud2l0dmxpZXQlMjIlMkMlMjJuYW1lJTIyJTNBJTIyZGFuaWVsLndpdHZsaWV0JTIyJTJDJTIydGVhbV9pZCUyMiUzQSUyMlQwNTI3OUtKSkU1JTIyJTdEJTJDJTIyYXBpX2FwcF9pZCUyMiUzQSUyMkEwN0Y2RjYxQVA0JTIyJTJDJTIydG9rZW4lMjIlM0ElMjJXcjI1clI5UmtZbFF4cWJncVR5RW9PNXIlMjIlMkMlMjJjb250YWluZXIlMjIlM0ElN0IlMjJ0eXBlJTIyJTNBJTIybWVzc2FnZSUyMiUyQyUyMm1lc3NhZ2VfdHMlMjIlM0ElMjIxNzI0NDM3MDE0LjE2NzcwOSUyMiUyQyUyMmNoYW5uZWxfaWQlMjIlM0ElMjJDMDdKNVIySlU5WiUyMiUyQyUyMmlzX2VwaGVtZXJhbCUyMiUzQWZhbHNlJTdEJTJDJTIydHJpZ2dlcl9pZCUyMiUzQSUyMjc2MDc4NTc4NDM2ODcuNTA3NTMyNTYzMDQ4MS4wZTRiMGYwMzQwODkzODNhNDU2MTc5MTA4NzIwNjkyZSUyMiUyQyUyMnRlYW0lMjIlM0ElN0IlMjJpZCUyMiUzQSUyMlQwNTI3OUtKSkU1JTIyJTJDJTIyZG9tYWluJTIyJTNBJTIyZHdpdHZsaWV0ZGV2JTIyJTdEJTJDJTIyZW50ZXJwcmlzZSUyMiUzQW51bGwlMkMlMjJpc19lbnRlcnByaXNlX2luc3RhbGwlMjIlM0FmYWxzZSUyQyUyMmNoYW5uZWwlMjIlM0ElN0IlMjJpZCUyMiUzQSUyMkMwN0o1UjJKVTlaJTIyJTJDJTIybmFtZSUyMiUzQSUyMnByaXZhdGVncm91cCUyMiU3RCUyQyUyMm1lc3NhZ2UlMjIlM0ElN0IlMjJ1c2VyJTIyJTNBJTIyVTA3RjZHMUVFMTAlMjIlMkMlMjJ0eXBlJTIyJTNBJTIybWVzc2FnZSUyMiUyQyUyMnRzJTIyJTNBJTIyMTcyNDQzNzAxNC4xNjc3MDklMjIlMkMlMjJib3RfaWQlMjIlM0ElMjJCMDdGVkExUjY1TiUyMiUyQyUyMmFwcF9pZCUyMiUzQSUyMkEwN0Y2RjYxQVA0JTIyJTJDJTIydGV4dCUyMiUzQSUyMnRlc3QlMjIlMkMlMjJ0ZWFtJTIyJTNBJTIyVDA1Mjc5S0pKRTUlMjIlMkMlMjJibG9ja3MlMjIlM0ElNUIlN0IlMjJ0eXBlJTIyJTNBJTIyc2VjdGlvbiUyMiUyQyUyMmJsb2NrX2lkJTIyJTNBJTIyQlMlNUMlMkZNSyUyMiUyQyUyMnRleHQlMjIlM0ElN0IlMjJ0eXBlJTIyJTNBJTIybXJrZHduJTIyJTJDJTIydGV4dCUyMiUzQSUyMlRlc3QlMjIlMkMlMjJ2ZXJiYXRpbSUyMiUzQWZhbHNlJTdEJTJDJTIyYWNjZXNzb3J5JTIyJTNBJTdCJTIydHlwZSUyMiUzQSUyMmJ1dHRvbiUyMiUyQyUyMmFjdGlvbl9pZCUyMiUzQSUyMmJ1dHRvbl8xX2NsaWNrJTIyJTJDJTIydGV4dCUyMiUzQSU3QiUyMnR5cGUlMjIlM0ElMjJwbGFpbl90ZXh0JTIyJTJDJTIydGV4dCUyMiUzQSUyMkJ1dHRvbisxJTIyJTJDJTIyZW1vamklMjIlM0F0cnVlJTdEJTdEJTdEJTJDJTdCJTIydHlwZSUyMiUzQSUyMnNlY3Rpb24lMjIlMkMlMjJibG9ja19pZCUyMiUzQSUyMll2VzIyJTIyJTJDJTIydGV4dCUyMiUzQSU3QiUyMnR5cGUlMjIlM0ElMjJtcmtkd24lMjIlMkMlMjJ0ZXh0JTIyJTNBJTIyT3IlMjIlMkMlMjJ2ZXJiYXRpbSUyMiUzQWZhbHNlJTdEJTJDJTIyYWNjZXNzb3J5JTIyJTNBJTdCJTIydHlwZSUyMiUzQSUyMmJ1dHRvbiUyMiUyQyUyMmFjdGlvbl9pZCUyMiUzQSUyMmJ1dHRvbl8yX2NsaWNrJTIyJTJDJTIydGV4dCUyMiUzQSU3QiUyMnR5cGUlMjIlM0ElMjJwbGFpbl90ZXh0JTIyJTJDJTIydGV4dCUyMiUzQSUyMkJ1dHRvbisyJTIyJTJDJTIyZW1vamklMjIlM0F0cnVlJTdEJTdEJTdEJTVEJTdEJTJDJTIyc3RhdGUlMjIlM0ElN0IlMjJ2YWx1ZXMlMjIlM0ElN0IlN0QlN0QlMkMlMjJyZXNwb25zZV91cmwlMjIlM0ElMjJodHRwcyUzQSU1QyUyRiU1QyUyRmhvb2tzLnNsYWNrLmNvbSU1QyUyRmFjdGlvbnMlNUMlMkZUMDUyNzlLSkpFNSU1QyUyRjc2MjQ5MDAxMTQyNDQlNUMlMkZsWnlVYk9DVFAzbkJDVGJXSmVqeWxTb0klMjIlMkMlMjJhY3Rpb25zJTIyJTNBJTVCJTdCJTIyYWN0aW9uX2lkJTIyJTNBJTIyYnV0dG9uXzFfY2xpY2slMjIlMkMlMjJibG9ja19pZCUyMiUzQSUyMkJTJTVDJTJGTUslMjIlMkMlMjJ0ZXh0JTIyJTNBJTdCJTIydHlwZSUyMiUzQSUyMnBsYWluX3RleHQlMjIlMkMlMjJ0ZXh0JTIyJTNBJTIyQnV0dG9uKzElMjIlMkMlMjJlbW9qaSUyMiUzQXRydWUlN0QlMkMlMjJ0eXBlJTIyJTNBJTIyYnV0dG9uJTIyJTJDJTIyYWN0aW9uX3RzJTIyJTNBJTIyMTcyNDQzNzQ4Ny44ODY3NzQlMjIlN0QlNUQlN0Q=', 
        'isBase64Encoded': True
    }

    # event = {'source': 'aws.events', 'force_pairing': True}
    # event = {'source': 'aws.events', 'force_ask_for_engagement': True}

    print(lambda_handler(event, None))
