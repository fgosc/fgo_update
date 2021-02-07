#!/usr/bin/python3
import sys
import json
from datetime import datetime
import argparse
import logging
from pathlib import Path
import configparser
import tempfile
import os
import re

import git
from discordwebhook import Discord
from zc import lockfile
from zc.lockfile import LockError

import trouble
import info_trouble

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

sha_json = "github_sha.json"
data_json = "fgoupdate.json"
mstver_file = "mstver.json"
mstQuest_file = "JP_tables/quest/mstQuest.json"
mstQuestInfo_file = "JP_tables/quest/viewQuestInfo.json"
mstQuestPhase_file = "JP_tables/quest/mstQuestPhase.json"
mstEventMission_file = "JP_tables/event/mstEventMission.json"
mstEventMissionCondition_file = "JP_tables/event/mstEventMissionCondition.json"
mstEventMissionConditionDetail_file = "JP_tables/event/mstEventMissionConditionDetail.json"
mstEvent_file = "JP_tables/event/mstEvent.json"
mstShop_file = "JP_tables/shop/mstShop.json"
mstEventReward_file = "JP_tables/event/mstEventReward.json"
mstGift_file = "JP_tables/gift/mstGift.json"
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
mstSvtTreasureDevice_file = "JP_tables/svt/mstSvtTreasureDevice.json"
mstTreasureDeviceDetail_file = "JP_tables/treasure/mstTreasureDeviceDetail.json"
mstItem_file = "JP_tables/item/mstItem.json"
mstBoxGacha_file = "JP_tables/box/mstBoxGacha.json"
mstBoxGachaBase_file = "JP_tables/box/mstBoxGachaBase.json"
mstGift_file = "JP_tables/gift/mstGift.json"
mstCommandCode_file = "JP_tables/command/mstCommandCode.json"
mstSvtCostume_file = "JP_tables/svt/mstSvtCostume.json"
aa_url = "https://assets.atlasacademy.io"
mstSvt = []
mstClass = []
id2class = {}
mstSkill = []
mstSkillDetail = []
mstSkillLv = []
mstFunc = []
id2itemName = {}
id2card = {1: "A", 2: "B", 3: "Q"}
id2card_long = {1: "Arts", 2: "Buster", 3: "Quick"}

class_dic = {
             1: "剣", 2: "弓", 3: "槍", 4: "騎", 5: "術", 6: "殺", 7: "狂",
             8: "盾", 9: "裁", 10: "分", 11: "讐", 12: "?", 17: "?", 20: "?",
             22: "?", 23: "月", 24: "?", 25: "降", 26: "?", 27: "?", 97: "?",
             1001: "?"
            }

cost2rarity = {16: "★5", 12: "★4", 7: "★3", 4: "★2",
               3: "★1", 0: "★4", 9: "9?", 1: "1?", 5: "5?"}
postCount = 0


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


def load_file(filename, cid):
    """
    高速化のため、HEADを読み込むときはgitを使用しないで直に読み込む
    """
    if cid == "HEAD":
        json_open = open(fgodata_local_repo / filename, 'r', encoding="UTF-8")
        json_load = json.load(json_open)
    else:
        json_load = json.loads(repo.git.show(cid + ":" + filename))
    return json_load


def check_datavar(updatefiles, cid="HEAD"):
    """
    アプリバージョンとデータバージョンをチェックする
    """
    global postCount
    if mstver_file not in updatefiles:
        return

    mstver = load_file(mstver_file, cid)
    logger.debug("dateVar: %s", mstver["dateVer"])

    """
    イベント・キャンペーンをチェックする
    終了日時はそれぞれ異なるので煩雑になるため表記しないこととする
    """
    fieleds = []
    if mstEvent_file in updatefiles:
        # 集合演算で新idだけ抽出
        mstEvent = load_file(mstEvent_file, cid)
        event = set([s["id"] for s in mstEvent])
        mstEvent_prev = json.loads(repo.git.show(cid + "^:" + mstEvent_file))
        event_prev = set([s["id"] for s in mstEvent_prev])
        eventIds = list(event - event_prev)
        logger.debug(eventIds)

        mstEvent_list = [m for m in mstEvent
                         if m["id"] in eventIds]
        # イベントを先に出すようにするためのソート
        mstEvent_list = sorted(mstEvent_list,
                               key=lambda x: x["type"], reverse=True)

        for event in mstEvent_list:
            logger.debug(event["type"])
            if event["type"] == 12:
                title = "イベント・クエスト"
            elif event["type"] == 22:
                title = "ボードゲーム有イベント"
            else:
                title = "キャンペーン"
            fieled1 = {
                    "name": ":date: 日時",
                    "value": '```開始 | '
                             + str(datetime.fromtimestamp(event["startedAt"]))
                             + '\n終了 | '
                             + str(datetime.fromtimestamp(event["endedAt"]))
                             + '```'
                    }
            fieleds.append(fieled1)
            fieled2 = {
                    "name": title,
                    "value": event["detail"]
                    }
            fieleds.append(fieled2)

    if "appVer" in mstver.keys():
        appVer = str(mstver["appVer"])
    else:
        appVer = ""
    date_str = str(datetime.fromtimestamp(mstver["dateVer"]))
    if len(fieleds) > 0:
        discord.post(username="FGO アップデート",
                     embeds=[{"title": "データ更新",
                              "description": "Version: " + appVer
                                             + " DataVer: "
                                             + str(mstver["dataVer"])
                                             + " "
                                             + date_str,
                              "fields": fieleds,
                              "color": 5620992}])
    else:
        discord.post(username="FGO アップデート",
                     embeds=[{"title": "データ更新",
                              "description": "Version: " + appVer
                                             + " DataVer: "
                                             + str(mstver["dataVer"])
                                             + " "
                                             + date_str,
                              "color": 5620992}])
    postCount += 1
    info_trouble.getInfoTrouble()


def output_gacha(gacha_list):
    """
    ガチャデータを出力する
    """
    # fields の内容を事前作成
    global postCount
    date_items = []
    prev_openedAt = 0
    prev_closedAt = 0
    items = []
    # 時間を分けたデータを作成
    for i, item in enumerate(gacha_list):
        openedAt = datetime.fromtimestamp(item["openedAt"])
        closedAt = datetime.fromtimestamp(item["closedAt"])
        if i == 0:
            itemdate = '```開始 | ' + str(openedAt) \
                       + '\n終了 | ' + str(closedAt) + '```\n'
            items.append("[" + item["name"]
                         + "](https://view.fate-go.jp/webview/summon"
                         + item["detailUrl"] + "_header.html)")
            prev_openedAt = openedAt
            prev_closedAt = closedAt
        elif prev_openedAt == openedAt and prev_closedAt == closedAt:
            items.append(item["name"])
        else:
            date_item = {"date": itemdate, "items": items}
            date_items.append(date_item)
            itemdate = '```開始 | ' + str(openedAt) \
                       + '\n終了 | ' + str(closedAt) + '```\n'
            items = []
            items.append(item["name"])
            prev_openedAt = openedAt
            prev_closedAt = closedAt
    if len(items) > 0:
        date_item = {"date": itemdate, "items": items}
        date_items.append(date_item)
    # descriptionを作成
    description = ""
    for date_item in date_items:
        logger.debug(date_item)
        description += "\n:date: **日時**\n"
        description += date_item["date"]
        description += '\n'.join(['- ' + n for n in date_item["items"]])
        description += "\n"
    image_url = "https://view.fate-go.jp/webview/common/images" \
                + gacha_list[0]["detailUrl"] + ".png"
    thumb_url = aa_url + "/GameData/JP/Items/6.png"
    discord.post(username="FGO アップデート",
                 embeds=[{
                          "title": "ガチャ更新",
                          "description": description,
                          "image": {"url": image_url},
                          "thumbnail": {
                                        "url": thumb_url
                                        },
                          "color": 5620992}])
    postCount += 1


def check_gacha(updatefiles, cid="HEAD"):
    """
    ガチャをチェックする
    """
    if mstGacha_file not in updatefiles:
        return
    # 集合演算で新idだけ抽出
    mstGacha = load_file(mstGacha_file, cid)
    gacha = set([g["id"] for g in mstGacha])
    mstGacha_prev = json.loads(repo.git.show(cid + "^:" + mstGacha_file))
    gacha_prev = set([g["id"] for g in mstGacha_prev])
    gachaIds = list(gacha - gacha_prev)

    mstGacha_list = [g for g in mstGacha
                     if g["id"] in gachaIds]
    mstGacha_list = sorted(mstGacha_list, key=lambda x: x['openedAt'])
    logger.debug("mstGacha_list: %s", mstGacha_list)
    output_gacha(mstGacha_list)


def make_svtStatus(svt, mstSvtLimit, spoiler=False):
    """
    サーヴァントのステータスを作成
    """
    hp = [s["hpMax"] for s in mstSvtLimit
          if s["svtId"] == svt["id"]
          and s["limitCount"] == 4][0]
    atk = [s["atkMax"] for s in mstSvtLimit
           if s["svtId"] == svt["id"]
           and s["limitCount"] == 4][0]
    desp = "**ステータス**\n"
    if spoiler:
        desp += "HP " + '||{:,}||'.format(hp) \
                + ", ATK " + '||{:,}||'.format(atk) \
                + ", COST " + str(svt["cost"]) \
                + "\n"
    else:
        desp += "HP " + '{:,}'.format(hp) \
                + ", ATK " + '{:,}'.format(atk) \
                + ", COST " + str(svt["cost"]) \
                + "\n"
    desp += "\n"
    return desp


def make_svtSkills(svt, mstSvtSkill):
    """
    サーヴァントのスキルを作成
    """
    desp = "**保有スキル:**\n"
    try:
        # 敵データなどで存在するときにコケるので try except
        skill1_id = [s["skillId"] for s in mstSvtSkill
                     if s["svtId"] == svt["id"] and s["num"] == 1][0]
        skill2_id = [s["skillId"] for s in mstSvtSkill
                     if s["svtId"] == svt["id"] and s["num"] == 2][0]
        skill3_id = [s["skillId"] for s in mstSvtSkill
                     if s["svtId"] == svt["id"] and s["num"] == 3][0]
        skill1_ct = [s["chargeTurn"] for s in mstSkillLv
                     if s["skillId"] == skill1_id and s["lv"] == 1][0]
        skill2_ct = [s["chargeTurn"] for s in mstSkillLv
                     if s["skillId"] == skill2_id and s["lv"] == 1][0]
        skill3_ct = [s["chargeTurn"] for s in mstSkillLv
                     if s["skillId"] == skill3_id and s["lv"] == 1][0]

        # 保有スキルを出力
        desp += "__スキル1__ チャージタイム||" + str(skill1_ct) + "\n"
        desp += [k["name"] for k in mstSkill
                 if k["id"] == skill1_id][0] + "\n"
        desp += [i["detail"] for i in mstSkillDetail
                 if i["id"] == skill1_id][0].replace("[{0}]", r"\[Lv\]") + "||"
        desp += "\n\n"
        desp += "__スキル2__ チャージタイム||" + str(skill2_ct) + "\n"
        desp += [k["name"] for k in mstSkill
                 if k["id"] == skill2_id][0] + "\n"
        desp += [i["detail"] for i in mstSkillDetail
                 if i["id"] == skill2_id][0].replace("[{0}]", r"\[Lv\]") + "||"
        desp += "\n\n"
        desp += "__スキル3__ チャージタイム||" + str(skill3_ct) + "\n"
        desp += [k["name"] for k in mstSkill
                 if k["id"] == skill3_id][0] + "\n"
        desp += [i["detail"] for i in mstSkillDetail
                 if i["id"] == skill3_id][0].replace("[{0}]", r"\[Lv\]") + "||"
    except Exception as e:
        logger.exception(e)

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
        desp += [i["detail"] for i in mstSkillDetail
                 if i["id"] == skillId][0].replace("{0}", "Lv")
        desp += "\n\n"
    desp += "||"

    desp += "\n"

    return desp


def make_np(svt, mstTreasureDevice, mstTreasureDeviceDetail,
            mstSvtTreasureDevice, spoiler=False):
    """
    サーヴァントの宝具を作成
    """
    desp = "**宝具:**\n"
    if spoiler:
        desp += "||"
    np = [np for np in mstTreasureDevice if np["seqId"] == svt["id"]][0]
    desp += np["name"]
    desp += "(" + np["ruby"] + ")" + " " \
            + id2card_long[[np["cardId"] for np in mstSvtTreasureDevice
                            if np["svtId"] == svt["id"]][0]] + "\n"
    desp += "__ランク__ " + np["rank"] + "\n"
    desp += "__種別__ " + np["typeText"] + "\n"
    if spoiler:
        desp += [n["detail"] for n in mstTreasureDeviceDetail
                 if n["id"] == np["id"]][0].replace("[{0}]",
                                                    "[Lv]") + "||" + "\n"
    else:
        desp += "```" \
                + [n["detail"] for n in mstTreasureDeviceDetail
                   if n["id"] == np["id"]][0].replace("[{0}]", "[Lv]") \
                + "```" + "\n"
    desp += "\n"
    return desp


def check_svt(updatefiles, cid="HEAD"):
    """
    サーヴァントをチェックする
    """
    global postCount
    if mstSvt_file not in updatefiles:
        return
    mstSvtLimit = load_file(mstSvtLimit_file, cid)
    mstSvtSkill = load_file(mstSvtSkill_file, cid)
    mstTreasureDevice = load_file(mstTreasureDevice_file, cid)
    mstTreasureDeviceDetail = load_file(mstTreasureDeviceDetail_file, cid)
    mstSvtTreasureDevice = load_file(mstSvtTreasureDevice_file, cid)
    # 集合演算で新idだけ抽出
    mstSvt = load_file(mstSvt_file, cid)
    svt = set([s["id"] for s in mstSvt if (s["type"] == 1 or s["type"] == 2)])
    mstSvt_prev = json.loads(repo.git.show(cid + "^:" + mstSvt_file))
    svt_prev = set([s["id"] for s in mstSvt_prev
                    if (s["type"] == 1 or s["type"] == 2)])
    gachaIds = list(svt - svt_prev)
    logger.debug(gachaIds)

    mstSvt_list1 = [q for q in mstSvt
                    if (q["type"] == 1 or q["type"] == 2)
                    and q["id"] in gachaIds and q["collectionNo"] != 0]
    mstSvt_list1 = sorted(mstSvt_list1, key=lambda x: x['collectionNo'])
    mstSvt_list2 = [q for q in mstSvt
                    if (q["type"] == 1 or q["type"] == 2)
                    and q["id"] in gachaIds and q["collectionNo"] == 0]
    mstSvt_list = mstSvt_list1 + mstSvt_list2
    logger.debug("mstSvt_list: %s", mstSvt_list)
    for svt in mstSvt_list:
        try:
            # スキル無しで事前実装されることがあるので
            if svt["collectionNo"] == 0:
                desp = cost2rarity[svt["cost"]] + ' ' \
                       + id2class[svt["classId"]] \
                       + ' ||' + svt["name"] + "||(※おそらくストーリーのネタバレを含みます)"
            else:
                desp = "- [" + "No." + str(svt["collectionNo"])
                desp += ' ' + cost2rarity[svt["cost"]] + ' ' \
                        + id2class[svt["classId"]] + ' ' + svt["name"] + "]"
                desp += "(" + "https://apps.atlasacademy.io/db/#/JP/servant/" \
                        + str(svt["collectionNo"]) + ")\n"
            cards = ""
            for cardId in svt["cardIds"]:
                cards += id2card[cardId]
            desp += "\n"

            if svt["collectionNo"] == 0:
                spoiler = True
            else:
                spoiler = False
            desp += make_svtStatus(svt, mstSvtLimit, spoiler=spoiler)
            desp += make_svtSkills(svt, mstSvtSkill)
            desp += make_svtClassSkill(svt)
            desp += make_np(svt, mstTreasureDevice, mstTreasureDeviceDetail,
                            mstSvtTreasureDevice, spoiler=spoiler)
            desp += "**コマンドカード:**\n"
            desp += "||" + cards + "||"
            if 0 < svt["cost"] < 7:
                color = "1"
            elif svt["cost"] == 7:
                color = "2"
            else:
                color = "3"
            icon_url = aa_url + "/GameData/JP/ClassIcons/class"
            thumb_url = icon_url + color + "_" + str(svt["classId"]) + ".png"
            if svt["collectionNo"] == 0:
                caution = "(詳細不明)"
            else:
                caution = ""
            discord.post(username="FGO アップデート",
                         embeds=[{
                                  "title": "サーヴァント新規追加" + caution,
                                  "thumbnail": {
                                                "url": thumb_url
                                                },
                                  "description": desp,
                                  "color": 5620992}])
            postCount += 1
        except Exception as e:
            logger.exception(e)
            continue


def check_strengthen(updatefiles, cid="HEAD"):
    """
    強化をチェックする
    """
    global postCount
    face_icon = -1
    np_desc = ""
    if mstTreasureDevice_file in updatefiles:
        # 集合演算で新idだけ抽出
        mstSvt_list = [q for q in mstSvt
                       if (q["type"] == 1 or q["type"] == 2)
                       and q["id"] and q["collectionNo"] != 0]
        mstSvtNp = load_file(mstSvtTreasureDevice_file, cid)
        svtNp = [n["treasureDeviceId"] for n in mstSvtNp
                 if n["priority"] > 101]

        mstNp = load_file(mstTreasureDevice_file, cid)
        np = set([s["id"] for s in mstNp if s["id"] in svtNp])
        mstNp_prev = json.loads(repo.git.show(cid + "^:"
                                              + mstTreasureDevice_file))
        np_prev = set([s["id"] for s in mstNp_prev if s["id"] in svtNp])
        npIds = list(np - np_prev)
        logger.debug(npIds)
        # # fields作成
        mstNpDetail = load_file(mstTreasureDeviceDetail_file, cid)

        for npId in npIds:
            svtId = [s["svtId"] for s in mstSvtNp
                     if s["treasureDeviceId"] == npId][0]
            logger.debug(svtId)
            try:
                svt = [s for s in mstSvt_list if s["id"] == svtId][0]
                if face_icon == -1:
                    face_icon = svtId
            except Exception as e:
                logger.exception(e)
                continue
            logger.debug(svt)
            np_desc += ":crown:No." + str(svt["collectionNo"])
            np_desc += ' ' + cost2rarity[svt["cost"]] + ' '
            np_desc += id2class[svt["classId"]] + ' ' + svt["name"] + "\n"

            # 宝具を出力
            np_desc += "[" + [n["name"] + "(" + n["ruby"] + ")" for n in mstNp
                              if n["id"] == npId][0] + "]"
            np_desc += "(" + "https://apps.atlasacademy.io/db/#/JP/servant/"
            np_desc += str(svt["collectionNo"]) + "/noble-phantasms" + ")"
            np_desc += " " + id2card_long[[np["cardId"] for np in mstSvtNp
                                           if np["svtId"] == svtId][0]] + "\n"
        #     value += "チャージタイム" + str(skill_ct) + "\n"
            np_desc += [n["detail"] for n in mstNpDetail
                        if n["id"] == npId][0].replace("[{0}]", r"\[Lv\]").replace("[g][o]▲[/o][/g]", ":small_red_triangle:")
            np_desc += '\n\n'
        if len(np_desc) > 0:
            np_desc = "**宝具強化**\n" + np_desc + "\n"

    """
    スキル強化をチェックする
    """
    skill_desc = ""
    if mstSkill_file in updatefiles:
        # 集合演算で新idだけ抽出
        mstSvt_list = [q for q in mstSvt
                       if (q["type"] == 1 or q["type"] == 2)
                       and q["id"] and q["collectionNo"] != 0]
        mstSvtId_list = [q["id"] for q in mstSvt
                         if (q["type"] == 1 or q["type"] == 2)
                         and q["id"] and q["collectionNo"] != 0]
        mstSvtSkill = load_file(mstSvtSkill_file, cid)
        svtSkill = set([s["skillId"] for s in mstSvtSkill
                        if s["svtId"] in mstSvtId_list and s["priority"] > 1])
        mstSvtSkill_prev = json.loads(repo.git.show(cid + "^:"
                                                    + mstSvtSkill_file))
        svtSkill_prev = set([s["skillId"] for s in mstSvtSkill_prev
                             if s["svtId"] in mstSvtId_list
                             and s["priority"] > 1])
        svtSkillIds = list(svtSkill - svtSkill_prev)
        logger.debug(svtSkillIds)
        # fields作成
        for svtSkill in svtSkillIds:
            skill_ct = [s["chargeTurn"] for s in mstSkillLv
                        if s["skillId"] == svtSkill and s["lv"] == 1][0]
            # skillId から servert id
            svtId = [s["svtId"] for s in mstSvtSkill
                     if s["skillId"] == svtSkill][0]
            logger.debug(svtId)
            try:
                svt = [s for s in mstSvt_list if s["id"] == svtId][0]
                if face_icon == -1:
                    face_icon = svtId
            except Exception as e:
                logger.exception(e)
                continue
            logger.debug(svt)
            skill_desc += ":mage: No." + str(svt["collectionNo"])
            skill_desc += ' ' + cost2rarity[svt["cost"]] + ' '
            skill_desc += id2class[svt["classId"]] + ' ' + svt["name"] + "\n"

            # 保有スキルを出力
            skill_desc += "[" + [k["name"] for k in mstSkill
                                 if k["id"] == svtSkill][0] + "]"
            skillNum = [s["skillNum"] for s in mstSvtSkill
                        if s["skillId"] == svtSkill][0]
            skill_desc += "(" + "https://apps.atlasacademy.io/db/#/JP/servant/"
            skill_desc += str(svt["collectionNo"]) + "/skill-" + str(skillNum)
            skill_desc += ") "
            skill_desc += "チャージタイム" + str(skill_ct) + "\n"
            skill_desc += [i["detail"] for i in mstSkillDetail
                           if i["id"] == svtSkill][0].replace("[{0}]", r"\[Lv\]").replace("[g][o]▲[/o][/g]", ":small_red_triangle:")
            skill_desc += '\n\n'
        if len(skill_desc) > 0:
            skill_desc = "**スキル強化**\n" + skill_desc

    if len(np_desc + skill_desc) != 0:
        thumb_url = aa_url + "/GameData/JP/Faces/f_" \
                    + str(face_icon) + "0.png"
        discord.post(username="FGO アップデート",
                     embeds=[{
                              "title": "サーヴァント強化",
                              "thumbnail": {
                                            "url": thumb_url
                                            },
                              "description": np_desc + skill_desc,
                              "color": 5620992}])
        postCount += 1


def output_quest(q_list, title):
    global postCount
    # fields の内容を事前作成
    date_items = []
    prev_openedAt = 0
    prev_closedAt = 0
    items = []
    # 時間を分けたデータを作成
    for i, quest in enumerate(q_list):
        openedAt = datetime.fromtimestamp(quest[5])
        closedAt = datetime.fromtimestamp(quest[6])
        if i == 0:
            itemdate = '```開始 | ' + str(openedAt) \
                       + '\n終了 | ' + str(closedAt) + '```'
            items.append(','.join([str(n) for n in quest[:-2]]))
            prev_openedAt = openedAt
            prev_closedAt = closedAt
        elif prev_openedAt == openedAt and prev_closedAt == closedAt:
            items.append(','.join([str(n) for n in quest[:-2]]))
        else:
            date_item = {"date": itemdate, "items": items}
            date_items.append(date_item)
            itemdate = '```開始 | ' + str(openedAt) \
                       + '\n終了 | ' + str(closedAt) + '```'
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
        field = [{"name": ":date: 日時",
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
                     embeds=[{
                                "title": title + "更新",
                                "fields": fields,
                                "color": 5620992}])
        postCount += 1


def check_quests(updatefiles, cid="HEAD"):
    """
    クエストをチェックする
    """
    if mstQuest_file not in updatefiles:
        return
    # 集合演算で新idだけ抽出
    mstQuest = load_file(mstQuest_file, cid)
    quest = set([s["id"] for s in mstQuest])
    mstQuest_prev = json.loads(repo.git.show(cid + "^:" + mstQuest_file))
    quest_prev = set([s["id"] for s in mstQuest_prev])
    questIds = list(quest - quest_prev)
    logger.debug(questIds)

    mstQuest_list = [q for q in mstQuest if q["id"] in questIds
                     if q["type"] != 7]
    mstQuest_list = sorted(mstQuest_list, key=lambda x: x['openedAt'])

    mstQuestInfo_list = load_file(mstQuestInfo_file, cid)
    mstQuestPhase_list = load_file(mstQuestPhase_file, cid)
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
        if "高難易度" in quest["name"]:
            enemy = questId2classIds[quest["id"]]
            q_list.append([quest["id"], quest["name"],
                           'Lv' + quest["recommendLv"],
                           'AP' + str(quest["actConsume"]),
                           list2class(enemy),
                           quest["openedAt"],
                           quest["closedAt"]])
            continue
        for q in mstQuestInfo_list:
            if q["questId"] == quest["id"]:
                if quest["id"] not in questId2classIds.keys():
                    enemy = ""
                else:
                    enemy = questId2classIds[quest["id"]]
                if quest["id"] > 94000000:
                    q_list.append([quest["id"], quest["name"],
                                   'Lv' + quest["recommendLv"],
                                   'AP' + str(quest["actConsume"]),
                                   list2class(enemy),
                                   quest["openedAt"],
                                   quest["closedAt"]])
                else:
                    fq_list.append([quest["id"], quest["name"],
                                    'Lv' + quest["recommendLv"],
                                    'AP' + str(quest["actConsume"]),
                                    list2class(enemy),
                                    quest["openedAt"],
                                    quest["closedAt"]])
                break

    logger.debug(q_list)
    logger.debug(fq_list)
    output_quest(q_list, "イベントクエスト")
    output_quest(fq_list, "恒常フリークエスト")


def check_missionCondition(updatefiles, cid="HEAD"):
    """
    特別ミッションのクリア条件をチェックする
    mstEventMisson->gift  "id": 8031015,
    mstEventMissonCondition->"targetIds"8031014 "missionId": 8031015,
    mstEventMissonConditionDetail "id": 8031014 "targetIds":(アイテム、クエスト)
    """
    global postCount
    global id2itemName
    if mstEventMissionCondition_file not in updatefiles:
        return
    if len(id2itemName.keys()) == 0:
        mstItem = load_file(mstItem_file, cid)
        mstSvt = load_file(mstSvt_file, cid)
        mstCommandCode = load_file(mstCommandCode_file, cid)
        mstQuest = load_file(mstQuest_file, cid)
        id2itemName = {item["id"]: item["name"] for item in mstItem}
        id2itemName.update({item["id"]: item["name"] for item in mstSvt})
        id2itemName.update({item["id"]: item["name"]
                            for item in mstCommandCode})
        id2itemName.update({item["id"]: item["name"] for item in mstQuest})

    mEM = load_file(mstEventMission_file, cid)
    id2type = {m["id"]: m["type"] for m in mEM}
    # 集合演算で新idだけ抽出
    mEMC = load_file(mstEventMissionCondition_file, cid)
    EMC = set([s["id"] for s in mEMC
               if s["targetIds"] != [0]
               and int(s["targetIds"][0]/100) != 30000
               and (s["condType"] == 22 or s["condType"] == 2)
               and id2type[s["missionId"]] == 6
               ])
    mEMC_prev = json.loads(repo.git.show(cid + "^:"
                           + mstEventMissionCondition_file))
    EMC_prev = set([s["id"] for s in mEMC_prev
                    if s["targetIds"] != [0]
                    and int(s["targetIds"][0]/100) != 30000
                    and (s["condType"] == 22 or s["condType"] == 2)
                    and id2type[s["missionId"]] == 6
                    ])
    EMCIds = list(EMC - EMC_prev)
    logger.debug(EMCIds)

    mEMCd = load_file(mstEventMissionConditionDetail_file, cid)

    fields = []
    for EMCId in EMCIds:
        mission = [m for m in mEMC if m["id"] == EMCId][0]
        name = mission["conditionMessage"]
        targetIds = [m['targetIds'] for m in mEMCd
                     if mission["targetIds"][0] == m["id"]][0]
        if max(targetIds) < 6000:
            value = " Traitsに下記の数値を入力して[検索]"
            value += "(https://apps.atlasacademy.io/db/#/JP/entities)\n"
            value += "- " + str(targetIds[0])
        else:
            value = "- "
            value += "\n- ".join([id2itemName[t] for t in targetIds])
        fields.append({"name": name, "value": value})

    if len(fields) > 0:
        discord.post(username="FGO アップデート",
                     embeds=[{
                            "title": "ミッション条件更新",
                            "fields": fields,
                            "color": 5620992}])
        postCount += 1


def check_mastermissions(EM_list):
    """
    マスターミッションをチェックする
    """
    global postCount
    if len(EM_list) != 0:
        thumb_url = aa_url + "/GameData/JP/Items/16.png"
        sdate = str(datetime.fromtimestamp(EM_list[0]["startedAt"]))
        edate = str(datetime.fromtimestamp(EM_list[0]["endedAt"]))
        date_value = '```開始 | ' + sdate + '\n終了 | ' + edate + '```'
        vdata = '\n'.join(['- ' + n["detail"] for n in EM_list])
        discord.post(username="FGO アップデート",
                     embeds=[{"title": "マスターミッション(ウィークリー)更新",
                              "thumbnail": {
                                            "url": thumb_url
                                            },
                              "fields": [{
                                          "name": ":date: 日時",
                                          "value": date_value
                                          },
                                         {
                                          "name": "ミッション",
                                          "value": vdata
                                          }
                                         ],
                              "color": 5620992}])
        postCount += 1


def check_eventmissions(EML_list):
    """
    イベントミッションをチェックする
    """
    global postCount
    if len(EML_list) != 0:
        sdate = str(datetime.fromtimestamp(EML_list[0]["startedAt"]))
        edate = str(datetime.fromtimestamp(EML_list[0]["endedAt"]))
        date_value = '```開始 | ' + sdate + '\n終了 | ' + edate + '```'
        vdata = '\n'.join(['- ' + n["detail"] for n in EML_list])
        discord.post(username="FGO アップデート",
                     embeds=[{
                                "title": "限定ミッション更新",
                                "fields": [
                                    {
                                        "name": ":date: 日時",
                                        "value": date_value
                                    }, {
                                        "name": "ミッション",
                                        "value": vdata
                                    }
                                ],
                                "color": 5620992}])
        postCount += 1


def check_dailymissions(EMD_list):
    """
    デイリーミッションをチェックする
    """
    global postCount
    if len(EMD_list) != 0:
        thumb_url = aa_url + "/GameData/JP/Items/7.png"
        sdate = str(datetime.fromtimestamp(EMD_list[0]["startedAt"]))
        edate = str(datetime.fromtimestamp(EMD_list[0]["endedAt"]))
        date_value = '```開始 | ' + sdate + '\n終了 | ' + edate + '```'
        vdata = '\n'.join(['- ' + n["detail"] for n in EMD_list])
        discord.post(username="FGO アップデート",
                     embeds=[{
                                "title": "ミッション(デイリー)更新",
                                "thumbnail": {
                                              "url": thumb_url
                                              },
                                "fields": [
                                    {
                                        "name": ":date: 日時",
                                        "value": date_value
                                    }, {
                                        "name": "ミッション",
                                        "value": vdata
                                    }
                                ],
                                "color": 5620992}])
        postCount += 1


def check_raddermissions(RM_list, cid):
    """
    イベントミッション(はしご式)をチェックする
    Discord の文字制限2000字を超えるのでファイルで出力
    """
    global postCount
    # 一時ファイルをつくらないで投稿する方法が良く分からないのでtempfileを使用

    if len(RM_list) != 0:
        global id2itemName
        if len(id2itemName.keys()) == 0:
            mstItem = load_file(mstItem_file, cid)
            mstSvt = load_file(mstSvt_file, cid)
            mstCommandCode = load_file(mstCommandCode_file, cid)
            mstQuest = load_file(mstQuest_file, cid)
            id2itemName = {item["id"]: item["name"] for item in mstItem}
            id2itemName.update({item["id"]: item["name"] for item in mstSvt})
            id2itemName.update({item["id"]: item["name"]
                                for item in mstCommandCode})
            id2itemName.update({item["id"]: item["name"] for item in mstQuest})

        pattern1 = r"(?P<month>[0-9]{1,2})/(?P<day>[0-9]{1,2})"
        pattern2 = r"(?P<hour>([0-9]|[01][0-9]|2[0-3])):(?P<min>[0-5][0-9])"
        pattern = pattern1 + " " + pattern2

        EMC = load_file(mstEventMissionCondition_file,
                        cid)
        mCondition = {m["missionId"]: m["conditionMessage"] for m in EMC[::-1]}
        mCondition_final = {m["missionId"]: m["conditionMessage"] for m in EMC}
        mstGift = load_file(mstGift_file, cid)
        # No. 順出力
        RM_list = sorted(RM_list, key=lambda x: x['dispNo'])
        s = '〔イベントミッションリスト (No.順)〕\n'
        s += '開始: ' + str(datetime.fromtimestamp(RM_list[0]["startedAt"]))
        s += '\n'
        s += '終了: ' + str(datetime.fromtimestamp(RM_list[0]["endedAt"]))
        s += '\n\n'
        # No. 順出力のときは【】で記述される開放部分は出力しない

        for n in RM_list:
            gifts = [(id2itemName[g["objectId"]],
                      g["num"]) for g in mstGift if g["id"] == n["giftId"]]
            s += '- No.' + str(n["dispNo"]) + '\t' \
                 + re.sub(r'【.*?】', '',
                          mCondition_final[n["id"]].replace("\n", "")) \
                 + '\t'
            s += "\t".join("{} x{:,}".format(gift[0],
                                             gift[1]) for gift in gifts)
            s += "\n"

        # 開放順出力
        s += '\n'
        s += '\n'
        s += '〔イベントミッションリスト (開放日時順)〕\n'

        # "conditionMessage" で振り分け
        new_list = []
        for em in RM_list:
            cond = mCondition[em["id"]]
            m1 = re.search(pattern, cond)
            if m1:
                str_o = r"\g<month>/\g<day> \g<hour>:\g<min>"
                opendaytime = re.sub(pattern, str_o, m1.group())
                # 年は指定されてないので開始時刻から取得
                year = str(datetime.fromtimestamp(em["startedAt"]).year)
                dt_date = datetime.strptime(year + '/' + opendaytime,
                                            "%Y/%m/%d %H:%M")
                openedAt = int(dt_date.timestamp())
                em["openedAt"] = openedAt
                em["has_data"] = True
            else:
                em["openedAt"] = em["startedAt"]
            new_list.append(em)
        new_list = sorted(new_list, key=lambda x: x['openedAt'])

        prev_time = 0
        for i, l in enumerate(new_list):
            if prev_time != l['openedAt']:
                if i != 0:
                    s += '\n'
                s += "開放日: " + str(datetime.fromtimestamp(l['openedAt']))
                s += '\n'
                prev_time = l['openedAt']
            s += '- No.' + str(l["dispNo"]) + ' '
            s += mCondition_final[l["id"]]
            s += '\n'

        tmpdir = tempfile.TemporaryDirectory()
        # 日本語のファイル名には対応していない
        savefile = os.path.join(tmpdir.name, 'Event Mission List.txt')
        with open(savefile, mode='w', encoding="UTF-8") as f:
            f.write(s)
        discord.post(username="FGO アップデート",
                     file={
                           "file1": open(savefile, "rb"),
                           },
                     )
        tmpdir.cleanup()
        postCount += 1


def check_missions(updatefiles, cid="HEAD"):
    """
    ミッションをチェックする
    """
    if mstEventMission_file not in updatefiles:
        return
    # 集合演算で新idだけ抽出
    mstEventMission = load_file(mstEventMission_file, cid)
    event = set([s["id"] for s in mstEventMission])
    mstEventMission_prev = json.loads(repo.git.show(cid + "^:"
                                      + mstEventMission_file))
    event_prev = set([s["id"] for s in mstEventMission_prev])
    eventMissiontIds = list(event - event_prev)
    logger.debug(eventMissiontIds)

    mstRadderMission_list = [m for m in mstEventMission
                             if m["type"] == 1
                             and m["id"] in eventMissiontIds]
    mstRadderMission_list = sorted(mstRadderMission_list,
                                   key=lambda x: x["startedAt"])
    mstEventMission_list = [m for m in mstEventMission
                            if m["type"] == 2
                            and m["id"] in eventMissiontIds]
    mstEventMission_list = sorted(mstEventMission_list,
                                  key=lambda x: x['closedAt'])
    mstEventMissionDaily_list = [m for m in mstEventMission
                                 if m["type"] == 3
                                 and m["id"] in eventMissiontIds]
    mstEventMissionDaily_list = sorted(mstEventMissionDaily_list,
                                       key=lambda x: x['closedAt'])
    mstEventMissionLimited_list = [m for m in mstEventMission
                                   if m["type"] == 6
                                   and m["id"] in eventMissiontIds]
    mstEventMissionLimited_list = sorted(mstEventMissionLimited_list,
                                         key=lambda x: x['closedAt'])

    check_raddermissions(mstRadderMission_list, cid)
    check_eventmissions(mstEventMissionLimited_list)
    check_mastermissions(mstEventMission_list)
    check_dailymissions(mstEventMissionDaily_list)


def output_shop(shop_list, shopname):
    """
    ショップデータを出力する
    """
    global postCount
    # fields の内容を事前作成
    date_items = []
    prev_openedAt = 0
    prev_closedAt = 0
    items = []
    # 時間を分けたデータを作成
    for i, item in enumerate(shop_list):
        openedAt = datetime.fromtimestamp(item["openedAt"])
        closedAt = datetime.fromtimestamp(item["closedAt"])
        # price = str(item["prices"][0])
        # limitNum = str(item["limitNum"]) if item["limitNum"] != 0 else "∞"
        if i == 0:
            itemdate = '```開始 | ' + str(openedAt) \
                       + '\n終了 | ' + str(closedAt) + '```'
            # items.append(item["name"] + " @" + price + " x" + limitNum)
            items.append(item)
            prev_openedAt = openedAt
            prev_closedAt = closedAt
        elif prev_openedAt == openedAt and prev_closedAt == closedAt:
            # items.append(item["name"] + " @" + price + " x" + limitNum)
            items.append(item)
        else:
            date_item = {"date": itemdate, "items": items}
            date_items.append(date_item)
            itemdate = '```開始 | ' + str(openedAt) \
                       + '\n終了 | ' + str(closedAt) + '```'
            items = []
            # items.append(item["name"] + " @" + price + " x" + limitNum)
            items.append(item)
            prev_openedAt = openedAt
            prev_closedAt = closedAt
    if len(items) > 0:
        items = sorted(sorted(items, key=lambda x: x["id"]),
                       key=lambda x: x["itemIds"][0], reverse=True)
        date_item = {"date": itemdate, "items": items}
        date_items.append(date_item)
    # ソート
    # filedを作成
    fields = []
    for date_item in date_items:
        logger.debug(date_item)
        field = [{"name": ":date: 日時",
                 "value": date_item["date"]
                  }]
        prev_itemId = 0
        for i, item in enumerate(date_item["items"]):
            itemId = item["itemIds"][0]
            if i == 0:
                if itemId in [0, 18]:
                    f = {"name": "アイテム"}
                else:
                    f = {"name": "{}で交換可能なアイテム".format(id2itemName[itemId])}
                f["value"] = "- " + item["name"] \
                             + " @" + str(item["prices"][0]) \
                             + " x" + (str(item["limitNum"])
                                       if item["limitNum"] != 0 else "∞")
                prev_itemId = itemId
            elif prev_itemId == itemId:
                f["value"] += "\n- " + item["name"] \
                              + " @" + str(item["prices"][0])\
                              + " x" + (str(item["limitNum"])
                                        if item["limitNum"] != 0 else "∞")
            else:
                field.append(f)
                if itemId in [0, 18]:
                    f = {"name": "アイテム"}
                else:
                    f = {"name": "{}で交換可能なアイテム".format(id2itemName[itemId])}
                f["value"] = "- " + item["name"] \
                             + " @" + str(item["prices"][0]) \
                             + " x" + (str(item["limitNum"])
                                       if item["limitNum"] != 0 else "∞")
                prev_itemId = itemId
        if len(f) > 0:
            field.append(f)
        fields += field
    logger.debug(fields)

    if len(fields) != 0:
        aa_asset_url = "https://assets.atlasacademy.io"
        if shopname == "マナプリズム交換":
            thumb_url = aa_asset_url + "/GameData/JP/Items/7.png"
            discord.post(username="FGO アップデート",
                         embeds=[{
                                  "title": shopname + "更新",
                                  "thumbnail": {
                                                "url": thumb_url
                                                },
                                  "fields": fields,
                                  "color": 5620992}])
            postCount += 1
        elif shopname == "レアプリズム交換":
            thumb_url = aa_asset_url + "/GameData/JP/Items/18.png"
            discord.post(username="FGO アップデート",
                         embeds=[{
                                  "title": shopname + "更新",
                                  "thumbnail": {
                                                "url": thumb_url
                                                },
                                  "fields": fields,
                                  "color": 5620992}])
            postCount += 1
        else:
            discord.post(username="FGO アップデート",
                         embeds=[{
                                  "title": shopname + "更新",
                                  "fields": fields,
                                  "color": 5620992}])
            postCount += 1


def check_shop(updatefiles, cid="HEAD"):
    """
    ショップをチェックする
    1 イベント限定ショップ
    2 マナプリズム
    3 レアプリズム
    8 サウンドプレイヤー
    """
    if mstShop_file not in updatefiles:
        return
    # 集合演算で新idだけ抽出
    mstShop = load_file(mstShop_file, cid)
    shop = set([s["id"] for s in mstShop])
    mstShop_prev = json.loads(repo.git.show(cid + "^:" + mstShop_file))
    shop_prev = set([s["id"] for s in mstShop_prev])
    shopIds = list(shop - shop_prev)
    logger.debug(shopIds)

    global id2itemName
    if len(id2itemName.keys()) > 0:
        mstItem = load_file(mstItem_file, cid)
        mstSvt = load_file(mstSvt_file, cid)
        mstCommandCode = load_file(mstCommandCode_file, cid)
        mstQuest = load_file(mstQuest_file, cid)
        id2itemName = {item["id"]: item["name"] for item in mstItem}
        id2itemName.update({item["id"]: item["name"] for item in mstSvt})
        id2itemName.update({item["id"]: item["name"]
                            for item in mstCommandCode})
        id2itemName.update({item["id"]: item["name"] for item in mstQuest})

    eventShop_list = [m for m in mstShop
                      if m["shopType"] == 1
                      and m["id"] in shopIds]
    eventShop_list = sorted(eventShop_list, key=lambda x: x['closedAt'])
    logger.debug("eventShop_list: %s", eventShop_list)
    manaShop_list = [m for m in mstShop
                     if m["shopType"] == 2
                     and m["id"] in shopIds]
    manaShop_list = sorted(manaShop_list, key=lambda x: x['closedAt'])
    logger.debug("manaShop_list: %s", manaShop_list)
    rareShop_list = [m for m in mstShop
                     if m["shopType"] == 3
                     and m["id"] in shopIds]
    rareShop_list = sorted(rareShop_list, key=lambda x: x['closedAt'])
    logger.debug("rareShop_list: %s", rareShop_list)
    soundPayer_list = [m for m in mstShop
                       if m["shopType"] == 8
                       and m["id"] in shopIds]
    logger.debug("soundPayer_list: %s", soundPayer_list)
    output_shop(eventShop_list, "イベントショップ")
    output_shop(manaShop_list, "マナプリズム交換")
    output_shop(rareShop_list, "レアプリズム交換")
    output_shop(soundPayer_list, "サウンドプレイヤー")


def check_svtfilter(updatefiles, cid="HEAD"):
    """
    サーヴァント強化フィルターの更新チェック
    """
    global postCount
    if mstSvtFilter_file not in updatefiles:
        return
    # 集合演算で新idだけ抽出
    mstSvtFilter = load_file(mstSvtFilter_file, cid)
    SvtFilter = set([s["id"] for s in mstSvtFilter])
    mstSvtFilter_prev = json.loads(repo.git.show(cid + "^:"
                                   + mstSvtFilter_file))
    SvtFilter_prev = set([s["id"] for s in mstSvtFilter_prev])
    SvtFilterIds = list(SvtFilter - SvtFilter_prev)
    logger.debug(SvtFilterIds)

    mstSvt_list = [q for q in mstSvt
                   if (q["type"] == 1 or q["type"] == 2)
                   and q["collectionNo"] not in mstSvt
                   and q["collectionNo"] != 0]
    mstSvtFilter_list = [m for m in mstSvtFilter
                         if m["id"] in SvtFilterIds]
    logger.debug("mstSvtFilter_list: %s", mstSvtFilter_list)
    mstSvtF_dic = {m["id"]: {"name": m["name"],
                             "cost": m["cost"],
                             "classId": m["classId"]} for m in mstSvt_list}
    logger.debug("mstSvtFilter_list: %s", mstSvtFilter_list)
    for svtFilter in mstSvtFilter_list:
        svts = {}
        for svtId in svtFilter["svtIds"]:
            if mstSvtF_dic[svtId]["classId"] not in svts.keys():
                svts[mstSvtF_dic[svtId]["classId"]
                     ] = [{"name": mstSvtF_dic[svtId]["name"],
                           "cost": mstSvtF_dic[svtId]["cost"]}]
            else:
                svts[mstSvtF_dic[svtId]["classId"]
                     ].append({"name": mstSvtF_dic[svtId]["name"],
                               "cost": mstSvtF_dic[svtId]["cost"]})
        svts = sorted(svts.items())
        logger.debug(svts)
        # filelds を作成
        fields = []
        for svt in svts:
            out = sorted(svt[1], key=lambda x: x['cost'], reverse=True)
            fields.append({"name": id2class[svt[0]],
                           "value": '\n'.join(['- ' + cost2rarity[m["cost"]]
                                               + " " + m["name"]
                                               for m in out])})
        discord.post(username="FGO アップデート",
                     embeds=[{
                                "title": svtFilter["name"] + "フィルター更新",
                                "fields": fields,
                                "color": 5620992}])
        postCount += 1


def plot_equiipExp(name, mc_exp):
    """
    マスター装備の必要経験値をプロットする
    """
    # ロードに時間がかかり、かつたまにしか実行されないため遅延 import
    import matplotlib.pyplot as plt
    global postCount
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
                 file={
                       "file1": open(savefile, "rb"),
                       },
                 )
    tmpdir.cleanup()
    postCount += 1


def check_mstEquip(updatefiles, cid="HEAD"):
    """
    マスター装備の更新チェック
    """
    if mstEquip_file not in updatefiles:
        return
    global postCount
    # 集合演算で新idだけ抽出
    mstEquip = load_file(mstEquip_file, cid)
    Equip = set([s["id"] for s in mstEquip])
    mstEquip_prev = json.loads(repo.git.show(cid + "^:" + mstEquip_file))
    Equip_prev = set([s["id"] for s in mstEquip_prev])
    equipIds = list(Equip - Equip_prev)
    logger.debug(equipIds)

    mstEquipExp = load_file(mstEquipExp_file, cid)
    mstEquipSkill = load_file(mstEquipSkill_file, cid)

    mstEquip_list = [m for m in mstEquip
                     if m["id"] in equipIds]
    logger.debug("mstEquip_list: %s", mstEquip_list)
    for equip in mstEquip_list:
        skill1_id = [s["skillId"] for s in mstEquipSkill
                     if s["equipId"] == equip["id"] and s["num"] == 1][0]
        skill2_id = [s["skillId"] for s in mstEquipSkill
                     if s["equipId"] == equip["id"] and s["num"] == 2][0]
        skill3_id = [s["skillId"] for s in mstEquipSkill
                     if s["equipId"] == equip["id"] and s["num"] == 3][0]
        skill1_ct = [s["chargeTurn"] for s in mstSkillLv
                     if s["skillId"] == skill1_id and s["lv"] == 1][0]
        skill2_ct = [s["chargeTurn"] for s in mstSkillLv
                     if s["skillId"] == skill2_id and s["lv"] == 1][0]
        skill3_ct = [s["chargeTurn"] for s in mstSkillLv
                     if s["skillId"] == skill3_id and s["lv"] == 1][0]
        mc_exp = [0] + [e["exp"] for e in mstEquipExp
                        if e["equipId"] == equip["id"]][:-1]
        logger.debug("mc_exp: %s", mc_exp)
        discord.post(username="FGO アップデート",
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
        postCount += 1
        plot_equiipExp(equip["name"], mc_exp)


def check_eventReward(updatefiles, cid="HEAD"):
    """
    ポイント報酬を出力する
    """
    if mstEventReward_file not in updatefiles:
        return
    global postCount
    # 集合演算で新idだけ抽出
    mER = load_file(mstEventReward_file, cid)
    mER_prev = json.loads(repo.git.show(cid + "^:" + mstEventReward_file))
    mstGift = load_file(mstGift_file, cid)
    giftId2reward = {g["id"]: {"itemId": g["objectId"], "num": g["num"]}
                     for g in mstGift}
    # 新規追加のイベントIDを検出する
    ER = set([s["eventId"] for s in mER])
    logger.debug(ER)
    ER_prev = set([s["eventId"] for s in mER_prev])
    logger.debug(ER_prev)
    evIds = list(ER - ER_prev)
    logger.debug(evIds)
    for evId in evIds:
        description = ""
        pointReward = [(i["point"], i["giftId"]) for i in mER
                       if i["eventId"] == evId]
        for p in pointReward:
            description += "{:,}".format(p[0]) + "\t"
            rew = giftId2reward[p[1]]
            description += id2itemName[rew["itemId"]] + "\t"
            description += "x{:,}".format(rew["num"]) + "\n"

        discord.post(username="FGO アップデート",
                     embeds=[{
                              "title": "ポイント報酬更新",
                              "description": description,
                              "color": 5620992}])
        postCount += 1


def check_box(updatefiles, cid="HEAD"):
    """
    ボックス報酬を出力する
    """
    if mstBoxGacha_file not in updatefiles:
        return
    global postCount
    global id2itemName
    if len(id2itemName.keys()) == 0:
        mstItem = load_file(mstItem_file, cid)
        mstSvt = load_file(mstSvt_file, cid)
        mstCommandCode = load_file(mstCommandCode_file, cid)
        mstQuest = load_file(mstQuest_file, cid)
        id2itemName = {item["id"]: item["name"] for item in mstItem}
        id2itemName.update({item["id"]: item["name"] for item in mstSvt})
        id2itemName.update({item["id"]: item["name"]
                            for item in mstCommandCode})
        id2itemName.update({item["id"]: item["name"] for item in mstQuest})

    # 集合演算で新idだけ抽出
    mstBG = load_file(mstBoxGacha_file, cid)
    BG = set([s["id"] for s in mstBG])
    mstBG_prev = json.loads(repo.git.show(cid + "^:" + mstBoxGacha_file))
    BG_prev = set([s["id"] for s in mstBG_prev])
    BGIds = list(BG - BG_prev)
    logger.debug(BGIds)
    mstGift = load_file(mstGift_file, cid)
    giftId2itemId = {i["id"]: i["objectId"] for i in mstGift}
    giftId2itemNum = {i["id"]: i["num"] for i in mstGift}

    mstBGB = load_file(mstBoxGachaBase_file, cid)
    for BG in BGIds:
        BGdic = [b for b in mstBG if b["id"] == BG][0]
        description = ":gift:**1回目のラインナップ**\n"
        pLineup = {}
        for i, baseId in enumerate(BGdic["baseIds"]):
            # print(str(baseId)[-2:] + "回目")
            lineups = [(i["targetId"], i["maxNum"]) for i in mstBGB
                       if i["id"] == baseId]
            cLineup = {}
            for linup in lineups:
                try:
                    item = id2itemName[giftId2itemId[linup[0]]]
                    itemNum = "({:,})".format(giftId2itemNum[linup[0]]) \
                              if giftId2itemNum[linup[0]] > 1 else ""
                    cLineup[item + itemNum] = linup[1]
                except Exception as e:
                    logger.exception(e)
                    # cLinenup.append("{} x{}\n".format(linup[0], linup[1]))
                    cLineup[linup[0]] = linup[1]
            if i == 0:
                # 一覧出力
                description += '- '
                lineup1 = ["{} x{}\n".format(ln, cLineup[ln]) for ln
                           in cLineup.keys()]
                description += '- '.join(lineup1)
            else:
                # 差分作成
                desc_inner = ""
                for p in pLineup.keys():
                    if p in cLineup.keys():
                        if pLineup[p] == cLineup[p]:
                            continue
                        desc_inner += "- " + p + ' x' + str(pLineup[p]) \
                                      + "→" + str(cLineup[p]) + "\n"
                        pLineup[p] = cLineup[p]
                    else:
                        desc_inner += "- " + p + ' x' \
                                      + str(pLineup[p]) + "→0\n"
                for c in cLineup.keys():
                    if c in pLineup.keys():
                        if pLineup[c] == cLineup[c]:
                            continue
                        desc_inner += "- " + c + ' x' + str(pLineup[c]) \
                                      + "→" + str(cLineup[c]) + "\n"
                    else:
                        desc_inner += "- " + c + ' x0→' \
                                      + str(cLineup[c]) + "\n"
                if desc_inner != "":
                    description += "\n:gift:**" \
                                   + str(int(str(baseId - 1)[-2:])) + "回目→" \
                                   + str(int(str(baseId)[-2:])) + "回目**\n"
                    description += desc_inner
            pLineup = cLineup.copy()

        payTargetId = [bg["payTargetId"] for bg in mstBG if bg["id"] == BG][0]
        payTarget = id2itemName[payTargetId]
        discord.post(username="FGO アップデート",
                     embeds=[{
                              "title": "【ボックス】" + payTarget
                                       + "交換 プレゼントラインナップ",
                              "description": description,
                              "color": 5620992}])
        postCount += 1


def check_costume(updatefiles, cid="HEAD"):
    """
    霊衣更新を出力する
    """
    global mstSvt
    global mstClass
    global id2class
    global postCount
    if mstSvtCostume_file not in updatefiles:
        return
    if len(mstSvt) == 0:
        mstSvt = load_file(mstSvt_file, args.cid)
    if len(mstClass) == 0:
        mstClass = load_file(mstClass_file, args.cid)
        id2class = {c["id"]: c["name"] for c in mstClass}
    # 集合演算で新idだけ抽出
    mSC = load_file(mstSvtCostume_file, cid)
    SC = set([s["costumeCollectionNo"] for s in mSC])
    mESC_prev = json.loads(repo.git.show(cid + "^:" + mstSvtCostume_file))
    ESC_prev = set([s["costumeCollectionNo"] for s in mESC_prev])
    SCIds = list(SC - ESC_prev)
    logger.debug(SCIds)

    fields = []
    face_icon = -1
    for SCId in SCIds:
        costume = [sc for sc in mSC if sc["costumeCollectionNo"] == SCId][0]
        svt = [s for s in mstSvt if s["id"] == costume["svtId"]][0]
        if face_icon == -1:
            face_icon = svt["id"]
        name = "No." + str(svt["collectionNo"])
        name += ' ' + cost2rarity[svt["cost"]] + ' '
        name += id2class[svt["classId"]] + ' ' + svt["name"] + '\n'
        value = "[" + costume["name"]
        value += "]" \
                 + "(https://apps.atlasacademy.io/db/#/JP/servant/" \
                 + str(svt["collectionNo"]) + "/materials)"

        value += '```' + costume["detail"] + '```\n'
        value += '開放条件: ' + costume["itemGetInfo"] + '\n'

        fields.append({"name": name,
                       "value": value})
    if len(SCIds) > 0:
        thumb_url = aa_url + "/GameData/JP/Faces/f_" \
                    + str(face_icon) + "0.png"
        discord.post(username="FGO アップデート",
                     embeds=[{
                                "title": "霊衣更新",
                                "thumbnail": {
                                              "url": thumb_url
                                              },
                                "fields": fields,
                                "color": 5620992}])
        postCount += 1


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
                               embeds=[{
                                "title": "Error",
                                "description": "Proccess locked",
                                "color": 15158332}])
            return

        func(*args, **kwargs)

        # 対象のpidが有効でなければロックされないので例外が出ても実質問題無し
        lock.close()

    return lock


def post(func, updatefiles, cid="HEAD"):
    """
    エラーになっても止まらないように
    """
    try:
        func(updatefiles, cid)
    except Exception as e:
        logger.exception(e)
        discord_error.post(username="FGO アップデート",
                           embeds=[{
                                    "title": func.__name__ + "Error",
                                    "description": "Check server log",
                                    "color": 15158332}])


@lock_or_through
def main(args):
    global postCount
    if args.cid != "HEAD" or check_update():
        updatefiles = repo.git.diff(args.cid + '^..'
                                    + args.cid, name_only=True).split('\n')
        if mstSvtFilter_file in updatefiles or mstSvt_file in updatefiles:
            global mstSvt
            global id2class
            mstSvt = load_file(mstSvt_file, args.cid)
            mstClass = load_file(mstClass_file, args.cid)
            id2class = {c["id"]: c["name"] for c in mstClass}
        if mstEquip_file in updatefiles or mstSvt_file in updatefiles:
            # 複数個所で使用するファイルを読んでおく
            global mstSkill
            global mstSkillDetail
            global mstSkillLv
            global mstFunc
            mstSkill = load_file(mstSkill_file, args.cid)
            mstSkillDetail = load_file(mstSkillDetail_file, args.cid)
            mstSkillLv = load_file(mstSkillLv_file, args.cid)
            mstFunc = load_file(mstFunc_file, args.cid)

        funcs = [check_gacha, check_svt, check_strengthen, check_quests,
                 check_missions, check_shop, check_eventReward, check_box,
                 check_svtfilter, check_mstEquip, check_costume,
                 check_missionCondition, check_datavar]
        for func in funcs:
            post(func, updatefiles, cid=args.cid)

    if postCount > 10:
        description = "bot が自動公開するのは10件のみです\n" \
                        + str(postCount - 10) + "件は手動で公開してください"
        discord_error.post(username="FGO アップデート",
                           embeds=[{
                                    "title": str(postCount) + "件投稿",
                                    "description": description,
                                    "color": 15158332}])

    # この機能だけは cid 指定の対象外
    postCount += trouble.getTrouble()
    postCount += info_trouble.makeDiffStr()


if __name__ == '__main__':
    # オプションの解析
    parser = argparse.ArgumentParser(
                description='Post FGO update information to Discord'
                )
    # 3. parser.add_argumentで受け取る引数を追加していく
    parser.add_argument('-c', '--cid',
                        default='HEAD', help='COMMIT IDを指定')
    parser.add_argument('-l', '--loglevel',
                        choices=('debug', 'info'), default='info')

    args = parser.parse_args()    # 引数を解析
    logging.basicConfig(
        level=logging.INFO,
        format='%(name)s <%(filename)s-L%(lineno)s>'
               + ' [%(levelname)s] %(message)s',
    )
    logger.setLevel(args.loglevel.upper())

    main(args)
