# -*- encoding: utf8 -*-

import os
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from ipaddress import IPv4Address
from typing import List, Union, Optional
from urllib.parse import urljoin
from uuid import UUID

import boto3
import requests
from boto3.dynamodb.conditions import Key
from dateutil.parser import parse, ParserError
from discord_webhook import DiscordWebhook, DiscordEmbed
from pydantic import BaseModel, condecimal, EmailStr
from tenacity import retry, wait_fixed, stop_after_attempt, RetryError
from typing_extensions import TypedDict

# Press the green button in the gutter to run the script.
EARNAPP_LOGO = "https://www.androidfreeware.net/img2/com-earnapp.jpg"
PAYPAL_ICON = "https://img.icons8.com/color/64/000000/paypal.png"

LOCAL = bool(os.environ.get('local', False))
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
    from dotenv import load_dotenv

    dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-1', endpoint_url="http://localhost:8000")
    load_dotenv()  # load .env file and export content as environment variables: WEBHOOK_URL, TOKEN
else:
    dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-1')

WEBHOOK_URL = os.environ['WEBHOOK_URL']
TOKEN = os.environ['TOKEN']

header = {
    'cookie': f'auth=1; auth-method=google; oauth-refresh-token={TOKEN}'
}
params = (('appid', 'earnapp_dashboard'),)


class RedeemDetails(TypedDict):
    email: str
    payment_method: str
    min_redeem: condecimal(ge=0)


class Transaction(BaseModel):
    uuid: Union[UUID, str]
    status: str  # paid, approved, pending_procedure
    email: EmailStr
    date: datetime
    payment_method: str
    payment_date: Optional[datetime] = None
    money_amount: condecimal(ge=0)
    ref_bonuses_amount: condecimal(ge=0)
    promo_bonuses_amount: condecimal(ge=0)


class Money(BaseModel):
    multiplier: int
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


def bw2cents(dev: Device) -> Decimal:
    """
    Given a device object, return number of cents earned by bandwidth use.
    :param dev: target device
    :return: number of cents (USD)
    """
    return dev.bw // ((Decimal(0.01) / dev.rate) * GIGABYTES)


def calculate_pending_bytes(dev: Device) -> Decimal:
    # number of G for 0.01USD = 0.01/0.25 = 0.04 GB (/0.01USD)
    number_of_cents = bw2cents(dev)
    pending_bytes = dev.bw - number_of_cents * Decimal((Decimal(0.01) / dev.rate) * GIGABYTES)
    return pending_bytes


def calculate_bandwidth_used(dev: Device) -> Decimal:
    """
    Given a bandwidth number already used, return number which already converted to money
    :param dev: Device object
    :return: a number express the bandwidth converted to money
    """
    number_of_cents = bw2cents(dev)
    return number_of_cents * Decimal((Decimal(0.01) / dev.rate) * GIGABYTES)


@retry(wait=wait_fixed(30), stop=stop_after_attempt(5))
def get_money_data_from_earnapp() -> Money:
    money_res = requests.get(
        money_endpoint,
        headers=header,
        params=params
    )
    return Money(**money_res.json())


@retry(wait=wait_fixed(30), stop=stop_after_attempt(5))
def get_devices_info_from_earnapp() -> List[Device]:
    dev_res = requests.get(
        devices_endpoint,
        headers=header,
        params=params
    )
    return list(map(lambda x: Device(**x), dev_res.json()))


def get_money_data(email: str, table=None) -> Money:
    if table is None:
        table = dynamodb.Table('Money')
    resp = table.get_item(Key={"email": email})
    return Money(**resp['Item'])


def update_money(m: Money, table=None):
    if table is None:
        table = dynamodb.Table('Money')

    table.update_item(
        Key={
            'email': m.redeem_details['email']
        },
        UpdateExpression="set balance=:b",
        ExpressionAttributeValues={
            ':b': m.balance,
        },
        ReturnValues="UPDATED_NEW"
    )


def get_current_devices(table=None) -> List[Device]:
    if table is None:
        table = dynamodb.Table('Devices')
    all_devs = table.scan()
    return [Device(**item) for item in all_devs['Items']]


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


def get_trx_from_earnapp():
    tx_res = requests.get(
        transaction_endpoint,
        headers=header,
        params=params
    )

    return list(map(lambda x: Transaction(**x), tx_res.json()))


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


def get_non_paid_trx_from_db(table=None) -> List[Transaction]:
    if table is None:
        table = dynamodb.Table('Transactions')
    all_trx = get_all_trx_from_db(table)
    resp = [trx for trx in all_trx if trx.status == 'approved' or trx.status == 'pending_procedure']
    return resp

def update_transactions(trx_l: List[Transaction], table=None):
    if table is None:
        table = dynamodb.Table('Transactions')

    for trx in trx_l:
        table.update_item(
            Key={
                'uuid': trx.uuid
            },
            UpdateExpression='set #fn = :s',
            ExpressionAttributeNames= {
                '#fn': 'status'
            },
            ExpressionAttributeValues={
                ':s': trx.status
            },
            ReturnValues="UPDATED_NEW"
        )


def get_traffic_and_earnings(dev_l, current_devs) -> str:
    dev_map = {dev.uuid: dev for dev in dev_l}

    bw_usage = defaultdict(int)
    earned_dict = defaultdict(Decimal)

    for dev in current_devs:
        title = str(dev.title)  # Assumption: each device has 1 ip as first element in the list

        # the bandwidth used at this moment is the current bandwidth used minus the bandwidth converted to money last time
        bw_used = dev_map[dev.uuid].bw - calculate_bandwidth_used(dev)
        bw_usage[title] += bw_used

        # pending_bytes += calculate_pending_bytes(dev_map[dev.uuid])  # total number of bytes for each device which not fit a cent
        # dev_earn = bw2cents(dev_map[dev.uuid]) - bw2cents(dev)  # number of cents earned
        # earned_dict[device_ip] += dev_earn  # total number of cents for each IP
        # need to calculate money based on total bandwidth used for each IP
        earned_dict[title] = bw_usage[title] // ((Decimal(0.01) / current_devs[0].rate) * GIGABYTES)

    ret_l = [f'{k: <15}: {v / MEGABYTES: >8.2f}MB|{earned_dict[k] / 100:>5.2f}$' for (k, v) in bw_usage.items()]

    return '\n'.join(ret_l)


def notify_new_trx(trx_l: List[Transaction], title: str='New Redeem Request'):
    webhook = DiscordWebhook(url=WEBHOOK_URL, rate_limit_retry=True)
    assert len(trx_l) > 0
    trx = trx_l[0]
    embed = DiscordEmbed(
        title=title,
        description= "New redeem request has been submitted" if title == 'New Redeem Request' else 'Redeem request status updated' ,
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
    webhook = DiscordWebhook(url=WEBHOOK_URL)

    try:
        earnapp_money = get_money_data_from_earnapp()
        money_table = dynamodb.Table('Money')
        db_money = get_money_data(earnapp_money.redeem_details['email'], money_table)

        dev_table = dynamodb.Table('Devices')
        dev_l = get_devices_info_from_earnapp()  # get latest devices information from EarnApp API
        current_devs = get_current_devices(dev_table)  # get current information from DynamoDB

        trx_table = dynamodb.Table('Transactions')
        non_paid_trx_map = {trx.uuid: trx for trx in get_non_paid_trx_from_db(trx_table)
                             if trx.status == 'approved' or trx.status=='pending_procedure'}

        all_trx = get_trx_from_earnapp()
        trx_map = { trx.uuid: trx for trx in all_trx}
        approved_trx_l = [trx for trx in all_trx if trx.status == 'approved']

        # find status changed trx
        changed_l = []
        for uuid in non_paid_trx_map.keys():
            if trx_map[uuid].status != non_paid_trx_map[uuid]:  # transaction status changed!
                changed_l.append(trx_map[uuid])

        if len(approved_trx_l) > 0:
            notify_new_trx(approved_trx_l)
            # insert new approved transactions to DynamoDB
            insert_trx_to_dynamodb(approved_trx_l, trx_table)
            change = earnapp_money.balance  # there is a redeem request, so reset the change value to balance
        elif len(changed_l) > 0:  # approved redeem request is processed now
            notify_new_trx(changed_l, title='Redeem Requests Status Changed!')
            change = earnapp_money.balance - db_money.balance
            update_transactions(changed_l, trx_table)  # update trx status
        else:
            change = earnapp_money.balance - db_money.balance

        if change > 0:
            title = f"Balance Increased [+{change}]"
            color = "03F8C4"
            update_money(earnapp_money, money_table)
            update_devices(dev_l, dev_table)
        elif change == 0:
            title = "Balance Unchanged!"
            color = "E67E22"
        else:  # bug from earnapp which may withdraw money
            title = f'Balance Decreased! [{change}]'
            color = "FF0000"
            update_money(earnapp_money, money_table)
            update_devices(dev_l, dev_table)

        embed = DiscordEmbed(
            title=title,
            color=color
        )

        embed.set_thumbnail(url=EARNAPP_LOGO)
        embed.add_embed_field(name="Earned", value=f"+{change}$")
        embed.add_embed_field(name="Balance", value=f"{earnapp_money.balance}")
        embed.add_embed_field(name="Lifetime Balance",
                              value=f"{earnapp_money.earnings_total}")
        embed.add_embed_field(name='Traffic and Earnings',
                              value=get_traffic_and_earnings(dev_l, current_devs))
        embed.add_embed_field(name="Total Devices",
                              value=f"{len(dev_l)}")

        embed.set_footer(text=f"Version: 0.0.1.0", icon_url=PAYPAL_ICON)
        embed.set_timestamp()

        webhook.add_embed(embed)
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
