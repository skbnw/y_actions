import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import datetime
import re
import urllib3
import os

# SSL証明書の検証を無効化
urllib3.disable_warnings()

# URLのリストを含むCSVファイルを読み込む
url_data = pd.read_csv("url/media_url_group.csv")

interval = 3  # インターバル（秒）

# 現在の日付と時刻を取得
now = datetime.now()

# データを格納するためのリストを作成
data = []

for index, row in url_data.iterrows():
    group = row["group"]
    media_jp = row["media_jp"]
    media_en = row["media_en"]
    url = row["url"]
    
    # group指定 "a"グループをスクレイプ　, "b", "c", "s"
    if group not in ["f"]:
        continue

    # スクレイピングの処理を実行
    start_page = 1
    end_page = 100
    page = start_page  # page変数を初期化
    while page <= end_page:
        url_with_page = f"{url}?page={page}"

        # HTTP GETリクエストを送信してHTMLを取得（SSL証明書の検証を無効化）
        response = requests.get(url_with_page, verify=False)
        html = response.text

        # BeautifulSoupを使用してHTMLをパース
        soup = BeautifulSoup(html, "html.parser")

        # <li class="newsFeed_item">要素をすべて取得
        items = soup.find_all("li", class_="newsFeed_item")

        # 各要素から必要な情報を取得し、データをリストに追加
        for item in items:
            link_articles = item.find("a", class_="newsFeed_item_link")["href"]
            title_articles = item.find("div", class_="newsFeed_item_title").text.strip()
            date_original = item.find("time", class_="newsFeed_item_date").text.strip()

            # media_enをデータに追加
            data.append([media_en, media_jp, title_articles, link_articles, date_original])

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
    df = pd.DataFrame(data, columns=["media_en", "media_jp", "title_articles", "link_articles", "date_original"])

    # 保存するディレクトリが存在しない場合は作成する
    folder_name = now.strftime("html_mediaALL_f_%Y%m_%W")
    os.makedirs(folder_name, exist_ok=True)

    # ファイル名を設定
    filename = f"{folder_name}/html_{media_en}_{now.strftime('%Y%m%d_%H%M%S')}.csv"

    # DataFrameをCSVファイルとして書き出し（エンコーディング：CP932）
    df.to_csv(filename, index=False, encoding="CP932", errors="ignore")

    # 作業完了メッセージをプリント
    print(f"Scraping complete for {media_jp}. File saved: {filename}")

    # スクレイピングが完了したことを示すメッセージを表示
    print("Scraping finished")

    # データをクリア
    data = []
