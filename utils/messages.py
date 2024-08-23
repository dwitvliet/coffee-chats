
def schedule_coffee_chat_message(users, channel) -> dict:
    number = 'two' if len(users) == 2 else 'three'
    return {'text': f'''

Hi! You {number} have been paired this week in <#{channel.id}>! Please set up a calendar invite to have a fun chat!

'''}


def chats_scheduled_channel_message(n_pairs: int) -> dict:

    return {'text': f'''

Hi, {n_pairs} intros have just been sent out! Don't forget to set up calendar invites to have a fun chat!

'''}


def ask_if_chat_happened_message() -> dict:
    return {'blocks': [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": 'Test'
            },
            "accessory": {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Button 1"
                },
                "action_id": "button_1_click"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Or"
            },
            "accessory": {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Button 2"
                },
                "action_id": "button_2_click"
            }
        }
    ], 'text': 'test'}