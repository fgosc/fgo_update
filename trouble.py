#!/usr/bin/python3
"""
「現在確認している不具合について」の情報更新をチェックする
"""
import argparse
import logging
from pathlib import Path
import difflib
import configparser
import sys
import json

from bs4 import BeautifulSoup
import requests
from discordwebhook import Discord

logger = logging.getLogger(__name__)
inifile = "fgoupdate.ini"
basedir = Path(__file__).resolve().parent

backup_f = basedir / "info_trouble.html"

LOOP_TIMES = 15
LOOP_SECONDS = 60

# 設定ファイル読み込み
config = configparser.ConfigParser()
configfile = basedir / Path(inifile)
if configfile.exists() is False:
    print("ファイル {} を作成してください".format(inifile),
          file=sys.stderr)
    exit(1)
config.read(configfile)
section1 = 'discord'
webhook_url = config.get(section1, 'webhook')
discord = Discord(url=webhook_url)
webhook_error_url = config.get(section1, 'webhook4error', fallback=webhook_url)
discord_error = Discord(url=webhook_error_url)

trouble_json = "trouble.json"


def troubleDiff(old, new) -> str:
    s = ""
    for i in difflib.context_diff(old, new, fromfile='更新前', tofile='更新後', n=0):
        s += (i)
    return s


def html2dic(content):
    soup = BeautifulSoup(content, "html.parser")
    list_news = soup.select("ul.list_news li")
    news = []
    for list_new in list_news:
        title = list_new.select_one("p.title").get_text()
        url_a = list_new.select_one("a")
        url = url_a.attrs['href']
        if url != "/info/trouble/":
            news.append({"title": title, "url": url})
    return news


def getTrouble():
    """
    ローカルのファイルとネット上のファイルでdiffをとる
    """
    target_url = "https://news.fate-go.jp/trouble/"

    filename = basedir / Path(trouble_json)
    if filename.exists():
        f1 = open(filename, 'r', encoding="UTF-8")
        trouble_prev = json.load(f1)
    else:
        # ダウンロード
        logger.warning("FILE %s don't exists.", filename)
        r = requests.get(target_url)
        if r.status_code != requests.codes.ok:
            logger.critical("ウェブサイトから情報取得できません")
            exit()
        with open(filename, "w", encoding="UTF-8") as savefile:
            json.dump(html2dic(r.content), savefile, ensure_ascii=False)
        logger.critical("JSONファイルが無いので作成しました")
        exit()

    # 情報取得
    r = requests.get(target_url)
    if r.status_code != requests.codes.ok:
        logger.critical("ウェブサイトから情報取得できません")
        exit()
    trouble = html2dic(r.content)

    # 比較
    urls = set(i["url"] for i in trouble) - set(i["url"] for i in trouble_prev)
    for url in urls:
        long_url = "https://news.fate-go.jp" + url
        r2 = requests.get(long_url)
        if r2.status_code != requests.codes.ok:
            logger.critical("ウェブサイトから情報取得できません")
            continue
        soup = BeautifulSoup(r2.content, "html.parser")
        discord.post(username="FGO アップデート",
                     embeds=[{
                              "title": soup.find('title').get_text().replace("  |  Fate/Grand Order 公式サイト", ""),
                              "author": {
                                         "name": "Fate/Grand Order 公式サイト : 不具合更新",
                                        },
                              "url": long_url,
                              "description": soup.find('main').get_text(),
                              "color": 5620992}])
    if len(urls) > 0:
        with open(filename, "w", encoding="UTF-8") as savefile:
            json.dump(trouble, savefile, ensure_ascii=False)
    return len(urls)


if __name__ == '__main__':
    # オプションの解析
    parser = argparse.ArgumentParser(
                description='Post FGO trouble information to Discord'
                )
    # 3. parser.add_argumentで受け取る引数を追加していく
    parser.add_argument('-l', '--loglevel',
                        choices=('debug', 'info'), default='info')

    args = parser.parse_args()    # 引数を解析
    logging.basicConfig(
        level=logging.INFO,
        format='%(name)s <%(filename)s-L%(lineno)s>'
               + ' [%(levelname)s] %(message)s',
    )
    logger.setLevel(args.loglevel.upper())

    getTrouble()
