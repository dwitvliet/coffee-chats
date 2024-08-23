import os
import random

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

        # send_channel_message(app.client, channel, chats_scheduled_channel_message(len(paired_users)))


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

@app.action("button_1_click")
@app.action("button_2_click")
def handle_button_click(ack, body, client):
    print(1)
    ack()
    client.chat_update(
        channel=body["channel"]["id"],
        ts=body["message"]["ts"],
        text="You clicked a button!",
        blocks=[]
    )
    # Store the button click for later use
    # store_button_click(body["user"]["id"], body["actions"][0]["action_id"])

if __name__ == "__main__":


    # _pair_users()

    _ask_for_engagement()

    # app.start(port=int(os.environ.get("PORT", 3000)))
