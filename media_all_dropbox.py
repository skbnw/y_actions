#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import datetime
import re
import urllib3
import os
import dropbox

# SSL証明書の検証を無効化
urllib3.disable_warnings()

# URLのリストを含むCSVファイルを読み込む
url_data = pd.read_csv("url/media_url_all.csv")

interval = 3  # インターバル（秒）

# 現在の日付と時刻を取得
now = datetime.now()

# Dropbox APIのアクセストークン
ACCESS_TOKEN = 'sl.Bhki_MZca4WyQZW4Bd-ycYjc-4KX95Zlb5xpY9fJQaerdbv-x27GqjreeRvy9v5aMIWQ7tRe1StOqhsMVqmb6cLEKyrLGSjjk64vz7qfMfGIdblR8CVtFPVbGAAsqRTXaGzvb2k'

# Dropboxへの接続
dbx = dropbox.Dropbox(ACCESS_TOKEN)

# データを格納するためのリストを作成
data = []

for index, row in url_data.iterrows():
    media_jp = row["media"]
    base_url = row["url"]

    start_page = 1
    end_page = 100
    page = start_page

    while page <= end_page:
        url = f"{base_url}?page={page}"

        # HTTP GETリクエストを送信してHTMLを取得（SSL証明書の検証を無効化）
        response = requests.get(url, verify=False)
        html = response.text

        # BeautifulSoupを使用してHTMLをパース
        soup = BeautifulSoup(html, "html.parser")

        # <li class="newsFeed_item">要素をすべて取得
        items = soup.find_all("li", class_="newsFeed_item")

        # 各要素から必要な情報を取得し、データをリストに追加
        for item in items:
            link_long = item.find("a", class_="newsFeed_item_link")["href"]
            title_long = item.find("div", class_="newsFeed_item_title").text.strip()
            date_original = item.find("time", class_="newsFeed_item_date").text.strip()

            # media_jpをデータに追加
            data.append([media_jp, title_long, link_long, date_original])

        # インターバルを待つ
        time.sleep(interval)

        # 作業進捗状況をプリント
        print(f"Scraped page {page} of {end_page} for {media_jp}")

        # ページの増加
        page += 1

        # データがなくなった場合に次のURLにスイッチ
        if not items:
            print(f"No more data for {media_jp}. Switching to next URL.")
            break

    # 取得した情報をDataFrameに格納
    df = pd.DataFrame(data, columns=["Media_JP", "title_long", "Link_Long", "date_original"])

    # ファイル名を設定
    filename = f"{media_jp}_{now.strftime('%Y%m%d_%H%M%S')}.csv"

    # DataFrameをCSVファイルとして書き出し（エンコーディング：CP932）
    df.to_csv(filename, index=False, encoding="CP932", errors="ignore")

    # Dropboxにアップロード
    with open(filename, 'rb') as file:
        dbx.files_upload(file.read(), f"/output/{filename}")

    # 作業完了メッセージをプリント
    print(f"Scraping complete for {media_jp}. File uploaded to Dropbox: {filename}")

    # データをクリア
    data = []


# In[ ]:




