import os
import boto3
import pytest
import datetime
from botocore.exceptions import ClientError

# Import functions from core
from app.db import get_user_session, update_user_session
from app.core import limit_messages

# Environment variables
os.environ['DYNAMODB_TABLE'] = 'UserMessages'
DYNAMODB_TABLE = os.getenv('DYNAMODB_TABLE', 'UserMessages')
DYNAMODB_ENDPOINT_URL = os.getenv('DYNAMODB_ENDPOINT_URL', 'http://localhost:8000')

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb', endpoint_url=DYNAMODB_ENDPOINT_URL)

@pytest.fixture(scope='module')
def dynamodb_client():
    table = dynamodb.Table(DYNAMODB_TABLE)
    # Ensure the table exists before running tests
    try:
        table.delete()
        table.wait_until_not_exists()
    except ClientError:
        pass

    table = dynamodb.create_table(
        TableName=DYNAMODB_TABLE,
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
    table.wait_until_exists()
    yield table

    # Cleanup after tests
    table.delete()
    table.wait_until_not_exists()

def test_get_user_session(dynamodb_client):
    # Insert a test item
    dynamodb_client.put_item(Item={
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

    response = dynamodb_client.get_item(Key={'UserID': user_id})
    stored_messages = response.get('Item', {}).get('Messages', [])
    assert len(stored_messages) == 1
    assert stored_messages[0]['content'] == 'Updated message'

if __name__ == '__main__':
    pytest.main()
