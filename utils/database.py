import boto3
import logging
from datetime import datetime, timedelta
from typing import Optional

class Database(object):
    
    def __init__(self, table_prefix=''):
        self.dynamodb = boto3.resource('dynamodb')
        self.access_tokens = self.dynamodb.Table(f'{table_prefix}access_tokens')
        self.intros = self.dynamodb.Table(f'{table_prefix}intros')
        self.ice_breaker_questions = self.dynamodb.Table(f'{table_prefix}ice_breaker_questions')
        self.paused_users = self.dynamodb.Table(f'{table_prefix}paused_users')
    
    
    def _get_active_intros(self, channel: Optional[str] = None) -> list[dict]:
        query = dict(
            IndexName='is_active-channel-index',
            KeyConditionExpression='is_active = :is_active',
            ExpressionAttributeValues={
                ':is_active': 1,
            }
        )

        if channel:
            query['KeyConditionExpression'] += ' AND channel = :channel'
            query['ExpressionAttributeValues'][':channel'] = channel

        return self.intros.query(**query)['Items']
    

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
            'token': access_token
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
    

    def save_intros(self, channel: str, paired_users: list[list[str]], paired_group_channels: list[str], ice_breaker: dict) -> bool:
        table = self.intros
        current_date = datetime.today().strftime('%Y-%m-%d')
        
        # Set previous intros as inactive.
        active_intro = self._get_active_intros(channel)
        
        if active_intro:
            active_intro_date = active_intro[0]['date']
            
            if active_intro_date == current_date:
                logging.warning(f'Already had a match today for f{channel} - skipping.')
                return False
            
            self._expire_intro(channel, active_intro_date)
        
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
        
        return True


    def expire_old_intros(self) -> None:
        previous_intros = self._get_active_intros()
        for intro in previous_intros:
            if datetime.now() - datetime.fromisoformat(intro['date']) > timedelta(days=16):
                self._expire_intro(intro['channel'], intro['date'])


    def load_recent_intros(self, channel) -> list:
        return self.intros.query(
            KeyConditionExpression='channel = :channel',
            ExpressionAttributeValues={
                ':channel': channel
            },
            ScanIndexForward=False,
            Limit=2
        )['Items']


    def load_active_intros(self) -> list:
        return self._get_active_intros()


    def update_intro_happened(self, channel: str, group_channel: str, happened: bool) -> str:
        previous_intros = self._get_active_intros(channel)
        if not previous_intros:
            return
        
        match = previous_intros[0]
        self.intros.update_item(
            Key={
                'channel': match['channel'],
                'date': match['date']
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
    