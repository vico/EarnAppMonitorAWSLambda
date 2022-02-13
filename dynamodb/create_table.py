import boto3
import os
# boto3 is the AWS SDK library for Python.
# We can use the low-level client to make API calls to DynamoDB.
LOCAL = bool(os.environ.get('local', False))

if LOCAL:
    client = boto3.client('dynamodb', region_name='ap-northeast-1', endpoint_url="http://localhost:8000")
else:
    client = boto3.client('dynamodb', region_name='ap-northeast-1')

try:
    resp = client.create_table(
        TableName="Transactions",
        # Declare your Primary Key in the KeySchema argument
        KeySchema=[
            {
                "AttributeName": "uuid",
                "KeyType": "HASH"
            }
        ],
        # Any attributes used in KeySchema or Indexes must be declared in AttributeDefinitions
        AttributeDefinitions=[
            {
                "AttributeName": "uuid",
                "AttributeType": "S"
            }
        ],
        # ProvisionedThroughput controls the amount of data you can read or write to DynamoDB per second.
        # You can control read and write capacity independently.
        ProvisionedThroughput={
            "ReadCapacityUnits": 1,
            "WriteCapacityUnits": 1
        }
    )

    client.create_table(
        TableName="Devices",
        # Declare your Primary Key in the KeySchema argument
        KeySchema=[
            {
                "AttributeName": "uuid",
                "KeyType": "HASH"
            },
            {
                "AttributeName": "title",
                "KeyType": "RANGE"
            }
        ],
        # Any attributes used in KeySchema or Indexes must be declared in AttributeDefinitions
        AttributeDefinitions=[
            {
                "AttributeName": "uuid",
                "AttributeType": "S"
            },
            {
                "AttributeName": "title",
                "AttributeType": "S"
            }
        ],
        # ProvisionedThroughput controls the amount of data you can read or write to DynamoDB per second.
        # You can control read and write capacity independently.
        ProvisionedThroughput={
            "ReadCapacityUnits": 1,
            "WriteCapacityUnits": 1
        }
    )
    client.create_table(
        TableName="Money",
        # Declare your Primary Key in the KeySchema argument
        KeySchema=[
            {
                "AttributeName": "email",
                "KeyType": "HASH"
            }
        ],
        # Any attributes used in KeySchema or Indexes must be declared in AttributeDefinitions
        AttributeDefinitions=[
            {
                "AttributeName": "email",
                "AttributeType": "S"
            }

        ],
        # ProvisionedThroughput controls the amount of data you can read or write to DynamoDB per second.
        # You can control read and write capacity independently.
        ProvisionedThroughput={
            "ReadCapacityUnits": 1,
            "WriteCapacityUnits": 1
        }
    )

    print("Tables created successfully!")
except Exception as e:
    print("Error creating table:")
    print(e)
