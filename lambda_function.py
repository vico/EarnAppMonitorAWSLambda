# -*- encoding: utf8 -*-

from discord_webhook import DiscordWebhook, DiscordEmbed
import os
from pyEarnapp import EarnApp
from tenacity import retry, wait_fixed, stop_after_attempt, RetryError

# Press the green button in the gutter to run the script.
EARNAPP_LOGO = "https://www.androidfreeware.net/img2/com-earnapp.jpg"
PAYPAL_ICON = "https://img.icons8.com/color/64/000000/paypal.png"
WEBHOOK_URL= os.environ['WEBHOOK_URL']
TOKEN = os.environ['TOKEN']

@retry(wait=wait_fixed(30), stop=stop_after_attempt(5))
def get_earnapp_info():
    api = EarnApp(TOKEN)
    user_data = api.get_user_data()
    earnings_info = api.get_earning_info()
    devices_info = api.get_devices_info()
    transaction_info = api.get_transaction_info()
    return {
        'user_data': user_data,
        'earnings_info': earnings_info,
        'devices_info': devices_info,
        'transaction_info': transaction_info
    }


def lambda_handler(event, context):

    webhook = DiscordWebhook(url=WEBHOOK_URL)

    try:
        info = get_earnapp_info()

        embed = DiscordEmbed(
            title="Earning Update 🤖",
            description="Earnapp Earning Monitor has been started.",
            color="FFFFFF"
        )

        embed.set_thumbnail(url=EARNAPP_LOGO)

        embed.add_embed_field(name="Username", value=f"{info['user_data'].name}")
        embed.add_embed_field(
            name="Multiplier", value=f"{info['earnings_info'].multiplier}")
        embed.add_embed_field(
            name="Balance", value=f"{info['earnings_info'].balance}")
        embed.add_embed_field(name="Lifetime Balance",
                              value=f"{info['earnings_info'].earnings_total}")
        embed.add_embed_field(name="Total Devices",
                              value=f"{info['devices_info'].total_devices}")
        embed.add_embed_field(name="Banned Devices",
                              value=f"{info['devices_info'].banned_devices}")
        embed.add_embed_field(
            name="Devices",
            value=f"{info['devices_info'].windows_devices} Windows | {info['devices_info'].linux_devices} Linux | {info['devices_info'].other_devices} Others",
            inline=False)
        embed.add_embed_field(name="Bugs?",
                              value=f"[Contact Devs.](https://github.com/vico/EarnAppMonitorAWSLambda/issues)")

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


