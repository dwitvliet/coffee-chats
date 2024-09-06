from typing import Optional


def chats_scheduled_channel_message(n_pairs: int, previous_intros_stats: Optional[dict] = None) -> dict:
    
    message = f'''*{n_pairs}* intros have just been sent out!'''
    
    if previous_intros_stats:
        intros_count = previous_intros_stats['intros_count']
        meetings_count = previous_intros_stats['meetings_count']
        pct_met = round(meetings_count / intros_count * 100)
        message += f'''\n\nLast round, *{meetings_count}* of *{intros_count}* groups met. That's *{pct_met}%* of intros made!'''

        if pct_met < 100:
            message += '\n\nCan you get to *100%*? Schedule your intro for this week and find out!'
        else:
            message += '\n\nKeep up the momentum! Don\'t forget to schedule your intro for this week!'

    return {'text': message}


def ask_if_chat_happened_message(channel: str) -> dict:
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
                    "action_id": "meeting_happened",
                    "value": channel
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": ":x: No"
                    },
                    "action_id": "meeting_did_not_happen",
                    "value": channel
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": ":calendar: Not yet, but scheduled"
                    },
                    "action_id": "meeting_will_happen",
                    "value": channel

                }
            ]
        }
    ], 'text': 'Did you get a chance to connect?'}
