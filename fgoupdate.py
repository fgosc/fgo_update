#!/usr/bin/python3
import sys
import json
import time
from datetime import datetime
import argparse
import logging
from pathlib import Path
import configparser
import tempfile
import os

import git
from discordwebhook import Discord
from zc import lockfile
from zc.lockfile import LockError

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
discord = Discord(url=webhook_url)
webhook_error_url = config.get(section1, 'webhook4error', fallback=webhook_url)
discord_error = Discord(url=webhook_error_url)

section2 = 'fgodata'
repo = config.get(section2, 'repository')
fgodata = repo.replace("https://github.com/", "").replace(".git", "")
fgodata_dir = fgodata.split("/")[-1]
fgodata_local_repo = basedir.parent / fgodata_dir
repo = git.Repo(fgodata_local_repo)
origin = repo.remotes.origin
avatar_url = "https://raw.githubusercontent.com/fgosc/fgo_update/main/info.png"

sha_json = "github_sha.json"
data_json = "fgoupdate.json"
mstver_file = "mstver.json"
mstQuest_file = "JP_tables/quest/mstQuest.json"
mstQuestInfo_file = "JP_tables/quest/viewQuestInfo.json"
mstQuestPhase_file = "JP_tables/quest/mstQuestPhase.json"
mstEventMission_file = "JP_tables/event/mstEventMission.json"
mstEvent_file = "JP_tables/event/mstEvent.json"
mstShop_file = "JP_tables/shop/mstShop.json"
mstSvt_file = "JP_tables/svt/mstSvt.json"
mstSvtLimit_file = "JP_tables/svt/mstSvtLimit.json"
mstSvtFilter_file = "JP_tables/svt/mstSvtFilter.json"
mstSvtSkill_file = "JP_tables/svt/mstSvtSkill.json"
mstEquip_file = "JP_tables/equip/mstEquip.json"
mstEquipExp_file = "JP_tables/equip/mstEquipExp.json"
mstEquipSkill_file = "JP_tables/equip/mstEquipSkill.json"
mstSkill_file = "JP_tables/skill/mstSkill.json"
mstSkillDetail_file = "JP_tables/skill/mstSkillDetail.json"
mstSkillLv_file = "JP_tables/skill/mstSkillLv.json"
mstFunc_file = "JP_tables/func/mstFunc.json"
mstClass_file = "JP_tables/class/mstClass.json"
mstGacha_file = "JP_tables/gacha/mstGacha.json"
mstTreasureDevice_file = "JP_tables/treasure/mstTreasureDevice.json"
mstTreasureDeviceDetail_file = "JP_tables/treasure/mstTreasureDeviceDetail.json"
mstSvt = []
mstSkill = []
mstSkillDetail = []
mstSkillLv = []
mstFunc = []

class_dic = {
             1: "剣", 2: "弓", 3: "槍", 4: "騎", 5: "術", 6: "殺", 7: "狂",
             8: "盾", 9: "裁", 10: "分", 11: "讐", 12: "?", 17: "?", 20: "?",
             22: "?", 23: "月", 24: "?", 25: "降", 26: "?", 27: "?", 97: "?", 1001: "?"
            }

cost2rarity = {16: "★5", 12: "★4", 7: "★3", 4: "★2", 3: "★1", 0: "★4", 9: "9?", 1: "1?", 5: "5?"}


def list2class(enemy):
    """
    リスト内のクラスを省略表記に
    """
    out = ""
    for e in enemy:
        out += class_dic[e]
    return out


def check_update():
    origin.pull()
    sha = str(repo.rev_parse('HEAD'))
    logger.debug("sha: %s", sha)
    filename = basedir / Path(sha_json)
    if filename.exists():
        f1 = open(filename, 'r')
        sha_prev = json.load(f1)["sha"]
    else:
        sha_prev = ""
    logger.debug("sha_prev: %s", sha_prev)
    if sha != sha_prev:
        f2 = open(filename, 'w')
        json.dump({"sha": sha}, f2)
        return True
    return False


def check_datavar(main_data, updatefiles):
    """
    アプリバージョンとデータバージョンをチェックする
    """
    if mstver_file not in updatefiles:
        return {"mstver": main_data["mstver"]}

    prev_mstver = main_data["mstver"]
    with open(basedir.parent / fgodata_dir / Path(mstver_file), encoding="UTF-8") as f:
        mstver = json.load(f)
    logger.debug("prev_dateVar: %s", prev_mstver["dateVer"])
    logger.debug("dateVar: %s", mstver["dateVer"])
    if prev_mstver["dateVer"] != mstver["dateVer"]:
        discord.post(username="FGO アップデート",
                     avatar_url=avatar_url,
                     embeds=[{"title": "データ更新",
                              "description": "Version: " + str(mstver["appVer"]) + " DataVer: " + str(mstver["dataVer"]),
                              "color": 5620992}])
    return {"mstver": mstver}


def output_gacha(gacha_list):
    """
    ガチャデータを出力する
    """
    # fields の内容を事前作成
    date_items = []
    prev_openedAt = 0
    prev_closedAt = 0
    items = []
    # 時間を分けたデータを作成
    for i, item in enumerate(gacha_list):
        openedAt = datetime.fromtimestamp(item["openedAt"])
        closedAt = datetime.fromtimestamp(item["closedAt"])
        if i == 0:
            itemdate = '```開始 | ' + str(openedAt) + '\n終了 | ' + str(closedAt) + '```'
            items.append("[" + item["name"] + "](https://view.fate-go.jp/webview/summon" + item["detailUrl"] + "_header.html)")
            prev_openedAt = openedAt
            prev_closedAt = closedAt
        elif prev_openedAt == openedAt and prev_closedAt == closedAt:
            items.append("[" + item["name"] + "](https://view.fate-go.jp/webview/summon" + item["detailUrl"] + "_header.html)")
        else:
            date_item = {"date": itemdate, "items": items}
            date_items.append(date_item)
            itemdate = '```開始 | ' + str(openedAt) + '\n終了 | ' + str(closedAt) + '```'
            items = []
            items.append("[" + item["name"] + "](https://view.fate-go.jp/webview/summon" + item["detailUrl"] + "_header.html)")
            prev_openedAt = openedAt
            prev_closedAt = closedAt
    if len(items) > 0:
        date_item = {"date": itemdate, "items": items}
        date_items.append(date_item)
    # filedを作成
    fields = []
    for date_item in date_items:
        logger.debug(date_item)
        field = [{"name": "日時",
                 "value": date_item["date"]
                  },
                 {
                  "name": "項目",
                  "value": '\n'.join(['- ' + n for n in date_item["items"]])
                  }]
        fields += field
    logger.debug("filelds: %s", fields)

    if len(fields) != 0:
        # 投稿できるfield 数に制限があるので分ける
        discord.post(username="FGO アップデート",
                     avatar_url=avatar_url,
                     embeds=[{
                                "title": "ガチャ更新",
                                "image": {"url": "https://view.fate-go.jp/webview/common/images" + gacha_list[0]["detailUrl"] + ".png"},
                                "fields": fields[:20],
                                "color": 5620992}])
        if len(fields) >= 20:
            discord.post(username="FGO アップデート",
                         avatar_url=avatar_url,
                         embeds=[{
                                    "title": "ガチャ更新",
                                    "image": {"url": "https://view.fate-go.jp/webview/common/images" + gacha_list[0]["detailUrl"] + ".png"},
                                    "fields": fields[20:],
                                    "color": 5620992}])


def check_gacha(main_data, updatefiles):
    """
    ガチャをチェックする
    """
    if mstGacha_file not in updatefiles:
        return {"mstgacha": main_data["mstgacha"]}
    exclude_id = [1, 101, 21001]  # ストーリー召喚、チュートリアル召喚、フレンドポイント召喚
    with open(basedir.parent / fgodata_dir / Path(mstGacha_file), encoding="UTF-8") as f:
        mstGacha = json.load(f)

    mstgacha = main_data["mstgacha"]
    logger.debug("mstgacha: %s", mstgacha)
    mstGacha_list = [g for g in mstGacha
                     if g["id"] not in mstgacha
                     and g["id"] not in exclude_id
                     and g["closedAt"] > time.time()]
    logger.debug("mstGacha_list: %s", mstGacha_list)
    output_gacha(mstGacha_list)
    m1 = [m["id"] for m in mstGacha_list]

    return {"mstgacha": mstgacha + m1}


def make_svtStatus(svt, mstSvtLimit):
    """
    サーヴァントのステータスを作成
    """
    hp = [s["hpMax"] for s in mstSvtLimit if s["svtId"] == svt["id"] and s["limitCount"] == 4][0]
    atk = [s["atkMax"] for s in mstSvtLimit if s["svtId"] == svt["id"] and s["limitCount"] == 4][0]
    desp = "**ステータス**\n"
    desp += "HP " + '{:,}'.format(hp) + ", ATK " + '{:,}'.format(atk) + ", COST " + str(svt["cost"]) + "\n"
    desp += "\n"
    return desp


def make_svtSkill(svt, mstSvtSkill):
    """
    サーヴァントのスキルを作成
    """
    skill1_id = [s["skillId"] for s in mstSvtSkill if s["svtId"] == svt["id"] and s["num"] == 1][0]
    skill2_id = [s["skillId"] for s in mstSvtSkill if s["svtId"] == svt["id"] and s["num"] == 2][0]
    skill3_id = [s["skillId"] for s in mstSvtSkill if s["svtId"] == svt["id"] and s["num"] == 3][0]
    skill1_ct = [s["chargeTurn"] for s in mstSkillLv if s["skillId"] == skill1_id and s["lv"] == 1][0]
    skill2_ct = [s["chargeTurn"] for s in mstSkillLv if s["skillId"] == skill2_id and s["lv"] == 1][0]
    skill3_ct = [s["chargeTurn"] for s in mstSkillLv if s["skillId"] == skill3_id and s["lv"] == 1][0]

    # 保有スキルを出力
    desp = "**保有スキル:**\n"
    desp += "__スキル1__ チャージタイム||" + str(skill1_ct) + "\n"
    desp += [k["name"] for k in mstSkill
             if k["id"] == skill1_id][0] + "\n"
    desp += [i["detail"] for i in mstSkillDetail if i["id"] == skill1_id][0].replace("[{0}]", r"\[Lv\]") + "||"
    desp += "\n\n"
    desp += "__スキル2__ チャージタイム||" + str(skill2_ct) + "\n"
    desp += [k["name"] for k in mstSkill
             if k["id"] == skill2_id][0] + "\n"
    desp += [i["detail"] for i in mstSkillDetail if i["id"] == skill2_id][0].replace("[{0}]", r"\[Lv\]") + "||"
    desp += "\n\n"
    desp += "__スキル3__ チャージタイム||" + str(skill3_ct) + "\n"
    desp += [k["name"] for k in mstSkill
             if k["id"] == skill3_id][0] + "\n"
    desp += [i["detail"] for i in mstSkillDetail if i["id"] == skill3_id][0].replace("[{0}]", r"\[Lv\]") + "||"
    desp += "\n\n"

    return desp


def make_svtClassSkill(svt):
    """
    サーヴァントのクラススキルを作成
    """
    desp = "**クラススキル:**\n"
    desp += "||"
    for skillId in svt["classPassive"]:
        desp += [s["name"] for s in mstSkill if s["id"] == skillId][0] + '\n'
        desp += [i["detail"] for i in mstSkillDetail if i["id"] == skillId][0].replace("{0}", "Lv")
        desp += "\n\n"
    desp += "||"

    desp += "\n"

    return desp


def make_np(svt, mstTreasureDevice, mstTreasureDeviceDetail):
    """
    サーヴァントの宝具を作成
    """
    desp = "**宝具:**\n"
    np = [np for np in mstTreasureDevice if np["seqId"] == svt["id"]][0]
    desp += np["name"]
    desp += "(" + np["ruby"] + ")" + "\n"
    desp += "__ランク__ " + np["rank"] + "\n"
    desp += "__種別__ " + np["typeText"] + "\n"
    desp += "```" + [n["detail"] for n in mstTreasureDeviceDetail if n["id"] == np["id"]][0].replace("[{0}]", "[Lv]") + "```" + "\n"
    desp += "\n"
    return desp


def check_svt(main_data, updatefiles):
    """
    サーヴァントをチェックする
    """
    if mstSvt_file not in updatefiles:
        return {"mstsvt": main_data["mstsvt"]}
    with open(basedir.parent / fgodata_dir / Path(mstSvtLimit_file), encoding="UTF-8") as f:
        mstSvtLimit = json.load(f)
    with open(basedir.parent / fgodata_dir / Path(mstSvtSkill_file), encoding="UTF-8") as f:
        mstSvtSkill = json.load(f)
    with open(basedir.parent / fgodata_dir / Path(mstClass_file), encoding="UTF-8") as f:
        mstClass = json.load(f)
    with open(basedir.parent / fgodata_dir / Path(mstTreasureDevice_file), encoding="UTF-8") as f:
        mstTreasureDevice = json.load(f)
    with open(basedir.parent / fgodata_dir / Path(mstTreasureDeviceDetail_file), encoding="UTF-8") as f:
        mstTreasureDeviceDetail = json.load(f)

    mstsvt = main_data["mstsvt"]
    logger.debug("mstsvt: %s", mstsvt)
    mstSvt_list = [q for q in mstSvt if (q["type"] == 1 or q["type"] == 2) and q["id"] not in mstsvt and q["collectionNo"] > 302]
    logger.debug("mstSvt_list: %s", mstSvt_list)
    id2class = {c["id"]: c["name"] for c in mstClass}
    id2card = {1: "A", 2: "B", 3: "Q"}
    for svt in mstSvt_list:
        desp = "[" + "- No." + str(svt["collectionNo"])
        desp += ' ' + cost2rarity[svt["cost"]] + ' ' + id2class[svt["classId"]] + ' ' + svt["name"] + "]"
        desp += "(" + "https://apps.atlasacademy.io/db/#/JP/servant/" + str(svt["collectionNo"]) + ")\n"
        cards = ""
        for cardId in svt["cardIds"]:
            cards += id2card[cardId]
        desp += "\n"

        desp += make_svtStatus(svt, mstSvtLimit)
        desp += make_svtSkill(svt, mstSvtSkill)
        desp += make_svtClassSkill(svt)
        desp += make_np(svt, mstTreasureDevice, mstTreasureDeviceDetail)
        desp += "**コマンドカード:**\n"
        desp += "||" + cards + "||"
        discord.post(username="FGO アップデート",
                     avatar_url=avatar_url,
                     embeds=[{
                              "title": "サーヴァント新規追加",
                              "description": desp,
                              "color": 5620992}])
    m1 = [m["id"] for m in mstSvt_list]
    return {"mstsvt": mstsvt + m1}


def output_quest(q_list, title):
    # fields の内容を事前作成
    date_items = []
    prev_openedAt = 0
    prev_closedAt = 0
    items = []
    # 時間を分けたデータを作成
    for i, quest in enumerate(q_list):
        openedAt = datetime.fromtimestamp(quest[4])
        closedAt = datetime.fromtimestamp(quest[5])
        if i == 0:
            itemdate = '```開始 | ' + str(openedAt) + '\n終了 | ' + str(closedAt) + '```'
            items.append(','.join([str(n) for n in quest[:-2]]))
            prev_openedAt = openedAt
            prev_closedAt = closedAt
        elif prev_openedAt == openedAt and prev_closedAt == closedAt:
            items.append(','.join([str(n) for n in quest[:-2]]))
        else:
            date_item = {"date": itemdate, "items": items}
            date_items.append(date_item)
            itemdate = '```開始 | ' + str(openedAt) + '\n終了 | ' + str(closedAt) + '```'
            items = []
            items.append(','.join([str(n) for n in quest[:-2]]))
            prev_openedAt = openedAt
            prev_closedAt = closedAt
    if len(items) > 0:
        date_item = {"date": itemdate, "items": items}
        date_items.append(date_item)
    # filedを作成
    fields = []
    for date_item in date_items:
        logger.debug(date_item)
        field = [{"name": "日時",
                 "value": date_item["date"]
                  },
                 {
                  "name": "クエスト",
                  "value": '\n'.join(['- ' + n for n in date_item["items"]])
                  }]
        fields += field
    logger.debug(fields)

    if len(fields) != 0:
        discord.post(username="FGO アップデート",
                     avatar_url=avatar_url,
                     embeds=[{
                                "title": title + "更新",
                                "fields": fields,
                                "color": 5620992}])


def check_quests(main_data, updatefiles):
    """
    クエストをチェックする
    """
    if mstQuest_file not in updatefiles:
        return {"mstquest": main_data["mstquest"]}
    with open(basedir.parent / fgodata_dir / Path(mstQuest_file), encoding="UTF-8") as f:
        mstQuest = json.load(f)

    mstquest = main_data["mstquest"]
    logger.debug("mstquest: %s", mstquest)
    mstQuest_list = [q for q in mstQuest if q["id"] not in mstquest]

    with open(basedir.parent / fgodata_dir / Path(mstQuestInfo_file), encoding="UTF-8") as f:
        mstQuestInfo_list = json.load(f)
    with open(basedir.parent / fgodata_dir / Path(mstQuestPhase_file), encoding="UTF-8") as f:
        mstQuestPhase_list = json.load(f)
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
        if quest["closedAt"] == 1901199599 or quest["closedAt"] < time.time():
            continue
        if "高難易度" in quest["name"]:
            enemy = questId2classIds[quest["id"]]
            q_list.append([quest["id"], quest["name"], 'Lv' + quest["recommendLv"], list2class(enemy), quest["openedAt"], quest["closedAt"]])
            continue
        for q in mstQuestInfo_list:
            if q["questId"] == quest["id"]:
                enemy = questId2classIds[quest["id"]]
                if quest["id"] > 94000000:
                    q_list.append([quest["id"], quest["name"], 'Lv' + quest["recommendLv"], list2class(enemy), quest["openedAt"], quest["closedAt"]])
                else:
                    fq_list.append([quest["id"], quest["name"], 'Lv' + quest["recommendLv"], list2class(enemy), quest["openedAt"], quest["closedAt"]])
                break

    logger.debug(q_list)
    logger.debug(fq_list)
    output_quest(q_list, "イベントクエスト")
    output_quest(fq_list, "恒常フリークエスト")
    m1 = [m[0] for m in q_list]
    m2 = [m[0] for m in fq_list]

    return {"mstquest": mstquest + m1 + m2}


def check_mastermissions(mstEventMission_list):
    """
    マスターミッションをチェックする
    """
    if len(mstEventMission_list) != 0:
        discord.post(username="FGO アップデート",
                     avatar_url=avatar_url,
                     embeds=[{"title": "マスターミッション(ウィークリー)更新",
                              "fields": [{
                                          "name": "日時",
                                          "value": '```開始 | ' + str(datetime.fromtimestamp(mstEventMission_list[0]["startedAt"])) + '\n終了 | ' + str(datetime.fromtimestamp(mstEventMission_list[0]["endedAt"])) + '```'
                                          },
                                         {
                                          "name": "ミッション",
                                          "value": '\n'.join(['- ' + n["detail"] for n in mstEventMission_list])
                                          }
                                         ],
                              "color": 5620992}])


def check_eventmissions(mstEventMissionLimited_list):
    """
    イベントミッションをチェックする
    """
    if len(mstEventMissionLimited_list) != 0:
        discord.post(username="FGO アップデート",
                     avatar_url=avatar_url,
                     embeds=[{
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
                                "color": 5620992}])


def check_dailymissions(mstEventMissionDaily_list):
    """
    デイリーミッションをチェックする
    """
    if len(mstEventMissionDaily_list) != 0:
        discord.post(username="FGO アップデート",
                     avatar_url=avatar_url,
                     embeds=[{
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
                                "color": 5620992}])


def check_missions(main_data, updatefiles):
    """
    ミッションをチェックする
    """
    if mstEventMission_file not in updatefiles:
        return {"mstmission": main_data["mstmission"]}
    with open(basedir.parent / fgodata_dir / Path(mstEventMission_file), encoding="UTF-8") as f:
        mstEventMission = json.load(f)
    mstmission = main_data["mstmission"]

    mstEventMission_list = [m for m in mstEventMission
                            if m["type"] == 2
                            and m["endedAt"] > time.time()
                            and m["id"] not in mstmission]
    mstEventMissionLimited_list = [m for m in mstEventMission
                                   if m["type"] == 6
                                   and m["endedAt"] > time.time()
                                   and m["id"] not in mstmission]
    mstEventMissionDaily_list = [m for m in mstEventMission
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


def check_event(main_data, updatefiles):
    """
    イベント・キャンペーンをチェックする
    終了日時はそれぞれ異なるので煩雑になるため表記しないこととする
    """
    if mstEvent_file not in updatefiles:
        return {"mstevent": main_data["mstevent"]}
    with open(basedir.parent / fgodata_dir / Path(mstEvent_file), encoding="UTF-8") as f:
        mstEvent = json.load(f)
    mstevent = main_data["mstevent"]
    logger.debug("mstevent: %s", mstevent)
    mstEvent_list = [m for m in mstEvent
                     if time.time() < m["endedAt"] < 1893423600
                     and m["id"] not in mstevent]
    for event in mstEvent_list:
        logger.debug(event["type"])
        if event["type"] == 12:
            title = "イベント・クエスト"
        else:
            title = "キャンペーン"

        discord.post(username="FGO アップデート",
                     avatar_url=avatar_url,
                     embeds=[{
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
                                "color": 5620992}])
    for event in mstEvent_list:
        mstevent.append(event["id"])
    return {"mstevent": mstevent}


def output_shop(shop_list, shopname):
    """
    ショップデータを出力する
    """
    # fields の内容を事前作成
    date_items = []
    prev_openedAt = 0
    prev_closedAt = 0
    items = []
    # 時間を分けたデータを作成
    for i, item in enumerate(shop_list):
        openedAt = datetime.fromtimestamp(item["openedAt"])
        closedAt = datetime.fromtimestamp(item["closedAt"])
        if i == 0:
            itemdate = '```開始 | ' + str(openedAt) + '\n終了 | ' + str(closedAt) + '```'
            items.append(item["name"] + "x" + str(item["limitNum"]))
            prev_openedAt = openedAt
            prev_closedAt = closedAt
        elif prev_openedAt == openedAt and prev_closedAt == closedAt:
            items.append(item["name"] + "x" + str(item["limitNum"]))
        else:
            date_item = {"date": itemdate, "items": items}
            date_items.append(date_item)
            itemdate = '```開始 | ' + str(openedAt) + '\n終了 | ' + str(closedAt) + '```'
            items = []
            items.append(item["name"] + "x" + str(item["limitNum"]))
            prev_openedAt = openedAt
            prev_closedAt = closedAt
    if len(items) > 0:
        date_item = {"date": itemdate, "items": items}
        date_items.append(date_item)
    # filedを作成
    fields = []
    for date_item in date_items:
        logger.debug(date_item)
        field = [{"name": "日時",
                 "value": date_item["date"]
                  },
                 {
                  "name": "アイテム",
                  "value": '\n'.join(['- ' + n for n in date_item["items"]])
                  }]
        fields += field
    logger.debug(fields)

    if len(fields) != 0:
        discord.post(username="FGO アップデート",
                     avatar_url=avatar_url,
                     embeds=[{
                                "title": shopname + "更新",
                                "fields": fields,
                                "color": 5620992}])


def check_shop(main_data, updatefiles):
    """
    ショップをチェックする
    1 イベント限定ショップ
    2 マナプリズム
    3 レアプリズム
    8 サウンドプレイヤー
    """
    if mstShop_file not in updatefiles:
        return {"mstshop": main_data["mstshop"]}
    with open(basedir.parent / fgodata_dir / Path(mstShop_file), encoding="UTF-8") as f:
        mstShop = json.load(f)
    mstshop = main_data["mstshop"]
    logger.debug("mstshop: %s", mstshop)
    eventShop_list = [m for m in mstShop
                      if m["shopType"] == 1
                      and time.time() < m["closedAt"] < 1893423600
                      and m["id"] not in mstshop]
    logger.debug("eventShop_list: %s", eventShop_list)
    manaShop_list = [m for m in mstShop
                     if m["shopType"] == 2
                     and m["openedAt"] >= 1609426800
                     and time.time() < m["closedAt"]
                     and m["id"] not in mstshop]
    logger.debug("manaShop_list: %s", manaShop_list)
    rareShop_list = [m for m in mstShop
                     if m["shopType"] == 3
                     and m["openedAt"] >= 1607958000
                     and time.time() < m["closedAt"]
                     and m["id"] not in mstshop]
    # 1594717200はこのソフトウェア公開直前の解放
    logger.debug("rareShop_list: %s", rareShop_list)
    soundPayer_list = [m for m in mstShop
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


def check_svtfilter(main_data, updatefiles):
    """
    サーヴァント強化フィルターの更新チェック
    """
    if mstSvtFilter_file not in updatefiles:
        return {"mstsvtfilter": main_data["mstsvtfilter"]}
    with open(basedir.parent / fgodata_dir / Path(mstSvtFilter_file), encoding="UTF-8") as f:
        mstSvtFilter = json.load(f)
    mstSvt_list = [q for q in mstSvt if (q["type"] == 1 or q["type"] == 2) and q["collectionNo"] not in mstSvt and q["collectionNo"] != 0]
    mstsvtfilter = main_data["mstsvtfilter"]
    logger.debug("mstsvtfilter: %s", mstsvtfilter)
    mstSvtFilter_list = [m for m in mstSvtFilter
                         if m["id"] not in mstsvtfilter]
    mstSvtF_dic = {m["id"]: cost2rarity[m["cost"]] + ' ' + m["name"] + '〔' + class_dic[m["classId"]] + '〕' for m in mstSvt_list}
    logger.debug(mstSvtF_dic)
    logger.debug("mstSvtFilter_list: %s", mstSvtFilter_list)
    for svtFilter in mstSvtFilter_list:
        discord.post(username="FGO アップデート",
                     avatar_url=avatar_url,
                     embeds=[{
                                "title": svtFilter["name"] + "フィルター更新",
                                "fields": [
                                    {
                                        "name": "対象サーヴァント",
                                        "value": '\n'.join(['- ' + mstSvtF_dic[n] for n in svtFilter["svtIds"]])
                                    }
                                ],
                                "color": 5620992}])
    for svtFilter in mstSvtFilter_list:
        mstsvtfilter.append(svtFilter["id"])
    return {"mstsvtfilter": mstsvtfilter}


def plot_equiipExp(name, mc_exp):
    """
    マスター装備の必要経験値をプロットする
    """
    # ロードに時間がかかり、かつたまにしか実行されないため遅延 import
    import matplotlib.pyplot as plt
    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1)

    # 折れ線グラフを出力
    level = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

    mcChaldea_exp = [0, 10000, 40000, 100000, 220000,
                     460000, 940000, 1900000, 3820000, 7660000]
    mcStd_exp = [0, 1569000, 4707000, 9414000, 15690000,
                 23535000, 32949000, 43932000, 56484000, 70605000]
    mcLmited_exp = [0, 53000, 132500, 305000, 609000,
                    1218000, 2200000, 3727000, 5963000, 8950000]
    mcArctic_exp = [0, 3451800, 10355400, 20710800, 34518000,
                    51777000, 72487800, 96650400, 124264800, 155331000]
    ax.plot(level, mcChaldea_exp)
    ax.plot(level, mcStd_exp)
    ax.plot(level, mcLmited_exp)
    ax.plot(level, mcArctic_exp)
    ax.plot(level, mc_exp, " ", marker='o')
    ax.set_title('マスター装備必要経験値')
    ax.set_xlabel('Lv')  # x軸ラベル
    ax.legend(['魔術礼装･カルデア', '恒常装備', '期間限定装備', '魔術礼装･極地用カルデア制服', name])  # 凡例を表示
    # 一時ファイルをつくらないで投稿する方法が良く分からないのでtempfileを使用
    tmpdir = tempfile.TemporaryDirectory()
    savefile = os.path.join(tmpdir.name, 'mcfig.png')
    plt.savefig(savefile)
    discord.post(username="FGO アップデート",
                 avatar_url=avatar_url,
                 file={
                       "file1": open(savefile, "rb"),
                       },
                 )
    tmpdir.cleanup()


def check_mstEquip(main_data, updatefiles):
    """
    マスター装備の更新チェック
    """
    if mstEquip_file not in updatefiles:
        return {"mstequip": main_data["mstequip"]}
    with open(basedir.parent / fgodata_dir / Path(mstEquip_file), encoding="UTF-8") as f:
        mstEquip = json.load(f)
    with open(basedir.parent / fgodata_dir / Path(mstEquipExp_file), encoding="UTF-8") as f:
        mstEquipExp = json.load(f)
    with open(basedir.parent / fgodata_dir / Path(mstEquipSkill_file), encoding="UTF-8") as f:
        mstEquipSkill = json.load(f)
    mstequip = main_data["mstEquip"]
    logger.debug("mstequip: %s", mstequip)
    mstEquip_list = [m for m in mstEquip
                     if m["id"] not in mstequip]
    logger.debug("mstEquip_list: %s", mstEquip_list)
    for equip in mstEquip_list:
        skill1_id = [s["skillId"] for s in mstEquipSkill if s["equipId"] == equip["id"] and s["num"] == 1][0]
        skill2_id = [s["skillId"] for s in mstEquipSkill if s["equipId"] == equip["id"] and s["num"] == 2][0]
        skill3_id = [s["skillId"] for s in mstEquipSkill if s["equipId"] == equip["id"] and s["num"] == 3][0]
        # sval を求める
        # mstFunc->applyTarget
        skill1_ct = [s["chargeTurn"] for s in mstSkillLv if s["skillId"] == skill1_id and s["lv"] == 1][0]
        skill2_ct = [s["chargeTurn"] for s in mstSkillLv if s["skillId"] == skill2_id and s["lv"] == 1][0]
        skill3_ct = [s["chargeTurn"] for s in mstSkillLv if s["skillId"] == skill3_id and s["lv"] == 1][0]
        # skill1_val = [s["svals"] for s in mstSkillLv if s["skillId"] == skill1_id]
        # skill2_val = [s["svals"] for s in mstSkillLv if s["skillId"] == skill2_id]
        # skill3_val = [s["svals"] for s in mstSkillLv if s["skillId"] == skill3_id]
        # skill1_funcType0 = [[f["funcType"] for f in mstFunc if f["id"] == func][0] for func in [s["funcId"] for s in mstSkillLv if s["skillId"] == skill1_id and s["lv"] == 1][0]]
        # logger.info(skill1_funcType0)
        mc_exp = [0] + [e["exp"] for e in mstEquipExp if e["equipId"] == equip["id"]][:-1]
        logger.debug("mc_exp: %s", mc_exp)
        discord.post(username="FGO アップデート",
                     avatar_url=avatar_url,
                     embeds=[{
                                "title": "マスター装備更新",
                                "description": "[" + equip["name"] + "](" + "https://apps.atlasacademy.io/db/#/JP/mystic-code/" + str(equip["id"]) + ")",
                                "fields": [
                                    {
                                        "name": "詳細",
                                        "value": '```' + equip["detail"] + '```'
                                    },
                                    {
                                        "name": "スキル1",
                                        "value": [k["name"] for k in mstSkill
                                                  if k["id"] == skill1_id
                                                  ][0] + ' CT' + str(skill1_ct) + '```' + [i["detail"] for i in mstSkillDetail if i["id"] == skill1_id][0].replace("{0}", "Lv") + '```',
                                        "inline": True
                                    },
                                    {
                                        "name": "スキル2",
                                        "value": [k["name"] for k in mstSkill
                                                  if k["id"] == skill2_id
                                                  ][0] + ' CT' + str(skill2_ct) + '```' + [i["detail"] for i in mstSkillDetail if i["id"] == skill2_id][0].replace("{0}", "Lv") + '```',
                                        "inline": True
                                    },
                                    {
                                        "name": "スキル3",
                                        "value": [k["name"] for k in mstSkill
                                                  if k["id"] == skill3_id
                                                  ][0] + ' CT' + str(skill3_ct) + '```' + [i["detail"] for i in mstSkillDetail if i["id"] == skill3_id][0].replace("{0}", "Lv") + '```',
                                        "inline": True
                                    }
                                ],
                                "color": 5620992}])
        plot_equiipExp(equip["name"], mc_exp)
    for equip in mstEquip_list:
        mstequip.append(equip["id"])
    return {"mstequip": mstequip}


def lock_or_through(func):
    '''
    ロックファイルによる排他制御デコレータ
    ロックされている場合は処理自体をスルー
    '''
    def lock(*args, **kwargs):
        lock = None
        try:
            lock = lockfile.LockFile('lock')
        except LockError:
            logger.error("locked")
            discord_error.post(username="FGO アップデート",
                               avatar_url=avatar_url,
                               embeds=[{
                                "title": "Error",
                                "description": "Proccess locked",
                                "color": 15158332}])
            return

        func(*args, **kwargs)

        # 対象のpidが有効でなければロックされないので例外が出ても実質問題無し
        lock.close()

    return lock


@lock_or_through
def main():
    filename = basedir / Path(data_json)
    mystic_code_init = [1, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 150, 160, 170]
    if filename.exists():
        f1 = open(filename, 'r')
        main_data = json.load(f1)
        if "mstgacha" not in main_data.keys():
            main_data["mstgacha"] = []
        if "mstsvt" not in main_data.keys():
            main_data["mstsvt"] = []
        if "mstshop" not in main_data.keys():
            main_data["mstshop"] = []
        if "mstsvtfilter" not in main_data.keys():
            main_data["mstsvtfilter"] = []
        if "mstequip" not in main_data.keys():
            main_data["mstequip"] = mystic_code_init
    else:
        main_data = {"mstver": {"appVer": "", "dataVer": 0, "dateVer": 0},
                     "mstquest": [], "mstmission": [], "mstevent": [],
                     "mstshop": [], "mstsvtfilter": [],
                     "mstequip": mystic_code_init, "mstsvt": [], "mstgacha": []}

    if check_update():
        updatefiles = repo.git.diff('HEAD~1..HEAD', name_only=True).split('\n')
        if mstSvtFilter_file in updatefiles or mstSvt_file in updatefiles:
            global mstSvt
            with open(basedir.parent / fgodata_dir / Path(mstSvt_file), encoding="UTF-8") as f:
                mstSvt = json.load(f)
        if mstEquip_file in updatefiles or mstSvt_file in updatefiles:
            # 複数個所で使用するファイルを読んでおく
            global mstSkill
            global mstSkillDetail
            global mstSkillLv
            global mstFunc
            with open(basedir.parent / fgodata_dir / Path(mstSkill_file), encoding="UTF-8") as f:
                mstSkill = json.load(f)
            with open(basedir.parent / fgodata_dir / Path(mstSkillDetail_file), encoding="UTF-8") as f:
                mstSkillDetail = json.load(f)
            with open(basedir.parent / fgodata_dir / Path(mstSkillLv_file), encoding="UTF-8") as f:
                mstSkillLv = json.load(f)
            with open(basedir.parent / fgodata_dir / Path(mstFunc_file), encoding="UTF-8") as f:
                mstFunc = json.load(f)
        try:
            new_data = check_datavar(main_data, updatefiles)
        except Exception as e:
            logger.exception(e)
            discord_error.post(username="FGO アップデート",
                               avatar_url=avatar_url,
                               embeds=[{
                                "title": "check_datavar Error",
                                "description": e,
                                "color": 15158332}])
            new_data = {"mstver": main_data["mstver"]}
        try:
            new_data.update(check_gacha(main_data, updatefiles))
        except Exception as e:
            logger.exception(e)
            discord_error.post(username="FGO アップデート",
                               avatar_url=avatar_url,
                               embeds=[{
                                "title": "check_gacha Error",
                                "description": str(e),
                                "color": 15158332}])
            new_data.update({"mstgacha": main_data["mstgacha"]})
        try:
            new_data.update(check_svt(main_data, updatefiles))
        except Exception as e:
            logger.exception(e)
            discord_error.post(username="FGO アップデート",
                               avatar_url=avatar_url,
                               embeds=[{
                                "title": "check_svt Error",
                                "description": str(e),
                                "color": 15158332}])
            new_data.update({"mstsvt": main_data["mstsvt"]})
        try:
            new_data.update(check_quests(main_data, updatefiles))
        except Exception as e:
            logger.exception(e)
            discord_error.post(username="FGO アップデート",
                               avatar_url=avatar_url,
                               embeds=[{
                                "title": "check_quests Error",
                                "description": str(e),
                                "color": 15158332}])
            new_data.update({"mstquest": main_data["mstquest"]})
        try:
            new_data.update(check_missions(main_data, updatefiles))
        except Exception as e:
            logger.exception(e)
            discord_error.post(username="FGO アップデート",
                               avatar_url=avatar_url,
                               embeds=[{
                                "title": "check_missions Error",
                                "description": e,
                                "color": 15158332}])
            new_data.update({"mstmission": main_data["mstmission"]})
        try:
            new_data.update(check_event(main_data, updatefiles))
        except Exception as e:
            logger.exception(e)
            discord_error.post(username="FGO アップデート",
                               avatar_url=avatar_url,
                               embeds=[{
                                "title": "check_event Error",
                                "description": e,
                                "color": 15158332}])
            new_data.update({"mstevent": main_data["mstevent"]})
        try:
            new_data.update(check_shop(main_data, updatefiles))
        except Exception as e:
            logger.exception(e)
            discord_error.post(username="FGO アップデート",
                               avatar_url=avatar_url,
                               embeds=[{
                                "title": "check_shop Error",
                                "description": e,
                                "color": 15158332}])
            new_data.update({"mstshop": main_data["mstshop"]})
        try:
            new_data.update(check_svtfilter(main_data, updatefiles))
        except Exception as e:
            logger.exception(e)
            discord_error.post(username="FGO アップデート",
                               avatar_url=avatar_url,
                               embeds=[{
                                "title": "check_svtfilter Error",
                                "description": e,
                                "color": 15158332}])
            new_data.update({"mstsvtfilter": main_data["mstsvtfilter"]})
        try:
            new_data.update(check_mstEquip(main_data, updatefiles))
        except Exception as e:
            logger.exception(e)
            discord_error.post(username="FGO アップデート",
                               avatar_url=avatar_url,
                               embeds=[{
                                "title": "check_mstEquip Error",
                                "description": e,
                                "color": 15158332}])
            new_data.update({"mstequip": main_data["mstequip"]})
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
