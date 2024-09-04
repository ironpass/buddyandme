import boto3
import os
from botocore.exceptions import ClientError

# Environment Variables
DYNAMODB_MESSAGES_TABLE = os.getenv("DYNAMODB_MESSAGES_TABLE", 'UserMessages')
DYNAMODB_PROMPTS_TABLE = os.getenv("DYNAMODB_PROMPTS_TABLE", 'UserPrompts')
ENDPOINT_URL = os.getenv("DYNAMODB_ENDPOINT_URL", None)

# Create the DynamoDB resource
if ENDPOINT_URL:
    dynamodb = boto3.resource('dynamodb', endpoint_url=ENDPOINT_URL)
else:
    dynamodb = boto3.resource('dynamodb')

# Tables
messages_table = dynamodb.Table(DYNAMODB_MESSAGES_TABLE)
prompts_table = dynamodb.Table(DYNAMODB_PROMPTS_TABLE)

def get_user_session(user_id):
    try:
        response = messages_table.get_item(Key={'UserID': user_id})
        return response.get('Item', {}).get('Messages', [])
    except ClientError as e:
        print("GET_USER_SESSION: ", e.response['Error']['Message'])
        return []

def update_user_session(user_id, messages):
    try:
        messages_table.put_item(Item={'UserID': user_id, 'Messages': messages})
    except ClientError as e:
        print("UPDATE_USER_SESSION: ", e.response['Error']['Message'])

def get_user_system_prompt(user_id):
    try:
        response = prompts_table.get_item(Key={'UserID': user_id})
        item = response.get('Item', None)
        
        if not item:
            # If user does not exist, return None for both fields
            return {"SystemPrompt": None, "ActiveMessageLimit": None}
        
        # Return raw system prompt and ActiveMessageLimit from the database
        system_prompt = item.get('SystemPrompt', None)  # No default value here
        active_message_limit = item.get('ActiveMessageLimit', None)  # No default value here
        
        return {"SystemPrompt": system_prompt, "ActiveMessageLimit": active_message_limit}
    except ClientError as e:
        print("GET_USER_SYSTEM_PROMPT: ", e.response['Error']['Message'])
        return {"SystemPrompt": None, "ActiveMessageLimit": None}

# Unused for now
def update_user_system_prompt(user_id, system_prompt, active_message_limit):
    try:
        prompts_table.put_item(Item={'UserID': user_id, 'SystemPrompt': system_prompt, 'ActiveMessageLimit': active_message_limit})
    except ClientError as e:
        print("UPDATE_USER_SYSTEM_PROMPT: ", e.response['Error']['Message'])
