import os
os.environ['DYNAMODB_MESSAGES_TABLE'] = 'UserMessages_TEST'
os.environ['DYNAMODB_PROMPTS_TABLE'] = 'UserPrompts_TEST'
os.environ['DYNAMODB_ENDPOINT_URL'] = 'http://localhost:8000'

from dotenv import load_dotenv
load_dotenv()
