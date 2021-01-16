# fgo_update

FGOのデータ更新をチェックしてDiscordのwebhookにpostする

Atlas Achademy の fgo-changes から発想を得てます

次の更新がpostされます
- データ更新
- ガチャ更新
- 新規サーヴァント追加
- クエスト更新
  - イベントフリークエスト・高難易度
  - 恒常フリークエスト
- ミッション更新
  - デイリーミッション
  - ウィークリーミッション
  - その他ミッション(イベント内ミッションを除く)
- イベント・キャンペーン更新
- ショップ更新
  - イベント限定ショップ
  - マナプリズム交換
  - レアプリ交換
  - サウンドプレイヤー
- 次回イベントフィルター
- マスター装備

# 実行環境
Pythonが動作する環境

Windows と Linux で動作を確認しています

# インストール
まずは Python をインストールしてください
## 必要なライブラリのインストール
```
$ pip install -r requirements.txt
```
## 設定ファイルのコピー
```
$ cp fgoupdate-dst.ini fgoupdate.ini  
```
## 設定ファイル fgoappupdate.ini の編集
- ```webhook= ```のあとにウェブフックURLを入力してください(更新通知用)
- ```webhook4error= ```のあとにウェブフックURLを入力してください(エラー通知用)
- ```repository = ```のあとにFGOデータのリポジトリ―のURLを入力してください
webhookは画面の「ウェブフックURLをコピー」を押すと取得できます

![image](https://user-images.githubusercontent.com/62515228/104086843-72d7fc80-529e-11eb-85ed-cff1d8241c6a.png)

例:
```
[discord]
webhook = https://discordapp.com/api/webhooks/00000000000000/abcdefghijklmn--ABCDEFGHIJKLMN
webhook4error = https://discordapp.com/api/webhooks/00000000000000/abcdefghijklmn--ABCDEFGHIJKLMN

[fgodata]
repository = https://github.com/*****/*****.git

```
## 実行権の付与(UNIXの場合)
```
$ chmod +x fgoupdate.py
```

# 使用法
下記のコマンド実行でアップデートの有無をチェックします

なお、初回実行時は多数の更新内容がポストされます
```
$ python3 ./fgoupdate.py
```
出力例:

![image](https://user-images.githubusercontent.com/62515228/104119021-3543a400-5370-11eb-96c0-c155cb5bb3e1.png)
![image](https://user-images.githubusercontent.com/62515228/104119035-560bf980-5370-11eb-9e7d-cfc6e52a4494.png)
![image](https://user-images.githubusercontent.com/62515228/104119054-6c19ba00-5370-11eb-8751-49ac11ccdb9f.png)
![image](https://user-images.githubusercontent.com/62515228/104119068-80f64d80-5370-11eb-867a-3d36dd0c58f5.png)
![image](https://user-images.githubusercontent.com/62515228/104120830-2fa08b00-537d-11eb-8b78-7cb721f82d5f.png)

実用的には cron などを利用して定期的に実行することになります

## Unix で cron を使用して5分毎に実行する例
```$ crontab -e```を実行して下記を入力 

```
0,5,10,15,20,25,30,35,40,45,50,55       *       *       *       *       /home/fgophi/bin/fgoupdate.py
```
