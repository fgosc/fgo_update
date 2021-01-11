#!/usr/bin/python3
import sys
import json
import time
from datetime import datetime
import argparse
import logging
from pathlib import Path
import configparser

import requests

logger = logging.getLogger(__name__)

inifile = "fgoupdate.ini"
basedir = Path(__file__).resolve().parent

# 設定ファイル読み込み
config = configparser.ConfigParser()
configfile = basedir / Path(inifile)
if configfile.exists() is False:
    print("ファイル {} を作成してください".format(inifile), file=sys.stderr)
    sys.exit(1)
config.read(configfile)
section1 = 'discord'
webhook_url = config.get(section1, 'webhook')

section2 = 'fgodata'
repo = config.get(section2, 'repository')
fgodata = repo.replace("https://github.com/", "").replace(".git", "")

sha_json = "github_sha.json"
data_json = "fgoupdate.json"
sha_url = "https://api.github.com/repos/" + fgodata + "/git/matching-refs/heads/master"
mstver_url = "https://raw.githubusercontent.com/" + fgodata + "/master/mstver.json"
mstQuest_url = "https://raw.githubusercontent.com/" + fgodata + "/master/JP_tables/quest/mstQuest.json"
mstQuestInfo_url = "https://raw.githubusercontent.com/" + fgodata + "/master/JP_tables/quest/viewQuestInfo.json"
mstQuestPhase_url = "https://raw.githubusercontent.com/" + fgodata + "/master/JP_tables/quest/mstQuestPhase.json"
mstEventMission_url = "https://raw.githubusercontent.com/" + fgodata + "/master/JP_tables/event/mstEventMission.json"
mstEvent_url = "https://raw.githubusercontent.com/" + fgodata + "/master/JP_tables/event/mstEvent.json"
mstShop_url = "https://raw.githubusercontent.com/" + fgodata + "/master/JP_tables/shop/mstShop.json"


def list2class(enemy):
    """
    リスト内のクラスを省略表記に
    """
    enemy_dic = {
                 1: "剣", 2: "弓", 3: "槍", 4: "騎", 5: "術", 6: "殺", 7: "狂",
                 8: "盾", 9: "裁", 10: "分", 11: "讐", 23: "月", 25: "降"
                 }
    out = ""
    for e in enemy:
        out += enemy_dic[e]
    return out


def check_update():
    headers = {"Accept": "application/vnd.github.v3+json"}
    resp = requests.get(sha_url, headers=headers)
    sha = resp.json()[0]["object"]["sha"]
    if resp.status_code != requests.codes.ok:
        logger.warning("GitHub return status code: %d", resp.status_code)
        return False
    filename = basedir / Path(sha_json)
    if filename.exists():
        f1 = open(filename, 'r')
        sha_prev = json.load(f1)["sha"]
    else:
        sha_prev = ""
    logger.debug("sha: %s", sha)
    logger.debug("sha_prev: %s", sha_prev)
    if sha != sha_prev:
        f2 = open(filename, 'w')
        json.dump({"sha": sha}, f2)
        return True
    return False


def check_datavar(main_data):
    """
    アプリバージョンとデータバージョンをチェックする
    """
    prev_mstver = main_data["mstver"]
    r_get = requests.get(mstver_url)
    mstver = r_get.json()
    logger.debug("prev_dateVar: %s", prev_mstver["dateVer"])
    logger.debug("dateVar: %s", mstver["dateVer"])
    if prev_mstver["dateVer"] != mstver["dateVer"]:
        main_content = {
                        "username": "FGO アップデート",
                        "embeds": [{
                                "title": "データ更新",
                                "description": "Version: " + str(mstver["appVer"]) + " DataVer: " + str(mstver["dataVer"]),
                                "color": 5620992
                                    }]
                        }

        requests.post(webhook_url, json.dumps(main_content), headers={'Content-Type': 'application/json'})
    return {"mstver": mstver}


def check_quests(main_data):
    """
    クエストをチェックする
    """
    r_get1 = requests.get(mstQuest_url)

    mstquest = main_data["mstquest"]
    logger.debug("mstquest: %s", mstquest)
    mstQuest_list = [q for q in r_get1.json() if q["id"] not in mstquest]

    r_get2 = requests.get(mstQuestInfo_url)
    mstQuestInfo_list = r_get2.json()
    r_get3 = requests.get(mstQuestPhase_url)
    mstQuestPhase_list = r_get3.json()
    questId2classIds = {q["questId"]: q["classIds"]
                        for q in mstQuestPhase_list}
    q_list = []
    fq_list = []
    for quest in mstQuest_list:
        if not (93000000 < quest["id"] < 100000000):
            continue
        if "種火集め" in quest["name"] or "宝物庫" in quest["name"] \
           or "修練場" in quest["name"]:
            continue
        if quest["closedAt"] == 1901199599:
            continue
        for q in mstQuestInfo_list:
            if q["questId"] == quest["id"]:
                enemy = questId2classIds[quest["id"]]
                if quest["id"] > 94000000:
                    q_list.append([quest["id"], quest["name"], 'Lv' + quest["recommendLv"], list2class(enemy)])
                else:
                    fq_list.append([quest["id"], quest["name"], 'Lv' + quest["recommendLv"], list2class(enemy)])
                break
    logger.debug(q_list)
    logger.debug(fq_list)
    output = ""
    for q in q_list:
        # すでにデータベースにあった場合加えない
        s = ','.join([str(n) for n in q])
        output += s + '\n'
        mstquest.append(q[0])

    if output != "":
        quest_content = {
                        "username": "FGO アップデート",
                        "embeds": [{
                                "title": "イベントクエスト更新",
                                "description": output,
                                "color": 5620992
                                    }]
                        }
        requests.post(webhook_url,
                      json.dumps(quest_content),
                      headers={'Content-Type': 'application/json'})
    output = ""
    for q in fq_list:
        # すでにデータベースにあった場合加えない
        s = ','.join([str(n) for n in q])
        output += s + '\n'
        mstquest.append(q[0])

    if output != "":
        quest_content = {
                        "username": "FGO アップデート",
                        "embeds": [{
                                "title": "恒常フリークエスト更新",
                                "description": output,
                                "color": 5620992
                                    }]
                        }
        requests.post(webhook_url,
                      json.dumps(quest_content),
                      headers={'Content-Type': 'application/json'})
    return {"mstquest": mstquest}


def check_mastermissions(mstEventMission_list):
    """
    マスターミッションをチェックする
    """
    if len(mstEventMission_list) != 0:
        mission_content = {
                        "username": "FGO アップデート",
                        "embeds": [{
                                "title": "マスターミッション(ウィークリー)更新",
                                "fields": [
                                    {
                                        "name": "日時",
                                        "value": '```開始 | ' + str(datetime.fromtimestamp(mstEventMission_list[0]["startedAt"])) + '\n終了 | ' + str(datetime.fromtimestamp(mstEventMission_list[0]["endedAt"])) + '```'
                                    }, {
                                        "name": "ミッション",
                                        "value": '\n'.join(['- ' + n["detail"] for n in mstEventMission_list])
                                    }
                                ],
                                "color": 5620992
                                    }]
                        }
        requests.post(webhook_url,
                      json.dumps(mission_content),
                      headers={'Content-Type': 'application/json'})


def check_eventmissions(mstEventMissionLimited_list):
    """
    イベントミッションをチェックする
    """
    if len(mstEventMissionLimited_list) != 0:
        limitedMission_content = {
                        "username": "FGO アップデート",
                        "embeds": [{
                                "title": "限定ミッション更新",
                                "fields": [
                                    {
                                        "name": "日時",
                                        "value": '```開始 | ' + str(datetime.fromtimestamp(mstEventMissionLimited_list[0]["startedAt"])) + '\n終了 | ' + str(datetime.fromtimestamp(mstEventMissionLimited_list[0]["endedAt"])) + '```'
                                    }, {
                                        "name": "ミッション",
                                        "value": '\n'.join(['- ' + n["detail"] for n in mstEventMissionLimited_list])
                                    }
                                ],
                                "color": 5620992
                                    }]
                        }
        requests.post(webhook_url,
                      json.dumps(limitedMission_content),
                      headers={'Content-Type': 'application/json'})


def check_dailymissions(mstEventMissionDaily_list):
    """
    デイリーミッションをチェックする
    """
    if len(mstEventMissionDaily_list) != 0:
        dailyMission_content = {
                        "username": "FGO アップデート",
                        "embeds": [{
                                "title": "ミッション(デイリー)更新",
                                "fields": [
                                    {
                                        "name": "日時",
                                        "value": '```開始 | ' + str(datetime.fromtimestamp(mstEventMissionDaily_list[0]["startedAt"])) + '\n終了 | ' + str(datetime.fromtimestamp(mstEventMissionDaily_list[0]["endedAt"])) + '```'
                                    }, {
                                        "name": "ミッション",
                                        "value": '\n'.join(['- ' + n["detail"] for n in mstEventMissionDaily_list])
                                    }
                                ],
                                "color": 5620992
                                    }]
                        }
        requests.post(webhook_url,
                      json.dumps(dailyMission_content),
                      headers={'Content-Type': 'application/json'})


def check_missions(main_data):
    """
    ミッションをチェックする
    """
    r_get4 = requests.get(mstEventMission_url)
    mstmission = main_data["mstmission"]

    mstEventMission_list = [m for m in r_get4.json()
                            if m["type"] == 2
                            and m["endedAt"] > time.time()
                            and m["id"] not in mstmission]
    mstEventMissionLimited_list = [m for m in r_get4.json()
                                   if m["type"] == 6
                                   and m["endedAt"] > time.time()
                                   and m["id"] not in mstmission]
    mstEventMissionDaily_list = [m for m in r_get4.json()
                                 if m["type"] == 3
                                 and m["endedAt"] > time.time()
                                 and m["id"] not in mstmission]

    check_mastermissions(mstEventMission_list)
    check_eventmissions(mstEventMissionLimited_list)
    check_dailymissions(mstEventMissionDaily_list)
    m1 = [m["id"] for m in mstEventMission_list]
    m2 = [m["id"] for m in mstEventMissionLimited_list]
    m3 = [m["id"] for m in mstEventMissionDaily_list]
    return {"mstmission": mstmission + m1 + m2 + m3}


def check_event(main_data):
    """
    イベント・キャンペーンをチェックする
    終了日時はそれぞれ異なるので煩雑になるため表記しないこととする
    """
    r_get = requests.get(mstEvent_url)
    mstevent = main_data["mstevent"]
    logger.debug("mstevent: %s", mstevent)
    mstEvent_list = [m for m in r_get.json()
                     if time.time() < m["endedAt"] < 1893423600
                     and m["id"] not in mstevent]
    # if len(mstEvent_list) != 0:
    for event in mstEvent_list:
        logger.debug(event["type"])
        if event["type"] == 12:
            title = "イベント・クエスト"
        else:
            title = "キャンペーン"

        event_content = {
                        "username": "FGO アップデート",
                        "embeds": [{
                                "title": title + "更新",
                                "fields": [
                                    {
                                        "name": "日時",
                                        "value": '```開始 | ' + str(datetime.fromtimestamp(event["startedAt"])) + '\n終了 | ' + str(datetime.fromtimestamp(event["endedAt"])) + '```'
                                    }, {
                                        "name": title,
                                        "value": event["detail"]
                                    }
                                ],
                                "color": 5620992
                                    }]
                        }
        requests.post(webhook_url,
                      json.dumps(event_content),
                      headers={'Content-Type': 'application/json'})
    for event in mstEvent_list:
        mstevent.append(event["id"])
    return {"mstevent": mstevent}


def output_shop(shop_list, shopname):
    """
    ショップデータを出力する
    """
    if len(shop_list) != 0:
        shop_content = {
                        "username": "FGO アップデート",
                        "embeds": [{
                                "title": shopname + "更新",
                                "fields": [
                                    {
                                        "name": "内容",
                                        "value": '\n'.join(['- ' + n["name"] for n in shop_list])
                                    }
                                ],
                                "color": 5620992
                                    }]
                        }
        requests.post(webhook_url,
                      json.dumps(shop_content),
                      headers={'Content-Type': 'application/json'})


def check_shop(main_data):
    """
    ショップをチェックする
    1 イベント限定ショップ
    2 マナプリズム
    3 レアプリズム
    8 サウンドプレイヤー
    """
    r_get = requests.get(mstShop_url)
    mstshop = main_data["mstshop"]
    logger.debug("mstshop: %s", mstshop)
    eventShop_list = [m for m in r_get.json()
                      if m["shopType"] == 1
                      and time.time() < m["closedAt"] < 1893423600
                      and m["id"] not in mstshop]
    logger.debug("eventShop_list: %s", eventShop_list)
    manaShop_list = [m for m in r_get.json()
                     if m["shopType"] == 2
                     and m["openedAt"] >= 1609426800
                     and time.time() < m["closedAt"]
                     and m["id"] not in mstshop]
    logger.debug("manaShop_list: %s", manaShop_list)
    rareShop_list = [m for m in r_get.json()
                     if m["shopType"] == 3
                     and m["openedAt"] >= 1607958000
                     and time.time() < m["closedAt"]
                     and m["id"] not in mstshop]
    # 1594717200はこのソフトウェア公開直前の解放
    logger.debug("rareShop_list: %s", rareShop_list)
    soundPayer_list = [m for m in r_get.json()
                       if m["shopType"] == 8
                       and m["openedAt"] >= 1594717200
                       and m["id"] not in mstshop]
    logger.debug("soundPayer_list: %s", soundPayer_list)
    output_shop(eventShop_list, "イベントショップ")
    output_shop(manaShop_list, "マナプリズム交換")
    output_shop(rareShop_list, "レアプリズム交換")
    output_shop(soundPayer_list, "サウンドプレイヤー")
    m1 = [m["id"] for m in eventShop_list]
    m2 = [m["id"] for m in manaShop_list]
    m3 = [m["id"] for m in rareShop_list]
    m4 = [m["id"] for m in soundPayer_list]
    return {"mstshop": mstshop + m1 + m2 + m3 + m4}


def main():
    filename = basedir / Path(data_json)
    if filename.exists():
        f1 = open(filename, 'r')
        main_data = json.load(f1)
        if "mstshop" not in main_data.keys():
            main_data["mstshop"] = []
    else:
        main_data = {"mstver": {"appVer": "", "dataVer": 0, "dateVer": 0},
                     "mstquest": [], "mstmission": [], "mstevent": [],
                     "mstshop": []}

    if check_update():
        new_data = check_datavar(main_data)
        new_data.update(check_quests(main_data))
        new_data.update(check_missions(main_data))
        new_data.update(check_event(main_data))
        new_data.update(check_shop(main_data))
        logger.debug(new_data)
        with open(filename, mode="w", encoding="UTF-8") as fout:
            fout.write(json.dumps(new_data))


if __name__ == '__main__':
    # オプションの解析
    parser = argparse.ArgumentParser(
                description='Post FGO update information to Discord'
                )
    # 3. parser.add_argumentで受け取る引数を追加していく
    parser.add_argument('-l', '--loglevel',
                        choices=('debug', 'info'), default='info')

    args = parser.parse_args()    # 引数を解析
    logging.basicConfig(
        level=logging.INFO,
        format='%(name)s <%(filename)s-L%(lineno)s> [%(levelname)s] %(message)s',
    )
    logger.setLevel(args.loglevel.upper())

    main()
