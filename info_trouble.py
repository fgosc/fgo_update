#!/usr/bin/python3
"""
「現在確認している不具合について」の情報更新をチェックする
"""
import argparse
import logging
from pathlib import Path
import difflib
import time
import configparser
import sys

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


def troubleDiff(old, new) -> str:
    s = ""
    for i in difflib.context_diff(old, new, fromfile='更新前', tofile='更新後', n=0):
        if not (i.startswith("***") or i.startswith("---")):
            s += (i)
    return s


def makeDiffStr() -> bool:
    """
    ローカルのファイルとネット上のファイルでdiffをとる
    """
    target_url = "https://news.fate-go.jp/info/trouble/"
    if backup_f.exists() is False:
        logger.warning("FILE %s don't exists.", backup_f)
        r = requests.get(target_url)
        if r.status_code != requests.codes.ok:
            return False
        with open(backup_f, "wb") as savefile:
            savefile.write(r.content)
        return False

    with open(backup_f, "r", encoding="UTF-8") as f:
        soup_old = BeautifulSoup(f, "html.parser")
    old_categories = soup_old.select("dl.accordion > dd")
    old = []
    p_olds = old_categories[-2].select("p")
    for p_old in p_olds:
        old.append(p_old.get_text())

    r = requests.get(target_url)
    if r.status_code != requests.codes.ok:
        return False
    soup_new = BeautifulSoup(r.content, "html.parser")
    # <dl> タグが閉じてないので <dd>で切り出す
    new_categories = soup_new.select("dl.accordion > dd")
    new = []
    p_news = new_categories[-2].select("p")
    for p_new in p_news:
        new.append(p_new.get_text())

    str_diff = troubleDiff(old, new)
    if len(str_diff) > 0:
        discord.post(username="FGO アップデート",
                     embeds=[{
                              "title": "修正済みの不具合更新",
                              "url": target_url,
                              "description": "```" + str_diff + "```",
                              "color": 5620992}])
        # ファイルを入れ替え
        with open(backup_f, "wb") as savefile:
            savefile.write(r.content)
        return True
    # postCount += 1
    return False


def getInfoTrouble():
    for i in range(LOOP_TIMES):
        if i > 0:
            time.sleep(LOOP_SECONDS)
        if makeDiffStr():
            break
        logger.info("{}回目のループ".format(i + 1))


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

    getInfoTrouble()
