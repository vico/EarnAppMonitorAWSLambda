# -*- encoding: utf8 -*-

import os
from decimal import Decimal
from ipaddress import IPv4Address
from typing import List, Union
from urllib.parse import urljoin
from uuid import UUID
from collections import defaultdict
import boto3
import requests
from discord_webhook import DiscordWebhook, DiscordEmbed
from pydantic import BaseModel, condecimal
from tenacity import retry, wait_fixed, stop_after_attempt, RetryError
from typing_extensions import TypedDict



# Press the green button in the gutter to run the script.
EARNAPP_LOGO = "https://www.androidfreeware.net/img2/com-earnapp.jpg"
PAYPAL_ICON = "https://img.icons8.com/color/64/000000/paypal.png"
WEBHOOK_URL = os.environ['WEBHOOK_URL']
TOKEN = os.environ['TOKEN']
LOCAL = bool(os.environ.get('local', False))

BASE_URL = 'https://earnapp.com/dashboard/api/'
user_data_endpoint = urljoin(BASE_URL, 'user_data')
money_endpoint = urljoin(BASE_URL, 'money')
devices_endpoint = urljoin(BASE_URL, 'devices')
device_endpoint = urljoin(BASE_URL, 'device')
transaction_endpoint = urljoin(BASE_URL, 'transactions')
redeem_endpoint = urljoin(BASE_URL, 'redeem')

header = {
    'cookie': f'auth=1; auth-method=google; oauth-refresh-token={TOKEN}'
}
params = (('appid', 'earnapp_dashboard'),)

if LOCAL:
    dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-1', endpoint_url="http://localhost:8000")
else:
    dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-1')


class RedeemDetails(TypedDict):
    email: str
    payment_method: str
    min_redeem: condecimal(ge=0)


# b'{"multiplier":1,"multiplier_icon":"","multiplier_hint":"","redeem_details":{"email":"tranvinhcuong@gmail.com","payment_method":"paypal.com","min_redeem":2.5},"balance":0.47,"earnings_total":12.32,"ref_bonuses":0,"ref_bonuses_total":0,"promo_bonuses":0,"promo_bonuses_total":0,"referral_part":"10%"}'
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
    title: str
    bw: int
    total_bw: int
    redeem_bw: int
    rate: condecimal(ge=0)
    earned: condecimal(ge=0)
    earned_total: condecimal(ge=0)
    country: str
    ips: List[IPv4Address]


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
            UpdateExpression="set bw=:bw, earned=:earned, earned_total=:et, total_bw=:tb, redeem_bw=:rb, ips=:ips, rate=:r",
            ExpressionAttributeValues={
                ':earned': dev.earned,
                ':et': dev.earned_total,
                ':tb': Decimal(dev.total_bw),
                ':rb': Decimal(dev.redeem_bw),
                ':bw': Decimal(dev.bw),
                ':ips': list(map(lambda x: str(x), dev.ips)),
                ':r': dev.rate
            },
            ReturnValues="UPDATED_NEW"
        )

def get_traffic_and_earnings(dev_l, current_devs) -> str:
    dev_map = {dev.uuid: dev for dev in dev_l}

    bw_usage = defaultdict(int)
    earned_dict = defaultdict(Decimal)

    for dev in current_devs:
        bw_usage[str(dev.ips[0])] += dev_map[dev.uuid].bw - dev.bw
        earned_dict[str(dev.ips[0])] += dev_map[dev.uuid].earned - dev.earned

    return '\n'.join([f'{k: <15}: {v/1024**2: >8.2f}MB|{earned_dict[k]:>5}$' for (k,v) in bw_usage.items()])

def lambda_handler(event, context):
    webhook = DiscordWebhook(url=WEBHOOK_URL)

    try:
        earnapp_money = get_money_data_from_earnapp()
        money_table = dynamodb.Table('Money')
        db_money = get_money_data(earnapp_money.redeem_details['email'], money_table)

        dev_table = dynamodb.Table('Devices')
        dev_l = get_devices_info_from_earnapp()  # get latest devices information from EarnApp API
        current_devs = get_current_devices(dev_table)  # get current information from DynamoDB

        change = earnapp_money.balance - db_money.balance
        if change > 0:
            title = f"Balance Increased [+{change}]"
            color = "03F8C4"
            update_money(earnapp_money, money_table)
            update_devices(dev_l, dev_table)
        else:
            title = "Balance Unchanged!"
            color = "E67E22"

        embed = DiscordEmbed(
            title=title,
            color=color
        )

        embed.set_thumbnail(url=EARNAPP_LOGO)

        embed.add_embed_field(name="Earned", value=f"+{change}$")

        embed.add_embed_field(
            name="Balance", value=f"{earnapp_money.balance}")
        embed.add_embed_field(name="Lifetime Balance",
                              value=f"{earnapp_money.earnings_total}")
        embed.add_embed_field(name='Traffic and Earnings',
                              value=get_traffic_and_earnings(dev_l, current_devs))
        embed.add_embed_field(name="Total Devices",
                              value=f"{len(dev_l)}")

        embed.set_footer(text=f"Version: 0.0.1.0", icon_url=PAYPAL_ICON)

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
