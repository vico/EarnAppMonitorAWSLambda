# -*- encoding: utf8 -*-

from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from enum import Enum
from ipaddress import IPv4Address
from typing import List, Union, Optional
from urllib.parse import urljoin
from uuid import UUID

import boto3
import requests
from dateutil.parser import parse, ParserError
from discord_webhook import DiscordWebhook, DiscordEmbed
from pydantic import BaseModel, condecimal, EmailStr
from tenacity import retry, wait_fixed, stop_after_attempt, RetryError
from typing_extensions import TypedDict

# Press the green button in the gutter to run the script.
EARNAPP_LOGO = "https://www.androidfreeware.net/img2/com-earnapp.jpg"
PAYPAL_ICON = "https://img.icons8.com/color/64/000000/paypal.png"

LOCAL = os.environ.get('local', '')
if LOCAL.lower() == 'false':
    LOCAL = False
else:
    LOCAL = True

GIGABYTES = 1000 ** 3
MEGABYTES = 1000 ** 2

BASE_URL = 'https://earnapp.com/dashboard/api/'
user_data_endpoint = urljoin(BASE_URL, 'user_data')
money_endpoint = urljoin(BASE_URL, 'money')
devices_endpoint = urljoin(BASE_URL, 'devices')
device_endpoint = urljoin(BASE_URL, 'device')
transaction_endpoint = urljoin(BASE_URL, 'transactions')
redeem_endpoint = urljoin(BASE_URL, 'redeem')

if LOCAL:
    # from dotenv import load_dotenv

    # session = boto3.Session(profile_name='dev')  # when run directly with local python, need to specify profile

    # for running inside container using SAM CLI (host.docker.internal only work for Mac Docker)
    dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-1', endpoint_url="http://172.17.0.1:8000")
    # for running directly lambda_function.py
    # dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-1', endpoint_url="http://localhost:8000")
    # load_dotenv()  # load .env file and export content as environment variables: WEBHOOK_URL, TOKEN
else:
    dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-1')

WEBHOOK_URL = os.environ['WEBHOOK_URL']
TOKEN = os.environ['TOKEN']

header = {
    'cookie': f'auth=1; auth-method=google; oauth-refresh-token={TOKEN}'
}
params = (('appid', 'earnapp_dashboard'),)


class TransactionStatus(str, Enum):
    paid = 'paid'
    approved = 'approved'
    pending_procedure = 'pending_procedure'


class Transaction(BaseModel):
    uuid: Union[UUID, str]
    status: TransactionStatus  # paid, approved, pending_procedure
    email: EmailStr
    date: datetime
    payment_method: str
    payment_date: Optional[datetime] = None
    money_amount: condecimal(ge=0)
    ref_bonuses_amount: condecimal(ge=0)
    promo_bonuses_amount: condecimal(ge=0)

    @staticmethod
    @retry(wait=wait_fixed(30), stop=stop_after_attempt(5))
    def get_trx_from_earnapp() -> List[Transaction]:
        tx_res = requests.get(
            transaction_endpoint,
            headers=header,
            params=params
        )

        return list(map(lambda x: Transaction(**x), tx_res.json()))

    @staticmethod
    def insert_trx_to_dynamodb(ret_l, table):
        with table.batch_writer() as batch:
            for trx in ret_l:
                batch.put_item(Item={
                    'uuid': trx.uuid,
                    'status': trx.status,
                    'email': trx.email,
                    'date': str(trx.date),
                    'payment_method': trx.payment_method,
                    'payment_date': str(trx.payment_date),
                    'money_amount': trx.money_amount,
                    'ref_bonuses_amount': trx.ref_bonuses_amount,
                    'promo_bonuses_amount': trx.promo_bonuses_amount
                })

    @staticmethod
    def update_transactions(trx_l: List[Transaction], table=None):
        if table is None:
            table = dynamodb.Table('Transactions')

        for trx in trx_l:
            update_str = 'set #fn = :s'
            update_values = {
                ':s': trx.status
            }
            if trx.payment_date is not None:
                update_str = update_str + ', payment_date = :pd'
                update_values[':pd'] = str(trx.payment_date)

            table.update_item(
                Key={
                    'uuid': trx.uuid
                },
                UpdateExpression=update_str,
                ExpressionAttributeNames={
                    '#fn': 'status'
                },
                ExpressionAttributeValues=update_values,
                ReturnValues="UPDATED_NEW"
            )

    @staticmethod
    def get_all_trx_from_db(table=None) -> List[Transaction]:
        if table is None:
            table = dynamodb.Table('Transactions')
        resp = table.scan()
        ret = []
        for trx in resp['Items']:
            try:
                trx['payment_date'] = parse(trx['payment_date'])
            except ParserError as e:
                trx['payment_date'] = None
            ret.append(Transaction(**trx))
        return ret

    @staticmethod
    def get_non_paid_trx_from_db(table=None) -> List[Transaction]:
        # TODO: rewrite scan to a query with OR condition if possible
        if table is None:
            table = dynamodb.Table('Transactions')
        all_trx = Transaction.get_all_trx_from_db(table)
        resp = [trx for trx in all_trx if
                trx.status == TransactionStatus.approved or trx.status == TransactionStatus.pending_procedure]
        return resp


class RedeemDetails(TypedDict):
    email: str
    payment_method: str
    min_redeem: condecimal(ge=0)


class Money(BaseModel):
    multiplier: condecimal(ge=1)
    multiplier_icon: str
    multiplier_hint: str
    redeem_details: RedeemDetails
    balance: condecimal(ge=0)
    earnings_total: condecimal(ge=0)
    ref_bonuses: condecimal(ge=0)
    ref_bonuses_total: condecimal(ge=0)
    promo_bonuses: condecimal(ge=0)
    promo_bonuses_total: condecimal(ge=0)
    referral_part: str

    @staticmethod
    @retry(wait=wait_fixed(30), stop=stop_after_attempt(5))
    def get_money_data_from_earnapp() -> Money:
        money_res = requests.get(
            money_endpoint,
            headers=header,
            params=params
        )
        return Money(**money_res.json())

    @staticmethod
    def get_money_data(email: str, table=None) -> Money:
        if table is None:
            table = dynamodb.Table('Money')
        resp = table.get_item(Key={"email": email})
        return Money(**resp['Item'])

    def write_to_db(self, table=None):
        if table is None:
            table = dynamodb.Table('Money')

        update_str = "set balance=:b, multiplier=:m, multiplier_icon=:mi, multiplier_hint=:mh, earnings_total= :ea"
        table.update_item(
            Key={
                'email': self.redeem_details['email']
            },
            UpdateExpression=update_str,
            ExpressionAttributeValues={
                ':b': self.balance,
                ':m': self.multiplier,
                ':mi': self.multiplier_icon,
                ':mh': self.multiplier_hint,
                ':ea': self.earnings_total,
            },
            ReturnValues="UPDATED_NEW"
        )


class Device(BaseModel):
    uuid: Union[UUID, str]
    appid: Optional[str] = ""  # old version does not have appid
    title: str
    bw: int
    total_bw: int
    redeem_bw: int
    rate: condecimal(ge=0)
    earned: condecimal(ge=0)
    earned_total: condecimal(ge=0)
    country: str
    ips: List[IPv4Address]

    def __init__(self, **data):  # not work when import old data from DB -> updated data in DB
        if isinstance(data['rate'], str):  # if the rate is a string (expect pattern of $0.25/GB)
            l = data['rate'].split(
                '/')  # split $0.25/GB to 2 parts (20220226 2:00 JST changed to str of format $0.25/GB)
            data['rate'] = Decimal(l[0][1:])
        super().__init__(**data)

    # @property
    # def rate_d(self) -> Decimal:
    #     if isinstance(self.rate, Decimal):
    #         return self.rate
    #     l = self.rate.split('/')  # split $0.25/GB to 2 parts
    #     return Decimal(l[0][1:])

    def bw2cents(self) -> Decimal:
        """
        Given a device object, return number of cents earned by bandwidth use.
        :return: number of cents (USD)
        """
        return self.bw // ((Decimal(0.01) / self.rate) * GIGABYTES)

    def calculate_pending_bytes(self) -> Decimal:
        # number of G for 0.01USD = 0.01/0.25 = 0.04 GB (/0.01USD)
        number_of_cents = self.bw2cents()
        pending_bytes = self.bw - number_of_cents * Decimal((Decimal(0.01) / self.rate) * GIGABYTES)
        return pending_bytes

    def calculate_bandwidth_used(self) -> Decimal:
        """
        Given a bandwidth number already used, return number which already converted to money
        :return: a number express the bandwidth converted to money
        """
        number_of_cents = self.bw2cents()
        return number_of_cents * Decimal((Decimal(0.01) / self.rate) * GIGABYTES)

    @staticmethod
    @retry(wait=wait_fixed(30), stop=stop_after_attempt(5))
    def get_devices_info_from_earnapp() -> List[Device]:
        dev_res = requests.get(
            devices_endpoint,
            headers=header,
            params=params
        )
        return list(map(lambda x: Device(**x), dev_res.json()))

    @staticmethod
    def get_devices_from_db(table=None) -> List[Device]:
        if table is None:
            table = dynamodb.Table('Devices')
        all_devs = table.scan()
        return [Device(**item) for item in all_devs['Items']]

    @staticmethod
    def update_devices(dev_l, table=None):
        if table is None:
            table = dynamodb.Table('Devices')
        for dev in dev_l:
            table.update_item(
                Key={
                    'uuid': dev.uuid,
                    'title': dev.title
                },
                UpdateExpression="set bw=:bw, earned=:earned, earned_total=:et, total_bw=:tb, redeem_bw=:rb, ips=:ips, rate=:r, app_id=:aid",
                ExpressionAttributeValues={
                    ':earned': dev.earned,
                    ':et': dev.earned_total,
                    ':tb': Decimal(dev.total_bw),
                    ':rb': Decimal(dev.redeem_bw),
                    ':bw': Decimal(dev.bw),
                    ':ips': list(map(lambda x: str(x), dev.ips)),
                    ':r': dev.rate,
                    ':aid': dev.appid
                },
                ReturnValues="UPDATED_NEW"
            )

    @staticmethod
    def get_traffic_and_earnings(dev_l: List[Device], current_devs: List[Device]) -> str:
        dev_map = {dev.uuid: dev for dev in dev_l}

        bw_usage = defaultdict(int)
        earned_dict = defaultdict(Decimal)

        for dev in current_devs:
            # the bandwidth used at this moment is the current bandwidth used minus the bandwidth converted to money last time
            bw_used = dev_map[dev.uuid].bw - dev.calculate_bandwidth_used()
            bw_usage[dev.title] += bw_used

            # need to calculate money based on total bandwidth used for each device
            earned_dict[dev.title] = bw_usage[dev.title] // ((Decimal(0.01) / current_devs[0].rate) * GIGABYTES)

        ret_l = [f'{k: <15}: {v / MEGABYTES: >8.2f}MB|{earned_dict[k] / 100:>5.2f}$' for (k, v) in bw_usage.items()]

        return '\n'.join(ret_l)


class DiscordUtility:

    @staticmethod
    def notify_new_trx(trx_l: List[Transaction], title: str = 'New Redeem Request'):
        webhook = DiscordWebhook(url=WEBHOOK_URL, rate_limit_retry=True)
        assert len(trx_l) > 0
        trx = trx_l[0]
        if title == 'New Redeem Request':
            description = 'New redeem request has been submitted'
        else:
            title = f'{title}: {trx.status}'
            description = 'Redeem request status updated.'

        embed = DiscordEmbed(
            title=title,
            description=description,
            color="07FF70"
        )
        embed.set_thumbnail(url=EARNAPP_LOGO)
        for transaction in trx_l:
            embed.add_embed_field(name="UUID", value=f"{transaction.uuid}")
            embed.add_embed_field(name="Amount", value=f"+{transaction.money_amount}$")
            embed.add_embed_field(name="Status", value=f"{transaction.status}")
            embed.add_embed_field(name="Redeem Date", value=f"{transaction.date.strftime('%Y-%m-%d')}")

        embed.add_embed_field(name="Method", value=f"{trx.payment_method}")
        embed.add_embed_field(name="Email", value=f"{trx.email}")

        footer_text = f"Payment {trx.status} as on {trx.date.strftime('%Y-%m-%d')} via {trx.payment_method}"

        embed.set_footer(text=footer_text, icon_url=PAYPAL_ICON)
        webhook.add_embed(embed)
        webhook.execute()


def lambda_handler(event, context):
    """Lambda function for notifying EarnApp's changes in balance and bandwidth usage via Discord.

        Parameters
        ----------
        event: dict, optional
            API Gateway Lambda Proxy Input Format

            Event doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html#api-gateway-simple-proxy-for-lambda-input-format

        context: object, optional
            Lambda Context runtime methods and attributes

            Context doc: https://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html

        Returns
        ------
        Discord's response: text

            Return doc
        """
    webhook = DiscordWebhook(url=WEBHOOK_URL)

    try:
        earnapp_money = Money.get_money_data_from_earnapp()
        money_table = dynamodb.Table('Money')
        db_money = Money.get_money_data(earnapp_money.redeem_details['email'], money_table)

        dev_table = dynamodb.Table('Devices')
        dev_l = Device.get_devices_info_from_earnapp()  # get latest devices information from EarnApp API
        current_devs = Device.get_devices_from_db(dev_table)  # get current information from DynamoDB

        trx_table = dynamodb.Table('Transactions')
        non_paid_trx_map = {trx.uuid: trx for trx in Transaction.get_non_paid_trx_from_db(trx_table)
                            if trx.status == TransactionStatus.approved or
                            trx.status == TransactionStatus.pending_procedure}

        all_trx = Transaction.get_trx_from_earnapp()
        trx_map = {trx.uuid: trx for trx in all_trx}
        approved_trx_l = [trx for trx in all_trx if trx.status == TransactionStatus.approved
                          and trx.uuid not in non_paid_trx_map
                          ]

        # notify about change in bandwidth usage
        change = earnapp_money.balance - db_money.balance
        if change > 0:
            title = f"Balance [+{change:.2f} → {earnapp_money.balance}] ({earnapp_money.multiplier:.2f})"  # for displaying on notification msg
            color = "03F8C4"
        elif change == 0:
            title = f"Balance Unchanged! [{earnapp_money.balance}] ({earnapp_money.multiplier:.2f})"
            color = "E67E22"
        else:  # bug from earnapp which may withdraw money
            title = f'Balance [{change:.2f} → {earnapp_money.balance}] ({earnapp_money.multiplier:.2f})'
            color = "FF0000"

        embed = DiscordEmbed(
            title=title,
            color=color
        )

        embed.set_thumbnail(url=EARNAPP_LOGO)
        embed.add_embed_field(name="Earned", value=f"+{change:.2f}$")
        embed.add_embed_field(name="Balance", value=f"{earnapp_money.balance:.2f}")
        embed.add_embed_field(name="Lifetime Balance",
                              value=f"{earnapp_money.earnings_total:.2f}")
        embed.add_embed_field(name='Traffic and Earnings',
                              value=Device.get_traffic_and_earnings(dev_l, current_devs))
        embed.add_embed_field(name="Total Devices",
                              value=f"{len(dev_l)}")

        embed.set_footer(text=f"Version: 0.0.1.0", icon_url=PAYPAL_ICON)
        embed.set_timestamp()

        webhook.add_embed(embed)

        # notify about redeem or status change of deem request if any


        # find status changed trx
        changed_l = []
        for uuid in non_paid_trx_map.keys():
            if trx_map[uuid].status != non_paid_trx_map[uuid].status:  # transaction status changed!
                changed_l.append(trx_map[uuid])
        is_redeemed = len(approved_trx_l) > 0
        if is_redeemed:
            DiscordUtility.notify_new_trx(approved_trx_l)
            # insert new approved transactions to DynamoDB
            Transaction.insert_trx_to_dynamodb(approved_trx_l, trx_table)
        elif len(changed_l) > 0:  # there are trx which have status are updated
            DiscordUtility.notify_new_trx(changed_l, title='Redeem Requests Status Changed!')
            Transaction.update_transactions(changed_l, trx_table)  # update trx status

        Device.update_devices(dev_l, dev_table)
        earnapp_money.write_to_db(money_table)  # always write balance info got from Dashboard to DB
        print('finished')
    except RetryError:
        embed = DiscordEmbed(
            title="Earning Update Error 🤖",
            description="Cannot get information from Earnapp!!!",
            color="FFFFFF"
        )
        webhook.add_embed(embed)

    response = webhook.execute()
    return response.text


if __name__ == '__main__':
    lambda_handler({}, {})
