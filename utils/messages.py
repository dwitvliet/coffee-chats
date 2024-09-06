from typing import Optional


def schedule_coffee_chat_message(users, channel) -> dict:
    number = 'two' if len(users) == 2 else 'three'
    return {'text': f'''Hi, you {number} have been paired this week in <#{channel}>! Please set up a calendar invite to have a fun chat!'''}


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


def message_response_to_action(user: str, action: str) -> dict:
    
    message = None
    
    if action == 'meeting_happened':
        message = f'<@{user}> said that *you met*. Awesome!'
        
    elif action == 'meeting_did_not_happen':
        message = f'<@{user}> said that *you haven\'t met yet*.'
        
    elif action == 'meeting_will_happen':
        message = f'<@{user}> said that you haven\'t met yet, but *it\'s scheduled to happen*. That\'s great!'
        
    elif action == 'expired':
        message = f'Response button expired.'
        
    if not message:
        return None
    
    return {
        'response_type': 'in_channel', 
        'text': message
    }
