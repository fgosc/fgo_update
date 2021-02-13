#!/usr/bin/python3
"""
「現在確認している不具合について」の情報更新をチェックする
"""
import argparse
import logging
from pathlib import Path
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
    """
    消えた情報には価値は無いので新規除法だけ出すように変更
    """
    new_set = set(new) - set(old)
    return "\n".join(new_set)


def makeDiffStr() -> int:
    """
    ローカルのファイルとネット上のファイルでdiffをとる

    不具合のカテゴリは次のものがある
    ■現在調査対応している不具合
    (■現在対応中の不具合)
    ■修正済みの不具合
    ■解消済みの不具合
    """
    target_url = "https://news.fate-go.jp/info/trouble/"

    # 新規ファイルをチェック
    r = requests.get(target_url)
    if r.status_code != requests.codes.ok:
        return False
    soup_new = BeautifulSoup(r.content, "html.parser")

    new_titles = soup_new.select("dl.accordion > dt")
    titles = []
    for new_title in new_titles:
        titles.append(new_title.get_text())

    # <dl> タグが閉じてないので <dd>で切り出す
    new_categories = soup_new.select("dl.accordion > dd")
    news = []
    for new_category in new_categories:
        new = []
        p_news = new_category.select("p")
        for p_new in p_news:
            new.append(p_new.get_text())
        news.append(new)

    # ローカルファイルをチェック
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
    olds = []
    for old_category in old_categories:
        old = []
        p_olds = old_category.select("p")
        for p_old in p_olds:
            old.append(p_old.get_text())
        olds.append(old)

    fields = []
    for i, (old, new) in enumerate(zip(olds, news)):
        str_diff = troubleDiff(old, new)

        if len(str_diff) > 0:
            name = titles[i]
            value = "```" + str_diff + "```"
            fields.append({"name": name, "value": value})
    if len(fields) > 0:
        title = soup_new.title.text.replace("  |  Fate/Grand Order 公式サイト", "")
        icon_url = "https://pbs.twimg.com/profile_images/1034364986041163776/tRqcymzd_400x400.jpg"
        discord.post(username="FGO アップデート",
                     embeds=[{
                              "title": title,
                              "author": {
                                         "name": "Fate/Grand Order 公式サイト",
                                         "icon_url": icon_url
                                    },
                              "url": target_url,
                              "fields": fields,
                              "color": 5620992}])
        # ファイルを入れ替え
        with open(backup_f, "wb") as savefile:
            savefile.write(r.content)
        return len(fields)
    # postCount += 1
    return 0


def getInfoTrouble():
    for i in range(LOOP_TIMES):
        if i > 0:
            time.sleep(LOOP_SECONDS)
        if makeDiffStr() > 0:
            break


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
