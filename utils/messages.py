
def schedule_coffee_chat_message(users, channel) -> dict:
    number = 'two' if len(users) == 2 else 'three'
    return {'text': f'''

Hi, you {number} have been paired this week in <#{channel.id}>! Please set up a calendar invite to have a fun chat!

'''}


def chats_scheduled_channel_message(n_pairs: int) -> dict:

    return {'text': f'''

*{n_pairs}* intros have just been sent out!

Last round, *6* of *12* groups met. That's *50%* of intros made!

Can you get to *100%*? Schedule your intro for this week and find out!

'''}


def ask_if_chat_happened_message() -> dict:
    return {'blocks': [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Checking in! A new round of intros will go out on Monday.\n*Did you get a chance to connect?*"
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": ":white_check_mark: Yes"
                    },
                    "action_id": "meeting_happened"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": ":x: No"
                    },
                    "action_id": "meeting_did_not_happen"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": ":calendar: Not yet, but scheduled"
                    },
                    "action_id": "meeting_will_happen"

                }
            ]
        }
    ], 'text': 'Did you get a chance to connect?'}
