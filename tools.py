# -*- coding: utf-8 -*-
# @File   :tools.py
# @Time   :2025/12/15 17:12
# @Author :admin

from bs4 import BeautifulSoup as bs
from loguru import logger
import requests
import json
import re
import urllib.parse
import os
import sys
from pathlib import Path
import psutil
import logging
from datetime import datetime
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)




def get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))


# 初始化日志
LOG_DIR = get_app_dir() / Path("logs")
LOG_DIR.mkdir(exist_ok=True)
log_file = LOG_DIR / f"app_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()  # 同时输出到控制台
    ]
)
logger = logging.getLogger(__name__)



def read_db_cookie(platform='live', filename='db_cookie.json'):
    db_cookie = {}
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            db_cookie = json.loads(f.read())
            return db_cookie[platform]
    except Exception as e:
        db_cookie = {}
    return db_cookie


def read_html(filename='html.html'):
    html = ''
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            html = f.read()
            return html
    except Exception as e:
        print(f'读取文件失败: {e}')
    return html

def save_html(html, filename='html.html'):
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html)
        print('保存成功')

def parse_douyinlive_html(html):
    soup = bs(html, 'html.parser')
    index = 0
    script_string = ''
    for script in soup.find_all('script'):
        if script.string:
            if 'appStore' in script.string and 'roomStore' in script.string and 'roomInfo' in script.string:
                script_string = script.string
                index += 1
                logger.info(f'index: {index}')
                if script_string:
                    script_string = script_string.strip('self.__pace_f.push([1,').strip('])').split(':', 1)[-1][:-3]
                    script_string = re.sub(r'\\(.)', r'\1', script_string)
                    script_string = re.findall(r'"roomInfo":{"room":(.*?),"roomId":', script_string)
                    if script_string:
                        script_string = script_string[0]
                        try:
                            script_string = urllib.parse.unquote(script_string).replace('u0026', '&')
                            room = json.loads(script_string)
                            return room
                        except Exception as e:
                            logger.info(f'error: {e}')
                    else:
                        logger.info(f'script_string: {script_string}')
                else:
                    logger.info(f'script_string: {script_string}')
    return {}


def get_real_url_DouyinLive(url=None, rid=None):
    room = {}
    if not url:
        url = f'https://live.douyin.com/{rid}'
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'zh-CN,zh;q=0.9',
        'cache-control': 'no-cache',
        'pragma': 'no-cache',
        'priority': 'u=0, i',
        'sec-ch-ua': '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
        'cookie': 'ttwid=1%7C6yQYsoWtfJUAn1a0KBgrcxEp_p1wjByys03l-adQs50%7C1740706178%7Cfe7e5b6e43453758639593d47b07e10d1deccbca284b11856a38b0804e3cf0b0',
    }
    try:
        response = requests.get(url, headers=headers, verify=False)
        logger.info(f'status_code {response.status_code} url: {url}')
        room = parse_douyinlive_html(response.text)
    except Exception as e:
        logger.info(f'error: {e}')
    return room


def get_rtmp_pull(share_url, req_count=1):
    """
    通过分享链接，获取直播拉流地址 （抖音）
    """
    item = {}
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Mobile Safari/537.36'
    }
    if str(share_url).isdigit():
        share_url = f'https://live.douyin.com/{share_url}'
    pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*,]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    link = re.findall(pattern, share_url)[0] if re.findall(pattern, share_url) else None
    logger.info(f'数据库获取并解析后的分享链接 link：{link}')
    if not link:
        return {}
    title = share_url.replace(link, '')
    share_url = link
    logger.info(f'title: {title} share_url: {share_url}')
    if '.flv' in share_url or '.m3u8' in share_url:
        ext_name = share_url.split('?', 1)[0].strip('.flv').strip('.m3u8')
        if str(ext_name).endswith('ld') or str(ext_name).endswith('sd1000'):
            item['sd1'] = share_url
        elif str(ext_name).endswith('sd') or str(ext_name).endswith('hd2000'):
            item['sd2'] = share_url
        elif str(ext_name).endswith('hd'):
            item['hd1'] = share_url
        elif str(ext_name).endswith('hd4000'):
            item['super'] = share_url
        elif str(ext_name).endswith('or4'):
            item['FULL_HD1'] = share_url
        else:
            item['default'] = share_url
        return item
    elif 'douyin' in share_url:
        rid = re.findall(r'live.douyin.com/(\d+)?', share_url)
        if rid:
            logger.info(f'rid: {rid}')
            rid = rid[0]
            room = get_real_url_DouyinLive(url=share_url, rid=rid)
            status = room.get('status', 'empty')
            if status == 'empty':
                living = 'empty'
                item['error'] = 'empty'
            elif status == 4:
                living = 0
            else:
                living = 1
            item['living'] = living
            item['title'] = room.get('title') or title
            item['room_id'] = room.get('id_str') or rid
            stream_url = room.get('stream_url', {})
            if stream_url:
                item['rtmp_pull_url'] = stream_url.get('rtmp_pull_url')
                item['sd1'] = stream_url.get('flv_pull_url', {}).get('SD1')
                item['sd2'] = stream_url.get('flv_pull_url', {}).get('SD2')
                item['hd1'] = stream_url.get('flv_pull_url', {}).get('HD1')
                item['FULL_HD1'] = stream_url.get('flv_pull_url', {}).get('FULL_HD1')
                item['hls_pull_url'] = stream_url.get('hls_pull_url')
        else:
            session = requests.session()
            try:
                res = session.get(share_url, verify=False, headers=headers)
                if res.status_code != 200:
                    return {}
            except Exception as e:
                error = f'{e}'
                logger.info(
                    f'get_rtmp_pull share_url: {share_url} 请求失败：{error}')
                if isinstance(error, str) and 'Max retries exceeded with url' in error:
                    item['error'] = 'max_retries_exceeded_407' if '407' in error else 'max_retries_exceeded'
                return item
            try:
                redict_url = res.url
                room_id = re.findall(r'/reflow/(\d+)?', redict_url)
                sec_user_id = re.findall(r'/reflow/.*?&sec_user_id=(.*?)&', redict_url)
                logger.info(f'===> 1: redict_url: {redict_url}')
                logger.info(f'room_id: {room_id} sec_user_id: {sec_user_id} share_url: {share_url}')
                if room_id:
                    room_id = room_id[0]
                    sec_user_id = sec_user_id[0] if sec_user_id else ''

                    msToken = 'v6WanzZx7tQmhaPHkkLzZ_TaRqNd4kKjvP55YnErMHp5ZHhXr1_z1mGqhhAu-X7tKBFdacH-1RwvbIqqbX_U6BaGs5yPxIYwM83G2gwFja8FGHNhv5bJZxI4VcMqvh0='
                    X_Bogus =  'DFSzKwVO3yGAN9R8Skhqql9WX7J7'
                    verifyFp = 'verify_lblvbnix_rblEdgn8_LQBK_4Ae2_AQIG_EsEO99OYKQfR'
                    api_url = f'https://webcast.amemv.com/webcast/room/reflow/info/?verifyFp={verifyFp}&type_id=0&live_id=1&room_id={room_id}&sec_user_id=&app_id=1128&msToken={msToken}&X-Bogus={X_Bogus}'

                    for i in range(req_count):
                        try:
                            logger.info(
                                f'share_url: {share_url} 第{i + 1}次请求 api_url: {api_url}')
                            res = session.get(api_url, verify=False, headers=headers)
                            if res.text:
                                break
                        except Exception as e:
                            logger.info(e)
                    Bdturing_Verify = res.headers.get('Bdturing-Verify') or res.headers.get('X-Vc-Bdturing-Parameters')
                    if not res.text or Bdturing_Verify:
                        # item['error'] = 'verify'
                        verifyFp = json.loads(Bdturing_Verify).get('fp') if Bdturing_Verify else ''
                        logger.info(
                            f'share_url: {share_url} room_id: {room_id} Bdturing_Verify: {verifyFp} result:{res.text}')

                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 Safari/537.36', }
                        default_cookie = 'n_mh=XK1o04PTRKaJrX31mB4DX2LQOUHNGQ6_8bBYhoc6zlE; xgplayer_user_id=764506889774; ttcid=c1e8c95b45df4d7881aae05ddd11603e46; _ga=GA1.1.2050762537.1652432241; ttwid=1%7Cdra7AmQq6A54nLquHPjQS2iTuC6U4eT5cF3XIGxJTn0%7C1652432243%7Cc51a943c1bad648a46a7034de183503482aed8d38d5dd4eaa61eb9eae19012d8; _ga_PZ1MHZSCJ7=GS1.1.1652432241.1.1.1652432250.0; sso_uid_tt=446b5d14c97a32f6d775a8c5081bee7c; sso_uid_tt_ss=446b5d14c97a32f6d775a8c5081bee7c; toutiao_sso_user=a351decb826db090e898f196ae1b88c5; toutiao_sso_user_ss=a351decb826db090e898f196ae1b88c5; SEARCH_RESULT_LIST_TYPE=%22single%22; home_can_add_dy_2_desktop=%220%22; s_v_web_id=verify_l7l856xc_gRAtlPOc_B3lE_4HGa_9SOe_F5aMlqbNMi1P; passport_csrf_token=09e06ae401a69fbb754886b9f8d137d5; passport_csrf_token_default=09e06ae401a69fbb754886b9f8d137d5; sid_ucp_sso_v1=1.0.0-KGYxZTMxMWE0ZmZjM2IyOGI5MWM2ZGEwM2E3MWNlODFlMjljNzY4NDMKHQj7-MG_jwIQg9XVmAYY7zEgDDCCjavPBTgGQPQHGgJscSIgYTM1MWRlY2I4MjZkYjA5MGU4OThmMTk2YWUxYjg4YzU; ssid_ucp_sso_v1=1.0.0-KGYxZTMxMWE0ZmZjM2IyOGI5MWM2ZGEwM2E3MWNlODFlMjljNzY4NDMKHQj7-MG_jwIQg9XVmAYY7zEgDDCCjavPBTgGQPQHGgJscSIgYTM1MWRlY2I4MjZkYjA5MGU4OThmMTk2YWUxYjg4YzU; passport_auth_status=6f50b645c4203a03ae06682a708a0b9c%2C; passport_auth_status_ss=6f50b645c4203a03ae06682a708a0b9c%2C; uid_tt=6522d66b46432f3dcbaf3777b8631ffa; uid_tt_ss=6522d66b46432f3dcbaf3777b8631ffa; sid_tt=af4de057bdeec58e97b5b5bc02d67835; sessionid=af4de057bdeec58e97b5b5bc02d67835; sessionid_ss=af4de057bdeec58e97b5b5bc02d67835; sid_guard=af4de057bdeec58e97b5b5bc02d67835%7C1662425675%7C5106232%7CFri%2C+04-Nov-2022+03%3A18%3A27+GMT; sid_ucp_v1=1.0.0-KDVlNGE3YzVmZjJiYWZkNTg3OWQzY2JmNDMyZTY1N2UzYTMwNjQxY2YKFwj7-MG_jwIQy7TamAYY7zEgDDgGQPQHGgJscSIgYWY0ZGUwNTdiZGVlYzU4ZTk3YjViNWJjMDJkNjc4MzU; ssid_ucp_v1=1.0.0-KDVlNGE3YzVmZjJiYWZkNTg3OWQzY2JmNDMyZTY1N2UzYTMwNjQxY2YKFwj7-MG_jwIQy7TamAYY7zEgDDgGQPQHGgJscSIgYWY0ZGUwNTdiZGVlYzU4ZTk3YjViNWJjMDJkNjc4MzU; csrf_session_id=d4bfad3988bdc781fc0172626ea2d12b; passport_fe_beating_status=true; odin_tt=ab4d1b802c4ad60ec92425937dc32c5a9e4ba4113642d4d9053b805a561f7d3e6d385a6fe39385e4e1e80ca2030773f6; download_guide=%223%2F20220930%22; FOLLOW_NUMBER_YELLOW_POINT_INFO=%22MS4wLjABAAAAPgc1if5_Uap-mnitkVf1RBnSgFW65l8iBdN9uSuGs7A%2F1664553600000%2F0%2F1664525562968%2F0%22; strategyABtestKey=1664781345.498; FOLLOW_LIVE_POINT_INFO=%22MS4wLjABAAAAPgc1if5_Uap-mnitkVf1RBnSgFW65l8iBdN9uSuGs7A%2F1664812800000%2F0%2F1664781345883%2F0%22; __ac_nonce=0633bec1900ce4747bf40; __ac_signature=_02B4Z6wo00f01KalNPgAAIDAJqfOuBZBOJCmgTBAAEqXocXkrufi5m4jzb8mA30eLdae.O48kKKOowftJ6yjNJOdVKjvMCMUUyZ022g-m.90Ns.jaw-T-t.LjwsPdq7KJJX.uhFqt1OfQNcr39; live_can_add_dy_2_desktop=%221%22; msToken=Afrq37AbWiJE7srsO9EcdcGz56eO_XlJrQ6zNPoYqLKen0HiY_BSZ2G8sTJzLiXDnPegIhdwcc-MeN6D5tIxvWJ6KToihQqb_fUXSJWthQmebBjR1FBF9O5R_7KzOjetPQ==; msToken=XWjqMT7QHLOJwoXro6agOKj9JaqZtv1zBMMHLmxLXhjmxo__xiGjAejtDOadYA9G3-RZuWObTCGqvUPevgAIZ7tumh7pNPszWIAUdRkCj3MUFcJcXruxI-s1340Bs_anYA==; tt_scid=AS-dCLxUaTfH0EifTy8AfajB0auBnMOMy.EZemsUxuwruZ5q7hO0N0cEyHwtoICzbbde'

                        db_cookie = read_db_cookie(platform='live')
                        headers['Cookie'] = db_cookie.get('cookie') if db_cookie.get('cookie') else default_cookie
                        res = requests.get(redict_url, verify=False, headers=headers)
                        redict_url = res.url
                        room_id = re.findall(r'live.douyin.com/(\d+)', redict_url)
                        logger.info(f'===> 2: redict_url: {redict_url}')
                        logger.info(f'room_id: {room_id} ')
                        if room_id:
                            api_url = f'https://live.douyin.com/webcast/web/enter/?aid=6383&live_id=1&device_platform=web&language=zh-CN&enter_from=web_share_link&cookie_enabled=true&screen_width=1920&screen_height=1080&browser_language=zh-CN&browser_platform=Win32&browser_name=Chrome&browser_version=93.0.4577.82&web_rid={room_id}'

                            default_cookie = 'ttwid=1%7C6XDhg78oBOJLyvJh2-Y3leE6fkNfkuamW6LVAmKFWZA%7C1663726177%7Cab70d3000fe5d88b775abe7419ac9ce2b3c584f69ee501cc871b74d3e77de687; passport_csrf_token=baf8fcc514e3d069a8ca148bd3ba317d; passport_csrf_token_default=baf8fcc514e3d069a8ca148bd3ba317d; xgplayer_user_id=923629786351; csrf_session_id=8af6b5de26c0eb447c5601c224b80813; odin_tt=b2669777338edd61aea185a50ca6516cf1eb0566f331c5f534c43e95b47824da9c56c2701598dce2d58a89eb110e631b7fda93b7311945b1e9352c13224e41f3ea56df5077522a8ea32c009b2c763489; __ac_signature=_02B4Z6wo00f01qg6z4QAAIDCKDg1xFz3tMqoGssAAMlBee; ttcid=364d98b80e1945649189b0cca02bd25617; tt_scid=vlYbA4imSaL.GDF4EL7JHjLT4yQB0L2A24hLXrxIvemzCwQ5jnxND6TQ58OrR9cSc2a7; live_can_add_dy_2_desktop=%221%22; msToken=rLykL3awoff_rfD_6FzVogI-gYg7LMrWEMoFHcTogRNYZKz68vMGCghyuFpY97Er_xCKJVMHzYHhzPW-LkeFnr6JU9UA0qsCGlxnl6Ip1kH7eryIth1v6dMki69MPsLd; msToken=vMM8lnQOURymkkQ0ji_A_9tZJC8z96tYRQaiDC4bgc2weIHObwcMjO7dcxArHIe9w-6uW9JuQXy05uTrUpBKzzSVXsFgWRXskHPIz_9AYtnj2655HPC3sn32z2vrfz1P'
                            db_cookie = read_db_cookie(platform='www')
                            headers['Cookie'] = db_cookie.get('cookie') if db_cookie.get('cookie') else default_cookie
                            res = requests.get(api_url, verify=False, headers=headers)
                            if res.text:
                                data = res.json()
                                room = data.get('data', {}).get('data', [])
                                if room and isinstance(room, list):
                                    room = room[0]
                                    status = room.get('status', 'empty')
                                    if status == 'empty':
                                        living = 'empty'
                                        item['error'] = 'empty'
                                    elif status == 4:
                                        living = 0
                                    else:
                                        living = 1
                                    item['living'] = living
                                    item['title'] = room.get('title') or title
                                    item['room_id'] = room.get('id_str') or room_id
                                    stream_url = room.get('stream_url', {})
                                    if stream_url:
                                        item['rtmp_pull_url'] = stream_url.get('rtmp_pull_url')
                                        item['sd1'] = stream_url.get('flv_pull_url', {}).get('SD1')
                                        item['sd2'] = stream_url.get('flv_pull_url', {}).get('SD2')
                                        item['hd1'] = stream_url.get('flv_pull_url', {}).get('HD1')
                                        item['FULL_HD1'] = stream_url.get('flv_pull_url', {}).get('FULL_HD1')
                                        item['hls_pull_url'] = stream_url.get('hls_pull_url')
                                else:
                                    logger.info(
                                        f'share_url: {share_url} room_id: {room_id} api_url: {api_url} result:{res.text}')

                                    item['error'] = 'verify'
                            else:
                                logger.info(
                                    f'share_url: {share_url} room_id: {room_id} api_url: {api_url} result:{res.text}')

                                item['error'] = 'verify'
                        else:
                            item['error'] = 'verify'
                    else:
                        data = res.json()
                        room = data.get('data', {}).get('room', {})
                        status = room.get('status', 'empty')
                        if status == 'empty':
                            living = 'empty'
                            item['error'] = 'empty'
                        elif status == 4:
                            living = 0
                        else:
                            living = 1
                        item['living'] = living
                        item['title'] = room.get('title') or title
                        item['room_id'] = room.get('id_str') or room_id
                        stream_url = room.get('stream_url', {})
                        if stream_url:
                            item['rtmp_pull_url'] = stream_url.get('rtmp_pull_url')
                            item['sd1'] = stream_url.get('flv_pull_url', {}).get('SD1')
                            item['sd2'] = stream_url.get('flv_pull_url', {}).get('SD2')
                            item['hd1'] = stream_url.get('flv_pull_url', {}).get('HD1')
                            item['FULL_HD1'] = stream_url.get('flv_pull_url', {}).get('FULL_HD1')
                            item['hls_pull_url'] = stream_url.get('hls_pull_url')
                else:
                    soup = bs(res.text, 'html.parser')
                    RENDER_DATA = soup.select('#RENDER_DATA')
                    script_str = soup.find('head').find_all('script')[-1]
                    s = script_str.prettify()
                    s = s.rstrip('</script>')
                    s = s.split('window.__INIT_PROPS__ =')[-1]
                    dic = json.loads(s)
                    room = dic.get('/webcast/reflow/:id', {}).get('room', {})
                    status = room.get('status', 'empty')
                    if status == 'empty':
                        living = 'empty'
                        item['error'] = 'empty'
                    elif status == 4:
                        living = 0
                    else:
                        living = 1
                    item['living'] = living
                    item['title'] = room.get('title') or title
                    item['room_id'] = room.get('id_str')
                    stream_url = room.get('stream_url', {})
                    if stream_url:
                        item['rtmp_pull_url'] = stream_url.get('rtmp_pull_url')
                        item['sd1'] = stream_url.get('flv_pull_url', {}).get('SD1')
                        item['sd2'] = stream_url.get('flv_pull_url', {}).get('SD2')
                        item['hd1'] = stream_url.get('flv_pull_url', {}).get('HD1')
                        item['FULL_HD1'] = stream_url.get('flv_pull_url', {}).get('FULL_HD1')
                        item['hls_pull_url'] = stream_url.get('hls_pull_url')

            except Exception as e:
                logger.info(f'share_url: {share_url} 抖音解析失败: {e}')
    return item



def get_stream_qualities(share_url):
    data = {'code': 0, 'msg': 'success', 'data': {}}
    result = get_rtmp_pull(share_url)
    if not result:
        data['code'] = 10001
        data['msg'] = '请求失败！检查链接是否有误'
    else:
        data['data']['title'] = result.get('title') or ''
        data['data']['room_id'] = result.get('room_id') or ''
        if result.get('living') == 0:
            data['code'] = 10001
            data['msg'] = '该直播已关播！'
        elif result.get('living') == 'empty':
            data['code'] = 10001
            data['msg'] = '请求失败，检查链接是否失效！'
        elif result.get('cookie'):
            data['code'] = 10001
            data['msg'] = data.get('cookie')
        elif result.get('error') == 'max_retries_exceeded':
            data['code'] = 10001
            data['msg'] = '请求频繁，稍后重试！'
        elif result.get('error') == 'max_retries_exceeded_407':
            data['code'] = 10001
            data['msg'] = '请求失败，检查代理是否过期！'
        elif result.get('error') == 'link_error':
            data['code'] = 10001
            data['msg'] = '请求失败！检查链接是否有误'
        elif result.get('error') == 'verify':
            data['code'] = 10001
            data['msg'] = 'verify 请求频繁，稍后重试！'
        else:
            qualities_list = []
            for k, v in result.items():
                dic = {}
                if k == 'sd1':
                    dic['name'] = '标清'
                    dic['playUrl'] = v
                    dic['type'] = 'ld'
                if k == 'sd2':
                    dic['name'] = '高清'
                    dic['playUrl'] = v
                    dic['type'] = 'sd'
                if k == 'hd1':
                    dic['name'] = '超清'
                    dic['playUrl'] = v
                    dic['type'] = 'hd'
                if k == 'FULL_HD1':
                    dic['name'] = '蓝光'
                    dic['playUrl'] = v
                    dic['type'] = 'uhd'
                if k == 'super':
                    dic['name'] = '蓝光4M'
                    dic['playUrl'] = v
                    dic['type'] = 'bd4M'
                if k == 'blueray':
                    dic['name'] = '蓝光8M'
                    dic['playUrl'] = v
                    dic['type'] = 'bd8M'
                if k == 'default':
                    dic['name'] = '默认'
                    dic['playUrl'] = v
                    dic['type'] = 'default'
                if dic:
                    qualities_list.append(dic)

            data['qualities'] = qualities_list

    return data






