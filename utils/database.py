import boto3
import logging
from datetime import date, datetime, timedelta


class Database(object):
    
    def __init__(self, table_prefix=''):
        self.dynamodb = boto3.resource('dynamodb')
        self.access_tokens = self.dynamodb.Table(f'{table_prefix}access_tokens')
        self.channels = self.dynamodb.Table(f'{table_prefix}channels')
        self.intros = self.dynamodb.Table(f'{table_prefix}intros')
        self.ice_breaker_questions = self.dynamodb.Table(f'{table_prefix}ice_breaker_questions')
        self.paused_users = self.dynamodb.Table(f'{table_prefix}paused_users')
    
    
    def get_active_intro(self, channel: str) -> dict:
        intros = self.intros.query(
            IndexName='is_active-channel-index',
            KeyConditionExpression='is_active = :is_active AND channel = :channel',
            ExpressionAttributeValues={
                ':is_active': 1,
                ':channel': channel,
            }
        )['Items']
        
        if intros:
            return intros[0]
            
        return None

    def _expire_intro(self, channel: str, date: str) -> None:
        self.intros.update_item(
            Key={
                'channel': channel,
                'date': date
            },
            UpdateExpression='SET is_active = :is_active',
            ExpressionAttributeValues={':is_active': 0}
        )
        
    def save_access_token(self, team: str, access_token: str):
        self.access_tokens.put_item(Item={
            'team': team,
            'token': access_token,
            'added_dt': datetime.now().date().isoformat()
        }) 
        
    def get_access_token(self, team: str) -> str:
        items = self.access_tokens.query(
            KeyConditionExpression='team = :team',
            ExpressionAttributeValues={
                ':team': team
            }
        )['Items']
        if items:
            return items[0]['token']
            

    
    def get_channel_settings(self, channel: str) -> dict:
        channel_metadata =  self.channels.query(
            KeyConditionExpression='channel = :channel',
            ExpressionAttributeValues={
                ':channel': channel
            }
        )['Items']
        
        if channel_metadata:
            return channel_metadata[0]
        
        return None
        
        
    def get_or_update_channel_settings(self, channel: str, new_add: bool = False, frequency: str = None, last_coffee_chat_dt: str = None, last_engagement_asked_dt: str = None) -> dict:

        if new_add:
            channel_metadata = None
        else:
            channel_metadata = self.get_channel_settings(channel)
        
        if channel_metadata and not frequency and not last_coffee_chat_dt and not last_engagement_asked_dt:
            return channel_metadata
        
        if not channel_metadata:
            channel_metadata = {
                'channel': channel, 
                'added_dt': datetime.today().strftime('%Y-%m-%d'),
                'frequency': 'triweekly',
                'is_active': True,
                'last_coffee_chat_dt': None,
                'last_engagement_asked_dt': None
            }
        
        if frequency:
            channel_metadata['frequency'] = frequency
            
        if last_coffee_chat_dt:
            channel_metadata['last_coffee_chat_dt'] = last_coffee_chat_dt
            
        if last_engagement_asked_dt:
            channel_metadata['last_engagement_asked_dt'] = last_engagement_asked_dt
        
        self.channels.put_item(Item=channel_metadata) 
        
        return channel_metadata
        
        
    def get_next_pairing_date(self, channel: str) -> date:
        channel_metadata = self.get_or_update_channel_settings(channel)
        last_coffee_chat_dt = channel_metadata['last_coffee_chat_dt']
        channel_added_dt = channel_metadata['added_dt']
        pairing_frequency = channel_metadata['frequency']
        
        next_pairing_date = None
        if not channel_metadata['is_active']:
            next_pairing_date = date(9999, 12, 31)
        elif last_coffee_chat_dt and pairing_frequency == 'biweekly':
            next_pairing_date = datetime.fromisoformat(last_coffee_chat_dt).date() + timedelta(days=14)
        elif last_coffee_chat_dt and pairing_frequency == 'triweekly':
            next_pairing_date = datetime.fromisoformat(last_coffee_chat_dt).date() + timedelta(days=21)
        elif last_coffee_chat_dt:
            raise Exception('Unexpected frequency:', pairing_frequency)
        else:
            next_pairing_date = max(
                datetime.fromisoformat(channel_added_dt).date() + timedelta(days=7),
                datetime.now().date() + timedelta(days=6)
            )
        
        # Set to Monday.
        next_pairing_date = next_pairing_date - timedelta(days=next_pairing_date.weekday())
            
        return next_pairing_date
    
    def get_next_engagement_survey_date(self, channel: str) -> date:
        next_pairing_date = self.get_next_pairing_date(channel)
        next_engagement_survey_date = next_pairing_date - timedelta(7)
        last_engagement_survey_date = datetime.fromisoformat(self.get_or_update_channel_settings(channel)['last_engagement_asked_dt'] or '9999-12-31').date()
        if next_engagement_survey_date == last_engagement_survey_date:
            print('Already did survey for this round')
            next_engagement_survey_date = date(9999, 12, 31)
        return next_engagement_survey_date
        
            
    def get_ice_breaker_question(self) -> dict:

        items = self.ice_breaker_questions.query(
            IndexName='is_active-times_used-index',
            KeyConditionExpression='is_active = :is_active',
            ExpressionAttributeValues={
                ':is_active': 1
            },
            Limit=1
        )['Items']
        
        if items:
            
            question = items[0]
            
            self.ice_breaker_questions.update_item(
                Key={'question_id': question['question_id']},
                UpdateExpression='SET times_used = :times_used',
                ExpressionAttributeValues={':times_used': question['times_used'] + 1}
            )
            
            return question
            
        return {'question_id': -1, 'question': ''}
    

    def save_intros(self, channel: str, paired_users: list[list[str]], paired_group_channels: list[str], ice_breaker: dict):
        table = self.intros
        current_date = datetime.today().date().isoformat()
        
        # Set previous intros as inactive.
        active_intro = self.get_active_intro(channel)
        
        if active_intro:
            active_intro_date = active_intro['date']
            self._expire_intro(channel, active_intro_date)
            
        self.get_or_update_channel_settings(channel, last_coffee_chat_dt=current_date)
        
        # Insert new intro record.
        table.put_item(Item={
            'channel': channel,
            'date': current_date,
            'is_active': 1,
            'ice_break_question_id': ice_breaker['question_id'],
            'intros': {
                group_channel: {
                    'users': users, 
                    'happened': False
                }
                for users, group_channel in zip(paired_users, paired_group_channels)
            }
        }) 

    def load_recent_intros(self, channel) -> list:
        return self.intros.query(
            KeyConditionExpression='channel = :channel',
            ExpressionAttributeValues={
                ':channel': channel
            },
            ScanIndexForward=False,
            Limit=2
        )['Items']



    def update_intro_happened(self, channel: str, group_channel: str, happened: bool) -> str:
        previous_intro = self.get_active_intro(channel)
        if not previous_intro:
            return
        
        self.intros.update_item(
            Key={
                'channel': previous_intro['channel'],
                'date': previous_intro['date']
            },
            UpdateExpression='SET intros.#group_channel.happened = :happened',
            ExpressionAttributeNames={
                '#group_channel': group_channel,
            },
            ExpressionAttributeValues={
                ':happened': happened
            }
        )
        
        return True


    def pause_intros(self, channel: str, user: str):
        self.paused_users.put_item(Item={
            'channel': channel,
            'user': user
        }) 
    
    def resume_intros(self, channel: str, user: str):
        self.paused_users.delete_item(Key={
            'channel': channel,
            'user': user
        }) 
    
    def get_paused_intros(self, channel: str):
        items = self.paused_users.query(
            KeyConditionExpression='channel = :channel',
            ExpressionAttributeValues={
                ':channel': channel
            }
        )['Items']

        return [i['user'] for i in items]
    