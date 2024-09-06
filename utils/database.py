import json
import os
import boto3
import logging
from datetime import datetime, timedelta
from typing import Optional

class Database(object):
    
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.intros = self.dynamodb.Table('intros')
        self.paused_users = self.dynamodb.Table('paused_users')
        

    def save_intros(self, channel: str, paired_users: list[list[str]], paired_group_channels: list[str]) -> bool:
        
        table = self.intros
        current_date = datetime.today().strftime('%Y-%m-%d')
        
        # Create record to insert.
        record_to_insert = {
            'channel': channel,
            'date': current_date,
            'is_active': 1,
            'intros': {
                group_channel: {
                    'users': users, 
                    'happened': False
                }
                for users, group_channel in zip(paired_users, paired_group_channels)
            }
        }
        
        # Set previous intros as inactive.
        active_intro = table.query(
            IndexName='is_active-channel-index',
            KeyConditionExpression='is_active = :is_active AND channel = :channel',
            ExpressionAttributeValues={
                ':is_active': 1,
                ':channel': channel
                
            }
        )['Items']
        
        
        if active_intro:
            
            active_intro_date = active_intro[0]['date']
            
            if active_intro_date == current_date:
                logging.warning(f'Already had a match today for f{channel} - skipping.')
                return False
    
            table.update_item(
                Key={
                    'channel': channel,
                    'date': active_intro_date
                },
                UpdateExpression='SET is_active = :is_active',
                ExpressionAttributeValues={':is_active': 0}
            )
        
        
        table.put_item(Item=record_to_insert) 
        
        return True


    def expire_old_intros(self) -> None:
        table = self.intros
        
        previous_intros = table.query(
            IndexName='is_active-channel-index',
            KeyConditionExpression='is_active = :is_active',
            ExpressionAttributeValues={
                ':is_active': 1,
            }
        )['Items']
        
        for match in previous_intros:
            expire_match = False
            if datetime.now() - datetime.fromisoformat(match['date']) > timedelta(days=14):
                expire_match = True
            elif any([m['happened'] for m in match['intros'].values()]):
                expire_match = True
                
            if expire_match:
                
                table.update_item(
                    Key={
                        'channel': match['channel'],
                        'date': match['date']
                    },
                    UpdateExpression='SET is_active = :is_active',
                    ExpressionAttributeValues={':is_active': 0}
                )


    def load_recent_intros(self, channel: Optional[str] = None) -> list:
        table = self.intros
    
        return table.query(
            KeyConditionExpression='channel = :channel',
            ExpressionAttributeValues={
                ':channel': channel
            },
            ScanIndexForward=False,
            Limit=2
        )['Items']


    def load_active_intros(self) -> list:
        table = self.intros
    
        return table.query(
            IndexName='is_active-channel-index',
            KeyConditionExpression='is_active = :is_active',
            ExpressionAttributeValues={
                ':is_active': 1,
            }
        )['Items']


    def update_intro_happened(self, channel: str, group_channel: str, happened: bool) -> str:
        table = self.intros

        previous_intros = table.query(
            IndexName='is_active-channel-index',
            KeyConditionExpression='is_active = :is_active AND channel = :channel',
            ExpressionAttributeValues={
                ':is_active': 1,
                ':channel': channel
            }
        )['Items']
        
        if not previous_intros:
            return
        
        match = previous_intros[0]
        table.update_item(
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
        table = self.paused_users
    
        table.put_item(Item={
            'channel': channel,
            'user': user
        }) 
    
    def resume_intros(self, channel: str, user: str):
        table = self.paused_users
    
        table.delete_item(Key={
            'channel': channel,
            'user': user
        }) 
    
    def get_paused_intros(self, channel: str):
        table = self.paused_users
    
        items = table.query(
            KeyConditionExpression='channel = :channel',
            ExpressionAttributeValues={
                ':channel': channel
            }
        )['Items']
        
        return [i['user'] for i in items]
    