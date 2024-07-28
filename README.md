Please do this to deploy the serverless
`sls deploy`

Start DB before test or run locally
`java -Djava.library.path=./DynamoDBLocal_lib -jar DynamoDBLocal.jar -sharedDb`

Start DB interface (DynamoDB Admin)
cd into the dynamodb-admin
`DYNAMO_ENDPOINT=localhost:8001 npm start`

Do this to run locally
`uvicorn main:app --host 0.0.0.0 --port 8000`

For test please run
`pytest test/*`