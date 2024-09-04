import json
import os
import boto3
import logging
from datetime import datetime, timedelta
from typing import Optional

from utils.models import User, Channel


def save_matches(channel: Channel, paired_users: list[list[User]], paired_group_channels: list[Channel]) -> None:
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('intros')
    date = datetime.today().strftime('%Y-%m-%d')
    
    # Create record to insert.
    record_to_insert = {
        'channel': channel.id,
        'date': date,
        'is_latest_date': 1,
        'intros': {
            group_channel.id: {
                'users': [u.id for u in users], 
                'did_meet': False
            }
            for users, group_channel in zip(paired_users, paired_group_channels)
        }
    }
    
    # Set previous matches as not the latest.
    previous_match = table.query(
        IndexName='is_latest_date-channel-index',
        KeyConditionExpression='is_latest_date = :is_latest_date AND channel = :channel',
        ExpressionAttributeValues={
            ':is_latest_date': 1,
            ':channel': channel.id
            
        }
    )['Items']
    
    
    if previous_match:
        
        if previous_match[0]['date'] == date:
            logging.warning(f'Already had a match today for f{channel} - skipping.')
            return

        table.update_item(
            Key={
                'channel': previous_match[0]['channel'],
                'date': previous_match[0]['date']
            },
            UpdateExpression='SET is_latest_date = :is_latest_date',
            ExpressionAttributeValues={':is_latest_date': 0}
        )
    
    
    table.put_item(Item=record_to_insert) 


def expire_old_matches() -> None:
    
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('intros')
    
    previous_matches = table.query(
        IndexName='is_latest_date-channel-index',
        KeyConditionExpression='is_latest_date = :is_latest_date',
        ExpressionAttributeValues={
            ':is_latest_date': 1,
        }
    )['Items']
    
    for match in previous_matches:
        expire_match = False
        if datetime.now() - datetime.fromisoformat(match['date']) > timedelta(days=14):
            expire_match = True
        elif any([m['did_meet'] for m in match['intros'].values()]):
            expire_match = True
            
        if expire_match:
            
            table.update_item(
                Key={
                    'channel': match['channel'],
                    'date': match['date']
                },
                UpdateExpression='SET is_latest_date = :is_latest_date',
                ExpressionAttributeValues={':is_latest_date': 0}
            )


def load_matches() -> dict:
    
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('intros')

    previous_matches = table.query(
        IndexName='is_latest_date-channel-index',
        KeyConditionExpression='is_latest_date = :is_latest_date',
        ExpressionAttributeValues={
            ':is_latest_date': 1,
        }
    )
    
    return previous_matches['Items']


def update_match_did_meet(channel: Channel, group_channel: Channel, did_meet: bool) -> str:
    
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('intros')
    

    previous_matches = table.query(
        IndexName='is_latest_date-channel-index',
        KeyConditionExpression='is_latest_date = :is_latest_date AND channel = :channel',
        ExpressionAttributeValues={
            ':is_latest_date': 1,
            ':channel': channel.id
        }
    )['Items']
    
    if not previous_matches:
        return
    
    match = previous_matches[0]
    table.update_item(
        Key={
            'channel': match['channel'],
            'date': match['date']
        },
        UpdateExpression='SET intros.#group_channel.did_meet = :did_meet',
        ExpressionAttributeNames={
            '#group_channel': group_channel.id,
        },
        ExpressionAttributeValues={
            ':did_meet': did_meet
        }
    )
    
    return True
