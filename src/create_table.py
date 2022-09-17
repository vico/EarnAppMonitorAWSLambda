import datetime
import os
from decimal import Decimal
from ipaddress import IPv4Address

import boto3
from dotenv import load_dotenv

load_dotenv()  # load .env file and export content as environment variables: WEBHOOK_URL, TOKEN

WEBHOOK_URL = os.environ['WEBHOOK_URL']
TOKEN = os.environ['TOKEN']

from lambda_function import Transaction, Money, Device

LOCAL = os.environ.get('local', '')
if LOCAL.lower() == 'false':
    LOCAL = False
else:
    LOCAL = True

session = boto3.Session(profile_name='dev')
if LOCAL:
    client = session.client('dynamodb', region_name='ap-northeast-1', endpoint_url="http://localhost:8000")
else:
    client = session.client('dynamodb', region_name='ap-northeast-1')


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
    dynamodb = session.resource('dynamodb', region_name='ap-northeast-1', endpoint_url="http://localhost:8000")
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
    Transaction.insert_trx_to_dynamodb(trx_l, trx_table)


def populate_money_table():
    dynamodb = session.resource('dynamodb', region_name='ap-northeast-1', endpoint_url="http://localhost:8000")
    table = dynamodb.Table('Money')

    money = Money(**{'ref_bonuses_total': Decimal('0'),
                     'multiplier_hint': '',
                     'balance': Decimal('0.44'),
                     'multiplier': Decimal('1'),
                     'multiplier_icon': '',
                     'redeem_details': {'email': 'tranvinhcuong@gmail.com',
                                        'payment_method': 'paypal.com',
                                        'min_redeem': Decimal('2.5')},
                     'ref_bonuses': Decimal('0'),
                     'promo_bonuses': Decimal('0'),
                     'earnings_total': Decimal('15.1'),
                     'referral_part': '10%',
                     'promo_bonuses_total': Decimal('0'),
                     'email': 'tranvinhcuong@gmail.com'})

    with table.batch_writer() as batch:
        batch.put_item(Item={
            'email': money.redeem_details['email'],
            'multiplier': money.multiplier,
            'multiplier_icon': money.multiplier_icon,
            'multiplier_hint': money.multiplier_hint,
            'redeem_details': money.redeem_details,
            'balance': money.balance,
            'earnings_total': money.earnings_total,
            'ref_bonuses': money.ref_bonuses,
            'ref_bonuses_total': money.ref_bonuses_total,
            'promo_bonuses': money.promo_bonuses,
            'promo_bonuses_total': money.promo_bonuses_total,
            'referral_part': money.referral_part
        })


def populate_device_table():
    dynamodb = session.resource('dynamodb', region_name='ap-northeast-1', endpoint_url="http://localhost:8000")
    table = dynamodb.Table('Devices')
    dev_l = [
        Device(uuid='sdk-node-31eb47c5d15849e5917a8028eee266cb', appid='node_earnapp.com', title='middle', bw=264677198,
               total_bw=2872097612, redeem_bw=2607420414, rate='$0.25/GB', earned=Decimal('0.06'),
               earned_total=Decimal('0.69'), country='jp', ips=[IPv4Address('222.224.148.183')]),
        Device(uuid='sdk-node-81869dce55b94d6e9d039ca3bc692cd9', appid='node_earnapp.com', title='bottom', bw=279744982,
               total_bw=3033488514, redeem_bw=2753743532, rate='$0.25/GB', earned=Decimal('0.06'),
               earned_total=Decimal('0.73'), country='jp', ips=[IPv4Address('222.224.148.183')]),
        Device(uuid='sdk-node-ca17fd0e8c2d4cd19d6fa6b4f0a324b4', appid='node_earnapp.com', title='top', bw=814733496,
               total_bw=5666501096, redeem_bw=4851767600, rate='$0.25/GB', earned=Decimal('0.19'),
               earned_total=Decimal('1.4'), country='jp', ips=[IPv4Address('111.217.8.34')]),
        Device(uuid='sdk-node-5171d466bdf643d2b87f374fb3e08f41', appid='node_earnapp.com', title='desktop',
               bw=599303480, total_bw=19924712920, redeem_bw=19325409440, rate='$0.25/GB', earned=Decimal('0.14'),
               earned_total=Decimal('7.32'), country='jp', ips=[IPv4Address('111.217.8.34')])
    ]
    with table.batch_writer() as batch:
        for dev in dev_l:
            tmp = dev.dict()
            tmp['ips'] = list(map(lambda x: str(x), tmp['ips']))
            batch.put_item(Item=tmp)


if __name__ == '__main__':
    create_devices_table()
    create_trx_table()
    create_money_table()
    populate_trx()
    populate_money_table()
    populate_device_table()