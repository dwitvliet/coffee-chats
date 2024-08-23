import base64
import json
import urllib.parse
import urllib.request

def lambda_handler(event, context):
    
    if 'body' not in event:
        return {'statusCode': 403}
        
    #Check for right message here.
        
    if event.get('isBase64Encoded'):
        body_decoded = base64.b64decode(event['body']).decode('utf-8')
    else:
        body_decoded = event['body']
        
    payload = json.loads(urllib.parse.parse_qs(body_decoded)['payload'][0])
    
    action = payload['actions'][0]['action_id']
    response_url = payload['response_url']
    channel_id = payload['channel']['id']
    user_id = payload['user']['id']
    
    message = {
        "response_type": "in_channel",  # Message will be visible to everyone in the channel
        "text": f"<@{user_id}> clicked button {action}!"
    }

    data = json.dumps(message).encode('utf-8')
    req = urllib.request.Request(response_url, data=data, headers={'Content-Type': 'application/json'})
    urllib.request.urlopen(req)
    
    

    
    return {
        'statusCode': 200,
        'body': json.dumps({'text': 'No action taken.'})
    }
    
