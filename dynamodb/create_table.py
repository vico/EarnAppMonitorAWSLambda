import datetime
from decimal import Decimal

import boto3
import os
from dotenv import load_dotenv

load_dotenv()  # load .env file and export content as environment variables: WEBHOOK_URL, TOKEN

WEBHOOK_URL = os.environ['WEBHOOK_URL']
TOKEN = os.environ['TOKEN']

from lambda_function import Transaction, insert_trx_to_dynamodb


LOCAL = os.environ.get('local', '')
if LOCAL.lower() == 'true':
    LOCAL = True
else:
    LOCAL = False

if LOCAL:
    client = boto3.client('dynamodb', region_name='ap-northeast-1', endpoint_url="http://localhost:8000")
else:
    client = boto3.client('dynamodb', region_name='ap-northeast-1')

def create_trx_table():
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
        print("Tables created successfully!")
    except Exception as e:
        print("Error creating table:")
        print(e)


def create_devices_table():
    try:
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
        print("Tables created successfully!")
    except Exception as e:
        print("Error creating table:")
        print(e)


def create_money_table():
    try:
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


def populate_trx():
    dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-1', endpoint_url="http://localhost:8000")
    trx_l = [
        Transaction(uuid='620de578a4395ee504b765ba', status='pending_procedure', email='tranvinhcuong@gmail.com',
                    date=datetime.datetime(2022, 2, 17, 6, 4, 40, 370000, tzinfo=datetime.timezone.utc),
                    payment_method='paypal.com', payment_date=None, money_amount=Decimal('2.81'),
                    ref_bonuses_amount=Decimal('0'), promo_bonuses_amount=Decimal('0')),
        Transaction(uuid='6205fc7685640a493f3de818', status='paid', email='tranvinhcuong@gmail.com',
                    date=datetime.datetime(2022, 2, 11, 6, 4, 38, 275000, tzinfo=datetime.timezone.utc),
                    payment_method='paypal.com',
                    payment_date=datetime.datetime(2022, 2, 13, 8, 8, 45, 805000, tzinfo=datetime.timezone.utc),
                    money_amount=Decimal('2.61'), ref_bonuses_amount=Decimal('0'), promo_bonuses_amount=Decimal('0')),
        Transaction(uuid='61fe1421b77c5459abf57a2b', status='paid', email='tranvinhcuong@gmail.com',
                    date=datetime.datetime(2022, 2, 5, 6, 7, 29, 140000, tzinfo=datetime.timezone.utc),
                    payment_method='paypal.com',
                    payment_date=datetime.datetime(2022, 2, 6, 8, 18, 27, 879000, tzinfo=datetime.timezone.utc),
                    money_amount=Decimal('3.14'), ref_bonuses_amount=Decimal('0'), promo_bonuses_amount=Decimal('0')),
        Transaction(uuid='61f77cf780ce06d130774824', status='paid', email='tranvinhcuong@gmail.com',
                    date=datetime.datetime(2022, 1, 31, 6, 8, 55, 425000, tzinfo=datetime.timezone.utc),
                    payment_method='paypal.com',
                    payment_date=datetime.datetime(2022, 1, 31, 12, 0, 44, 99000, tzinfo=datetime.timezone.utc),
                    money_amount=Decimal('6.08'), ref_bonuses_amount=Decimal('0'), promo_bonuses_amount=Decimal('0'))
    ]
    trx_table = dynamodb.Table('Transactions')
    insert_trx_to_dynamodb(trx_l, trx_table)


if __name__ == '__main__':
    create_devices_table()
    create_trx_table()
    create_money_table()
    populate_trx()