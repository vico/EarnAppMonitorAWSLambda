from decimal import Decimal

from dotenv import load_dotenv

load_dotenv()

from src.lambda_function import Device


def test_init_device_from_earnapp():
    # data got from EarnApp Dashboard (after requests.json())
    res_data1 = {'uuid': 'sdk-node-31eb47c5d15849e5917a8028eee266cb',
                 'appid': 'node_earnapp.com',
                 'title': 'middle',
                 'bw': 2340880908,
                 'total_bw': 7545667030,
                 'redeem_bw': 5204786122,
                 'rate': '$0.25/GB',
                 'earned': 0.54,
                 'earned_total': 1.78,
                 'country': 'jp',
                 'ips': ['218.225.136.137']}

    try:
        _ = Device(**res_data1)
    except Exception as exc:
        assert False, f'Exception is raised with initialization Device: {exc}'

def test_init_device_from_dynamodb():
    # data got from DynamoDB
    res_data2 = {'country': 'jp',
                 'earned': Decimal('0.06'),
                 'redeem_bw': Decimal('2607420414'),
                 'bw': Decimal('264677198'),
                 'rate': Decimal('0.25'),
                 'appid': 'node_earnapp.com',
                 'total_bw': Decimal('2872097612'),
                 'title': 'middle',
                 'uuid': 'sdk-node-31eb47c5d15849e5917a8028eee266cb',
                 'ips': ['222.224.148.183'],
                 'earned_total': Decimal('0.69')}
    try:
        _ = Device(**res_data2)
    except Exception as exc:
        assert False, f'Exception is raised with initialization Device: {exc}'