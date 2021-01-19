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
mstSvtTreasureDevice_file = "JP_tables/svt/mstSvtTreasureDevice.json"
mstTreasureDeviceDetail_file = "JP_tables/treasure/mstTreasureDeviceDetail.json"
mstItem_file = "JP_tables/item/mstItem.json"
mstSvt = []
id2class = {}
mstSkill = []
mstSkillDetail = []
mstSkillLv = []
mstFunc = []
id2itemName = {}

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


def check_datavar(updatefiles, cid="HEAD"):
    """
    アプリバージョンとデータバージョンをチェックする
    """
    if mstver_file not in updatefiles:
        return

    mstver = json.loads(repo.git.show(cid + ":" + mstver_file))
    logger.debug("dateVar: %s", mstver["dateVer"])
    discord.post(username="FGO アップデート",
                 avatar_url=avatar_url,
                 embeds=[{"title": "データ更新",
                          "description": "Version: " + str(mstver["appVer"]) + " DataVer: " + str(mstver["dataVer"]),
                          "color": 5620992}])


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
                                "thumbnail": {
                                              "url": "https://assets.atlasacademy.io/GameData/JP/Items/6.png"
                                              },
                                "fields": fields[:20],
                                "color": 5620992}])
        if len(fields) >= 20:
            discord.post(username="FGO アップデート",
                         avatar_url=avatar_url,
                         embeds=[{
                                    "title": "ガチャ更新",
                                    "image": {"url": "https://view.fate-go.jp/webview/common/images" + gacha_list[0]["detailUrl"] + ".png"},
                                    "thumbnail": {
                                                  "url": "https://assets.atlasacademy.io/GameData/JP/Items/6.png"
                                                  },
                                    "fields": fields[20:],
                                    "color": 5620992}])


def check_gacha(updatefiles, cid="HEAD"):
    """
    ガチャをチェックする
    """
    if mstGacha_file not in updatefiles:
        return
    # 集合演算で新idだけ抽出
    mstGacha = json.loads(repo.git.show(cid + ":" + mstGacha_file))
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
    hp = [s["hpMax"] for s in mstSvtLimit if s["svtId"] == svt["id"] and s["limitCount"] == 4][0]
    atk = [s["atkMax"] for s in mstSvtLimit if s["svtId"] == svt["id"] and s["limitCount"] == 4][0]
    desp = "**ステータス**\n"
    if spoiler:
        desp += "HP " + '||{:,}||'.format(hp) + ", ATK " + '||{:,}||'.format(atk) + ", COST " + str(svt["cost"]) + "\n"
    else:
        desp += "HP " + '{:,}'.format(hp) + ", ATK " + '{:,}'.format(atk) + ", COST " + str(svt["cost"]) + "\n"
    desp += "\n"
    return desp


def make_svtSkills(svt, mstSvtSkill):
    """
    サーヴァントのスキルを作成
    """
    desp = "**保有スキル:**\n"
    try:
        # 敵データなどで存在するときにコケるので try except
        skill1_id = [s["skillId"] for s in mstSvtSkill if s["svtId"] == svt["id"] and s["num"] == 1][0]
        skill2_id = [s["skillId"] for s in mstSvtSkill if s["svtId"] == svt["id"] and s["num"] == 2][0]
        skill3_id = [s["skillId"] for s in mstSvtSkill if s["svtId"] == svt["id"] and s["num"] == 3][0]
        skill1_ct = [s["chargeTurn"] for s in mstSkillLv if s["skillId"] == skill1_id and s["lv"] == 1][0]
        skill2_ct = [s["chargeTurn"] for s in mstSkillLv if s["skillId"] == skill2_id and s["lv"] == 1][0]
        skill3_ct = [s["chargeTurn"] for s in mstSkillLv if s["skillId"] == skill3_id and s["lv"] == 1][0]

        # 保有スキルを出力
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
        desp += [i["detail"] for i in mstSkillDetail if i["id"] == skillId][0].replace("{0}", "Lv")
        desp += "\n\n"
    desp += "||"

    desp += "\n"

    return desp


def make_np(svt, mstTreasureDevice, mstTreasureDeviceDetail, spoiler=False):
    """
    サーヴァントの宝具を作成
    """
    desp = "**宝具:**\n"
    if spoiler:
        desp += "||"
    np = [np for np in mstTreasureDevice if np["seqId"] == svt["id"]][0]
    desp += np["name"]
    desp += "(" + np["ruby"] + ")" + "\n"
    desp += "__ランク__ " + np["rank"] + "\n"
    desp += "__種別__ " + np["typeText"] + "\n"
    if spoiler:
        desp += [n["detail"] for n in mstTreasureDeviceDetail if n["id"] == np["id"]][0].replace("[{0}]", "[Lv]") + "||" + "\n"
    else:
        desp += "```" + [n["detail"] for n in mstTreasureDeviceDetail if n["id"] == np["id"]][0].replace("[{0}]", "[Lv]") + "```" + "\n"
    desp += "\n"
    return desp


def check_svt(updatefiles, cid="HEAD"):
    """
    サーヴァントをチェックする
    """
    if mstSvt_file not in updatefiles:
        return
    mstSvtLimit = json.loads(repo.git.show(cid + ":" + mstSvtLimit_file))
    mstSvtSkill = json.loads(repo.git.show(cid + ":" + mstSvtSkill_file))
    mstTreasureDevice = json.loads(repo.git.show(cid + ":" + mstTreasureDevice_file))
    mstTreasureDeviceDetail = json.loads(repo.git.show(cid + ":" + mstTreasureDeviceDetail_file))
    # 集合演算で新idだけ抽出
    mstSvt = json.loads(repo.git.show(cid + ":" + mstSvt_file))
    svt = set([s["id"] for s in mstSvt if (s["type"] == 1 or s["type"] == 2)])
    mstSvt_prev = json.loads(repo.git.show(cid + "^:" + mstSvt_file))
    svt_prev = set([s["id"] for s in mstSvt_prev if (s["type"] == 1 or s["type"] == 2)])
    gachaIds = list(svt - svt_prev)
    logger.debug(gachaIds)

    mstSvt_list1 = [q for q in mstSvt if (q["type"] == 1 or q["type"] == 2) and q["id"] in gachaIds and q["collectionNo"] != 0]
    mstSvt_list1 = sorted(mstSvt_list1, key=lambda x: x['collectionNo'])
    mstSvt_list2 = [q for q in mstSvt if (q["type"] == 1 or q["type"] == 2) and q["id"] in gachaIds and q["collectionNo"] == 0]
    mstSvt_list = mstSvt_list1 + mstSvt_list2
    logger.debug("mstSvt_list: %s", mstSvt_list)
    id2card = {1: "A", 2: "B", 3: "Q"}
    for svt in mstSvt_list:
        try:
            # スキル無しで事前実装されることがあるので
            if svt["collectionNo"] == 0:
                desp = cost2rarity[svt["cost"]] + ' ' + id2class[svt["classId"]] + ' ||' + svt["name"] + "||(※おそらくストーリーのネタバレを含みます)"
            else:
                desp = "[" + "- No." + str(svt["collectionNo"])
                desp += ' ' + cost2rarity[svt["cost"]] + ' ' + id2class[svt["classId"]] + ' ' + svt["name"] + "]"
                desp += "(" + "https://apps.atlasacademy.io/db/#/JP/servant/" + str(svt["collectionNo"]) + ")\n"
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
            desp += make_np(svt, mstTreasureDevice, mstTreasureDeviceDetail, spoiler=spoiler)
            desp += "**コマンドカード:**\n"
            desp += "||" + cards + "||"
            if svt["cost"] < 7:
                color = "1"
            elif svt["cost"] == 7:
                color = "2"
            else:
                color = "3"
            icon_url = "https://assets.atlasacademy.io/GameData/JP/ClassIcons/class"
            thumb_url = icon_url + color + "_" + str(svt["classId"]) + ".png"
            if svt["collectionNo"] == 0:
                caution = "(ノンプレイヤブル)"
            else:
                caution = ""
            discord.post(username="FGO アップデート",
                         avatar_url=avatar_url,
                         embeds=[{
                                  "title": "サーヴァント新規追加" + caution,
                                  "thumbnail": {
                                                "url": thumb_url
                                                },
                                  "description": desp,
                                  "color": 5620992}])
        except Exception as e:
            logger.excption(e)
            continue


# def make_svtSkill(svt, mstSvtSkill):
#     """
#     サーヴァントのスキルを作成(強化用)
#     """
#     # 指定のスキルを持っているサーヴァントを逆引き
#     desp = "**保有スキル:**\n"
#     try:
#         # 敵データなどで存在するときにコケるので try except
#         skill1_id = [s["skillId"] for s in mstSvtSkill if s["svtId"] == svt["id"] and s["num"] == 1][0]
#         skill1_ct = [s["chargeTurn"] for s in mstSkillLv if s["skillId"] == skill1_id and s["lv"] == 1][0]

#         # 保有スキルを出力
#         desp += "__スキル1__ チャージタイム||" + str(skill1_ct) + "\n"
#         desp += [k["name"] for k in mstSkill
#                 if k["id"] == skill1_id][0] + "\n"
#         desp += [i["detail"] for i in mstSkillDetail if i["id"] == skill1_id][0].replace("[{0}]", r"\[Lv\]") + "||"
#         desp += "\n\n"
#     except Exception as e:
#         pass

#     desp += "\n\n"

#     return desp


def check_np(updatefiles, cid="HEAD"):
    """
    宝具強化をチェックする
    """
    if mstTreasureDevice_file not in updatefiles:
        return
    # 集合演算で新idだけ抽出
    mstSvt_list = [q for q in mstSvt if (q["type"] == 1 or q["type"] == 2) and q["id"] and q["collectionNo"] != 0]
    mstSvtNp = json.loads(repo.git.show(cid + ":" + mstSvtTreasureDevice_file))
    svtNp = [n["treasureDeviceId"] for n in mstSvtNp if n["priority"] > 101]

    mstNp = json.loads(repo.git.show(cid + ":" + mstTreasureDevice_file))
    np = set([s["id"] for s in mstNp if s["id"] in svtNp])
    mstNp_prev = json.loads(repo.git.show(cid + "^:" + mstTreasureDevice_file))
    np_prev = set([s["id"] for s in mstNp_prev if s["id"] in svtNp])
    npIds = list(np - np_prev)
    logger.debug(npIds)
    # # fields作成
    mstNpDetail = json.loads(repo.git.show(cid + ":" + mstTreasureDeviceDetail_file))

    fields = []
    for npId in npIds:
        svtId = [s["svtId"] for s in mstSvtNp if s["treasureDeviceId"] == npId][0]
        logger.debug(svtId)
        svt = [s for s in mstSvt_list if s["id"] == svtId][0]
        logger.debug(svt)
        name = "No." + str(svt["collectionNo"])
        name += ' ' + cost2rarity[svt["cost"]] + ' ' + id2class[svt["classId"]] + ' ' + svt["name"]

        logger.debug(name)

        # 宝具を出力
        value = "[" + [n["name"] + "(" + n["ruby"] + ")" for n in mstNp
                       if n["id"] == npId][0] + "]"
    #     skillNum = [s["skillNum"] for s in mstSvtSkill if s["skillId"] == svtSkill][0]
        value += "(" + "https://apps.atlasacademy.io/db/#/JP/servant/" + str(svt["collectionNo"]) + "/noble-phantasms" + ")\n"
    #     value += "チャージタイム" + str(skill_ct) + "\n"
        value += [n["detail"] for n in mstNpDetail if n["id"] == npId][0].replace("[{0}]", r"\[Lv\]").replace("[g][o]▲[/o][/g]", ":small_red_triangle:")
        field = {"name": name, "value": value}
        fields.append(field)
    if len(fields) != 0:
        discord.post(username="FGO アップデート",
                     avatar_url=avatar_url,
                     embeds=[{
                                "title": "サーヴァント宝具強化",
                                "fields": fields,
                                "color": 5620992}])


def check_skill(updatefiles, cid="HEAD"):
    """
    スキル強化をチェックする
    """
    if mstSkill_file not in updatefiles:
        return
    # 集合演算で新idだけ抽出
    mstSvt_list = [q for q in mstSvt if (q["type"] == 1 or q["type"] == 2) and q["id"] and q["collectionNo"] != 0]
    mstSvtId_list = [q["id"] for q in mstSvt if (q["type"] == 1 or q["type"] == 2) and q["id"] and q["collectionNo"] != 0]
    mstSvtSkill = json.loads(repo.git.show(cid + ":" + mstSvtSkill_file))
    svtSkill = set([s["skillId"] for s in mstSvtSkill if s["svtId"] in mstSvtId_list and s["priority"] > 1])
    mstSvtSkill_prev = json.loads(repo.git.show(cid + "^:" + mstSvtSkill_file))
    svtSkill_prev = set([s["skillId"] for s in mstSvtSkill_prev if s["svtId"] in mstSvtId_list and s["priority"] > 1])
    svtSkillIds = list(svtSkill - svtSkill_prev)
    logger.debug(svtSkillIds)
    # fields作成
    fields = []
    for svtSkill in svtSkillIds:
        skill_ct = [s["chargeTurn"] for s in mstSkillLv if s["skillId"] == svtSkill and s["lv"] == 1][0]
        # skillId から servert id
        svtId = [s["svtId"] for s in mstSvtSkill if s["skillId"] == svtSkill][0]
        logger.debug(svtId)
        svt = [s for s in mstSvt_list if s["id"] == svtId][0]
        logger.debug(svt)
        name = "No." + str(svt["collectionNo"])
        name += ' ' + cost2rarity[svt["cost"]] + ' ' + id2class[svt["classId"]] + ' ' + svt["name"]

        logger.debug([s["name"] for s in mstSkill if s["id"] == svtSkill][0])

        # 保有スキルを出力
        value = "[" + [k["name"] for k in mstSkill
                       if k["id"] == svtSkill][0] + "]"
        skillNum = [s["skillNum"] for s in mstSvtSkill if s["skillId"] == svtSkill][0]
        value += "(" + "https://apps.atlasacademy.io/db/#/JP/servant/" + str(svt["collectionNo"]) + "/skill-" + str(skillNum) + ") "
        value += "チャージタイム" + str(skill_ct) + "\n"
        value += [i["detail"] for i in mstSkillDetail if i["id"] == svtSkill][0].replace("[{0}]", r"\[Lv\]").replace("[g][o]▲[/o][/g]", ":small_red_triangle:")
        field = {"name": name, "value": value}
        fields.append(field)
    if len(fields) != 0:
        discord.post(username="FGO アップデート",
                     avatar_url=avatar_url,
                     embeds=[{
                                "title": "サーヴァントスキル強化",
                                "fields": fields,
                                "color": 5620992}])


def output_quest(q_list, title):
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


def check_quests(updatefiles, cid="HEAD"):
    """
    クエストをチェックする
    """
    if mstQuest_file not in updatefiles:
        return
    # 集合演算で新idだけ抽出
    mstQuest = json.loads(repo.git.show(cid + ":" + mstQuest_file))
    quest = set([s["id"] for s in mstQuest])
    mstQuest_prev = json.loads(repo.git.show(cid + "^:" + mstQuest_file))
    quest_prev = set([s["id"] for s in mstQuest_prev])
    questIds = list(quest - quest_prev)
    logger.debug(questIds)

    mstQuest_list = [q for q in mstQuest if q["id"] in questIds]
    mstQuest_list = sorted(mstQuest_list, key=lambda x: x['openedAt'])

    mstQuestInfo_list = json.loads(repo.git.show(cid + ":" + mstQuestInfo_file))
    mstQuestPhase_list = json.loads(repo.git.show(cid + ":" + mstQuestPhase_file))
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
            q_list.append([quest["id"], quest["name"], 'Lv' + quest["recommendLv"], 'AP' + str(quest["actConsume"]), list2class(enemy), quest["openedAt"], quest["closedAt"]])
            continue
        for q in mstQuestInfo_list:
            if q["questId"] == quest["id"]:
                enemy = questId2classIds[quest["id"]]
                if quest["id"] > 94000000:
                    q_list.append([quest["id"], quest["name"], 'Lv' + quest["recommendLv"], 'AP' + str(quest["actConsume"]), list2class(enemy), quest["openedAt"], quest["closedAt"]])
                else:
                    fq_list.append([quest["id"], quest["name"], 'Lv' + quest["recommendLv"], 'AP' + str(quest["actConsume"]), list2class(enemy), quest["openedAt"], quest["closedAt"]])
                break

    logger.debug(q_list)
    logger.debug(fq_list)
    output_quest(q_list, "イベントクエスト")
    output_quest(fq_list, "恒常フリークエスト")


def check_mastermissions(mstEventMission_list):
    """
    マスターミッションをチェックする
    """
    if len(mstEventMission_list) != 0:
        discord.post(username="FGO アップデート",
                     avatar_url=avatar_url,
                     embeds=[{"title": "マスターミッション(ウィークリー)更新",
                              "thumbnail": {
                                            "url": "https://assets.atlasacademy.io/GameData/JP/Items/16.png"
                                            },
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
                                "thumbnail": {
                                              "url": "https://assets.atlasacademy.io/GameData/JP/Items/7.png"
                                              },
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


def check_missions(updatefiles, cid="HEAD"):
    """
    ミッションをチェックする
    """
    if mstEventMission_file not in updatefiles:
        return
    # 集合演算で新idだけ抽出
    mstEventMission = json.loads(repo.git.show(cid + ":" + mstEventMission_file))
    event = set([s["id"] for s in mstEventMission])
    mstEventMission_prev = json.loads(repo.git.show(cid + "^:" + mstEventMission_file))
    event_prev = set([s["id"] for s in mstEventMission_prev])
    eventMissiontIds = list(event - event_prev)
    logger.debug(eventMissiontIds)

    mstEventMission_list = [m for m in mstEventMission
                            if m["type"] == 2
                            and m["id"] in eventMissiontIds]
    mstEventMission_list = sorted(mstEventMission_list, key=lambda x: x['closedAt'])
    mstEventMissionLimited_list = [m for m in mstEventMission
                                   if m["type"] == 6
                                   and m["id"] in eventMissiontIds]
    mstEventMissionLimited_list = sorted(mstEventMissionLimited_list, key=lambda x: x['closedAt'])
    mstEventMissionDaily_list = [m for m in mstEventMission
                                 if m["type"] == 3
                                 and m["id"] in eventMissiontIds]
    mstEventMissionDaily_list = sorted(mstEventMissionDaily_list, key=lambda x: x['closedAt'])

    check_mastermissions(mstEventMission_list)
    check_eventmissions(mstEventMissionLimited_list)
    check_dailymissions(mstEventMissionDaily_list)


def check_event(updatefiles, cid="HEAD"):
    """
    イベント・キャンペーンをチェックする
    終了日時はそれぞれ異なるので煩雑になるため表記しないこととする
    """
    if mstEvent_file not in updatefiles:
        return
    # 集合演算で新idだけ抽出
    mstEvent = json.loads(repo.git.show(cid + ":" + mstEvent_file))
    event = set([s["id"] for s in mstEvent])
    mstEvent_prev = json.loads(repo.git.show(cid + "^:" + mstEvent_file))
    event_prev = set([s["id"] for s in mstEvent_prev])
    eventIds = list(event - event_prev)
    logger.debug(eventIds)

    mstEvent_list = [m for m in mstEvent
                     if m["id"] in eventIds]
    fieleds = []

    if len(mstEvent_list) == 0:
        return

    for event in mstEvent_list:
        logger.debug(event["type"])
        if event["type"] == 12:
            title = "イベント・クエスト"
        else:
            title = "キャンペーン"
        fieled1 = {
                   "name": "日時",
                   "value": '```開始 | ' + str(datetime.fromtimestamp(event["startedAt"])) + '\n終了 | ' + str(datetime.fromtimestamp(event["endedAt"])) + '```'
                   }
        fieleds.append(fieled1)
        fieled2 = {
                   "name": title,
                   "value": event["detail"]
                   }
        fieleds.append(fieled2)

    discord.post(username="FGO アップデート",
                 avatar_url=avatar_url,
                 embeds=[{
                          "title": "イベント・キャンペーン更新",
                          "fields": fieleds,
                          "color": 5620992}])


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
        # price = str(item["prices"][0])
        # limitNum = str(item["limitNum"]) if item["limitNum"] != 0 else "∞"
        if i == 0:
            itemdate = '```開始 | ' + str(openedAt) + '\n終了 | ' + str(closedAt) + '```'
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
            itemdate = '```開始 | ' + str(openedAt) + '\n終了 | ' + str(closedAt) + '```'
            items = []
            # items.append(item["name"] + " @" + price + " x" + limitNum)
            items.append(item)
            prev_openedAt = openedAt
            prev_closedAt = closedAt
    if len(items) > 0:
        items = sorted(sorted(items, key=lambda x: x["id"]), key=lambda x: x["itemIds"][0], reverse=True)
        date_item = {"date": itemdate, "items": items}
        date_items.append(date_item)
    # ソート
    # filedを作成
    fields = []
    for date_item in date_items:
        logger.debug(date_item)
        field = [{"name": "日時",
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
                f["value"] = "- " + item["name"] + " @" + str(item["prices"][0]) + " x" + (str(item["limitNum"]) if item["limitNum"] != 0 else "∞")
                prev_itemId = itemId
            elif prev_itemId == itemId:
                f["value"] += "\n- " + item["name"] + " @" + str(item["prices"][0]) + " x" + (str(item["limitNum"]) if item["limitNum"] != 0 else "∞")
            else:
                field.append(f)
                if itemId in [0, 18]:
                    f = {"name": "アイテム"}
                else:
                    f = {"name": "{}で交換可能なアイテム".format(id2itemName[itemId])}
                f["value"] = "- " + item["name"] + " @" + str(item["prices"][0]) + " x" + (str(item["limitNum"]) if item["limitNum"] != 0 else "∞")
                prev_itemId = itemId
        if len(f) > 0:
            field.append(f)
        fields += field
    logger.debug(fields)

    if len(fields) != 0:
        if shopname == "マナプリズム交換":
            discord.post(username="FGO アップデート",
                         avatar_url=avatar_url,
                         embeds=[{
                                  "title": shopname + "更新",
                                  "thumbnail": {
                                                "url": "https://assets.atlasacademy.io/GameData/JP/Items/7.png"
                                                },
                                  "fields": fields,
                                  "color": 5620992}])
        elif shopname == "レアプリズム交換":
            discord.post(username="FGO アップデート",
                         avatar_url=avatar_url,
                         embeds=[{
                                  "title": shopname + "更新",
                                  "thumbnail": {
                                                "url": "https://assets.atlasacademy.io/GameData/JP/Items/18.png"
                                                },
                                  "fields": fields,
                                  "color": 5620992}])
        else:
            discord.post(username="FGO アップデート",
                         avatar_url=avatar_url,
                         embeds=[{
                                  "title": shopname + "更新",
                                  "fields": fields,
                                  "color": 5620992}])


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
    mstShop = json.loads(repo.git.show(cid + ":" + mstShop_file))
    shop = set([s["id"] for s in mstShop])
    mstShop_prev = json.loads(repo.git.show(cid + "^:" + mstShop_file))
    shop_prev = set([s["id"] for s in mstShop_prev])
    shopIds = list(shop - shop_prev)
    logger.debug(shopIds)

    mstItem = json.loads(repo.git.show(cid + ":" + mstItem_file))
    global id2itemName
    id2itemName = {item["id"]: item["name"] for item in mstItem}
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
    # if mstSvtFilter_file not in updatefiles:
    #     return
    # 集合演算で新idだけ抽出
    mstSvtFilter = json.loads(repo.git.show(cid + ":" + mstSvtFilter_file))
    SvtFilter = set([s["id"] for s in mstSvtFilter])
    mstSvtFilter_prev = json.loads(repo.git.show(cid + "^:" + mstSvtFilter_file))
    SvtFilter_prev = set([s["id"] for s in mstSvtFilter_prev])
    SvtFilterIds = list(SvtFilter - SvtFilter_prev)
    logger.debug(SvtFilterIds)

    mstSvt_list = [q for q in mstSvt if (q["type"] == 1 or q["type"] == 2) and q["collectionNo"] not in mstSvt and q["collectionNo"] != 0]
    mstSvtFilter_list = [m for m in mstSvtFilter
                         if m["id"] in SvtFilterIds]
    logger.debug("mstSvtFilter_list: %s", mstSvtFilter_list)
    mstSvtF_dic = {m["id"]: {"name": m["name"], "cost": m["cost"], "classId": m["classId"]} for m in mstSvt_list}
    logger.debug("mstSvtFilter_list: %s", mstSvtFilter_list)
    for svtFilter in mstSvtFilter_list:
        svts = {}
        for svtId in svtFilter["svtIds"]:
            if mstSvtF_dic[svtId]["classId"] not in svts.keys():
                svts[mstSvtF_dic[svtId]["classId"]] = [{"name": mstSvtF_dic[svtId]["name"],
                                                       "cost": mstSvtF_dic[svtId]["cost"]}]
            else:
                svts[mstSvtF_dic[svtId]["classId"]].append({"name": mstSvtF_dic[svtId]["name"],
                                                            "cost": mstSvtF_dic[svtId]["cost"]})
        svts = sorted(svts.items())
        logger.debug(svts)
        # filelds を作成
        fields = []
        for svt in svts:
            out = sorted(svt[1], key=lambda x: x['cost'], reverse=True)
            fields.append({"name": id2class[svt[0]],
                           "value": '\n'.join(['- ' + cost2rarity[m["cost"]] + " " + m["name"] for m in out])})
        discord.post(username="FGO アップデート",
                     avatar_url=avatar_url,
                     embeds=[{
                                "title": svtFilter["name"] + "フィルター更新",
                                "fields": fields,
                                "color": 5620992}])


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


def check_mstEquip(updatefiles, cid="HEAD"):
    """
    マスター装備の更新チェック
    """
    if mstEquip_file not in updatefiles:
        return
    # 集合演算で新idだけ抽出
    mstEquip = json.loads(repo.git.show(cid + ":" + mstEquip_file))
    Equip = set([s["id"] for s in mstEquip])
    mstEquip_prev = json.loads(repo.git.show(cid + "^:" + mstEquip_file))
    Equip_prev = set([s["id"] for s in mstEquip_prev])
    equipIds = list(Equip - Equip_prev)
    logger.debug(equipIds)

    mstEquipExp = json.loads(repo.git.show(cid + ":" + mstEquipExp_file))
    mstEquipSkill = json.loads(repo.git.show(cid + ":" + mstEquipSkill_file))

    mstEquip_list = [m for m in mstEquip
                     if m["id"] in equipIds]
    logger.debug("mstEquip_list: %s", mstEquip_list)
    for equip in mstEquip_list:
        skill1_id = [s["skillId"] for s in mstEquipSkill if s["equipId"] == equip["id"] and s["num"] == 1][0]
        skill2_id = [s["skillId"] for s in mstEquipSkill if s["equipId"] == equip["id"] and s["num"] == 2][0]
        skill3_id = [s["skillId"] for s in mstEquipSkill if s["equipId"] == equip["id"] and s["num"] == 3][0]
        skill1_ct = [s["chargeTurn"] for s in mstSkillLv if s["skillId"] == skill1_id and s["lv"] == 1][0]
        skill2_ct = [s["chargeTurn"] for s in mstSkillLv if s["skillId"] == skill2_id and s["lv"] == 1][0]
        skill3_ct = [s["chargeTurn"] for s in mstSkillLv if s["skillId"] == skill3_id and s["lv"] == 1][0]
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
def main(args):
    if args.cid != "HEAD" or check_update():
        updatefiles = repo.git.diff(args.cid + '^..' + args.cid, name_only=True).split('\n')
        if mstSvtFilter_file in updatefiles or mstSvt_file in updatefiles:
            global mstSvt
            global id2class
            mstSvt = json.loads(repo.git.show(args.cid + ":" + mstSvt_file))
            mstClass = json.loads(repo.git.show(args.cid + ":" + mstClass_file))
            id2class = {c["id"]: c["name"] for c in mstClass}
        if mstEquip_file in updatefiles or mstSvt_file in updatefiles:
            # 複数個所で使用するファイルを読んでおく
            global mstSkill
            global mstSkillDetail
            global mstSkillLv
            global mstFunc
            mstSkill = json.loads(repo.git.show(args.cid + ":" + mstSkill_file))
            mstSkillDetail = json.loads(repo.git.show(args.cid + ":" + mstSkillDetail_file))
            mstSkillLv = json.loads(repo.git.show(args.cid + ":" + mstSkillLv_file))
            mstFunc = json.loads(repo.git.show(args.cid + ":" + mstFunc_file))
        try:
            check_datavar(updatefiles, cid=args.cid)
        except Exception as e:
            logger.exception(e)
            discord_error.post(username="FGO アップデート",
                               avatar_url=avatar_url,
                               embeds=[{
                                "title": "check_datavar Error",
                                "description": e,
                                "color": 15158332}])
        try:
            check_gacha(updatefiles, cid=args.cid)
        except Exception as e:
            logger.exception(e)
            discord_error.post(username="FGO アップデート",
                               avatar_url=avatar_url,
                               embeds=[{
                                "title": "check_gacha Error",
                                "description": str(e),
                                "color": 15158332}])
        try:
            check_svt(updatefiles, cid=args.cid)
        except Exception as e:
            logger.exception(e)
            discord_error.post(username="FGO アップデート",
                               avatar_url=avatar_url,
                               embeds=[{
                                "title": "check_svt Error",
                                "description": str(e),
                                "color": 15158332}])
        try:
            check_np(updatefiles, cid=args.cid)
        except Exception as e:
            logger.exception(e)
            discord_error.post(username="FGO アップデート",
                               avatar_url=avatar_url,
                               embeds=[{
                                "title": "check_np Error",
                                "description": str(e),
                                "color": 15158332}])
        try:
            check_skill(updatefiles, cid=args.cid)
        except Exception as e:
            logger.exception(e)
            discord_error.post(username="FGO アップデート",
                               avatar_url=avatar_url,
                               embeds=[{
                                "title": "check_skill Error",
                                "description": str(e),
                                "color": 15158332}])
        try:
            check_quests(updatefiles, cid=args.cid)
        except Exception as e:
            logger.exception(e)
            discord_error.post(username="FGO アップデート",
                               avatar_url=avatar_url,
                               embeds=[{
                                "title": "check_quests Error",
                                "description": str(e),
                                "color": 15158332}])
        try:
            check_missions(updatefiles, cid=args.cid)
        except Exception as e:
            logger.exception(e)
            discord_error.post(username="FGO アップデート",
                               avatar_url=avatar_url,
                               embeds=[{
                                "title": "check_missions Error",
                                "description": e,
                                "color": 15158332}])
        try:
            check_event(updatefiles, cid=args.cid)
        except Exception as e:
            logger.exception(e)
            discord_error.post(username="FGO アップデート",
                               avatar_url=avatar_url,
                               embeds=[{
                                "title": "check_event Error",
                                "description": e,
                                "color": 15158332}])
        try:
            check_shop(updatefiles, cid=args.cid)
        except Exception as e:
            logger.exception(e)
            discord_error.post(username="FGO アップデート",
                               avatar_url=avatar_url,
                               embeds=[{
                                "title": "check_shop Error",
                                "description": e,
                                "color": 15158332}])
        try:
            check_svtfilter(updatefiles, cid=args.cid)
        except Exception as e:
            logger.exception(e)
            discord_error.post(username="FGO アップデート",
                               avatar_url=avatar_url,
                               embeds=[{
                                "title": "check_svtfilter Error",
                                "description": e,
                                "color": 15158332}])
        try:
            check_mstEquip(updatefiles, cid=args.cid)
        except Exception as e:
            logger.exception(e)
            discord_error.post(username="FGO アップデート",
                               avatar_url=avatar_url,
                               embeds=[{
                                "title": "check_mstEquip Error",
                                "description": e,
                                "color": 15158332}])


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
        format='%(name)s <%(filename)s-L%(lineno)s> [%(levelname)s] %(message)s',
    )
    logger.setLevel(args.loglevel.upper())

    main(args)
