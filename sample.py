#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import os
import glob
import xml.etree.ElementTree as ET
import csv
import requests
from bs4 import BeautifulSoup
import pandas as pd
import urllib3
import datetime

# SSL証明書検証エラーを無効化
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# データを保存するためのリスト
data = []

# 週の開始日と終了日を計算
today = datetime.date.today()
start_of_week = today - datetime.timedelta(days=today.weekday())
end_of_week = start_of_week + datetime.timedelta(days=6)

# 週の開始日と終了日を表示
print("週の開始日:", start_of_week)
print("週の終了日:", end_of_week)

# XMLファイルのパス
xml_files = glob.glob("top-picks/*.xml")

# 各XMLファイルに対して処理を実行
for xml_file in xml_files:
    # XMLファイルをパース
    tree = ET.parse(xml_file)
    root = tree.getroot()

    # チャンネルの情報を抽出
    channel = root.find("channel")
    channelTitle = channel.find("title").text
    pubDate = channel.find("pubDate").text

    # ニュースアイテムの情報を抽出
    items = root.findall(".//item")

    for item in items:
        itemTitle = item.find("title").text
        itemLink = item.find("link").text
        itemPubDate = item.find("pubDate").text
        itemComments = item.find("comments").text if item.find("comments") is not None else ""

        # itemのlink先にアクセスしてmediaを取得
        response = requests.get(itemLink, verify=False)
        soup = BeautifulSoup(response.text, "html.parser")
        media_element = soup.select_one("span > a > span > span")
        media = media_element.text if media_element is not None else ""

        # itemのlink先にアクセスしてLinkを取得
        link_element = soup.select_one("article div div p a")
        link = link_element.get("href") if link_element is not None else ""

        # データをリストに追加
        data.append({
            "pubDate": pubDate,
            "channelTitle": channelTitle,
            "itemTitle": itemTitle,
            "link": itemLink,
            "itemPubDate": itemPubDate,
            "comments": itemComments,
            "media": media,
            "Link": link
        })

# データフレームを作成
df = pd.DataFrame(data)

# 週の開始日と終了日の範囲でデータをフィルタリング
df["pubDate"] = pd.to_datetime(df["pubDate"])
df = df[(df["pubDate"] >= start_of_week) & (df["pubDate"] <= end_of_week)]

# データフレームをCSVファイルとして保存
csv_file = "top-picks_weekly_{}.csv".format(start_of_week.strftime("%Y%m%d"))
df.to_csv(csv_file, index=False, encoding="CP932")

# 結果を表示
print("CSVファイルが保存されました:", csv_file)

