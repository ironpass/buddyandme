import boto3
import os
from botocore.exceptions import ClientError

DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE", 'UserMessages')
ENDPOINT_URL = 'http://localhost:8000'

dynamodb = boto3.resource('dynamodb', endpoint_url=ENDPOINT_URL)
table = dynamodb.Table(DYNAMODB_TABLE)

def get_user_session(user_id):
    try:
        response = table.get_item(Key={'UserID': user_id})
        return response.get('Item', {}).get('Messages', [])
    except ClientError as e:
        print("GET_USER_SESSION: ", e.response['Error']['Message'])
        return []

def update_user_session(user_id, messages):
    try:
        table.put_item(Item={'UserID': user_id, 'Messages': messages})
    except ClientError as e:
        print("UPDATE_USER_SESSION: ", e.response['Error']['Message'])
