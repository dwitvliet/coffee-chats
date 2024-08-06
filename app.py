import os
from slack_bolt import App
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Initialize the Bolt app with your bot token and signing secret
app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

# Function to get channel members
def get_channel_members(channel_id: str):
    try:
        response = app.client.conversations_members(channel=channel_id)
        members = response['members']
        return members
    except SlackApiError as e:
        print(f"Error fetching members: {e.response['error']}")
        return []

# Function to list channels
def list_channels():
    try:
        response = app.client.users_conversations(types="public_channel,private_channel", limit=999, exclude_archived=True)
        channels = response['channels']
        return channels
    except SlackApiError as e:
        print(f"Error fetching channels: {e.response['error']}")
        return []

def get_user_info():
    try:

        pass #users.info

    except SlackApiError as e:
        print(f"Error fetching member: {e.response['error']}")
        return []

# Example usage: Print all channels and members of the first channel
def print_channels_and_members():
    channels = list_channels()
    print("Channels the app is a member of:")
    for channel in channels:
        print(f"{channel['name']} (ID: {channel['id']})")
        
        members = get_channel_members(channel['id'])
        print('Members:')
        for member in members:
            print()



# Start the app
if __name__ == "__main__":
    print_channels_and_members()  # Print channels and members when the app starts
    # app.start(port=int(os.environ.get("PORT", 3000)))
