import os
import boto3
import pytest
import datetime
from botocore.exceptions import ClientError
from app.db import get_user_session, update_user_session, get_user_system_prompt, update_user_system_prompt, dynamodb

@pytest.fixture(scope='module')
def dynamodb_client():
    # Access the tables using the dynamodb object from app.db
    messages_table = dynamodb.Table(os.environ['DYNAMODB_MESSAGES_TABLE'])
    prompts_table = dynamodb.Table(os.environ['DYNAMODB_PROMPTS_TABLE'])

    # Ensure the UserMessages_TEST table exists before running tests
    try:
        messages_table.delete()
        messages_table.wait_until_not_exists()
    except ClientError:
        pass

    messages_table = dynamodb.create_table(
        TableName=os.environ['DYNAMODB_MESSAGES_TABLE'],
        KeySchema=[
            {
                'AttributeName': 'UserID',
                'KeyType': 'HASH'
            }
        ],
        AttributeDefinitions=[
            {
                'AttributeName': 'UserID',
                'AttributeType': 'S'
            }
        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 5,
            'WriteCapacityUnits': 5
        }
    )
    messages_table.wait_until_exists()

    # Ensure the UserPrompts_TEST table exists before running tests
    try:
        prompts_table.delete()
        prompts_table.wait_until_not_exists()
    except ClientError:
        pass

    prompts_table = dynamodb.create_table(
        TableName=os.environ['DYNAMODB_PROMPTS_TABLE'],
        KeySchema=[
            {
                'AttributeName': 'UserID',
                'KeyType': 'HASH'
            }
        ],
        AttributeDefinitions=[
            {
                'AttributeName': 'UserID',
                'AttributeType': 'S'
            }
        ],
        ProvisionedThroughput={
            'ReadCapacityUnits': 5,
            'WriteCapacityUnits': 5
        }
    )
    prompts_table.wait_until_exists()

    yield messages_table, prompts_table

    # Cleanup after tests
    messages_table.delete()
    messages_table.wait_until_not_exists()
    prompts_table.delete()
    prompts_table.wait_until_not_exists()

def test_get_user_session(dynamodb_client):
    messages_table, _ = dynamodb_client

    # Insert a test item into the UserMessages_TEST table
    messages_table.put_item(Item={
        'UserID': 'test_user',
        'Messages': [
            {
                'role': 'user',
                'content': 'Hello',
                'timestamp': datetime.datetime.utcnow().isoformat()
            },
            {
                'role': 'assistant',
                'content': 'Hi there!',
                'timestamp': datetime.datetime.utcnow().isoformat()
            }
        ]
    })

    # Test get_user_session
    messages = get_user_session('test_user')
    assert len(messages) == 2
    assert messages[0]['content'] == 'Hello'
    assert messages[1]['content'] == 'Hi there!'

def test_update_user_session(dynamodb_client):
    messages_table, _ = dynamodb_client
    user_id = 'test_user'
    messages = [
        {
            'role': 'user',
            'content': 'Updated message',
            'timestamp': datetime.datetime.utcnow().isoformat()
        }
    ]
    # Test update_user_session
    update_user_session(user_id, messages)

    response = messages_table.get_item(Key={'UserID': user_id})
    stored_messages = response.get('Item', {}).get('Messages', [])
    assert len(stored_messages) == 1
    assert stored_messages[0]['content'] == 'Updated message'

def test_get_user_system_prompt(dynamodb_client):
    _, prompts_table = dynamodb_client

    # Insert a test item into the UserPrompts_TEST table
    prompts_table.put_item(Item={
        'UserID': 'test_user',
        'SystemPrompt': 'You are a friendly assistant.'
    })

    # Test get_user_system_prompt
    system_prompt = get_user_system_prompt('test_user')
    assert system_prompt == 'You are a friendly assistant.'

def test_update_user_system_prompt(dynamodb_client):
    _, prompts_table = dynamodb_client
    user_id = 'test_user'
    new_prompt = 'You are a playful teddy bear.'

    # Test update_user_system_prompt
    update_user_system_prompt(user_id, new_prompt)

    response = prompts_table.get_item(Key={'UserID': user_id})
    stored_prompt = response.get('Item', {}).get('SystemPrompt', '')
    assert stored_prompt == new_prompt

if __name__ == '__main__':
    pytest.main()
