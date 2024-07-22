import requests
from bs4 import BeautifulSoup
import pandas as pd
import time as t
from datetime import datetime
import os

# SSL証明書の検証を無効化
requests.packages.urllib3.disable_warnings()

# URLのリストを含むCSVファイルを読み込む
url_data = pd.read_csv("url/media_url_group.csv")

interval = 3  # インターバル（秒）

# 現在の日付と時刻を取得
now = datetime.now()

# 対象グループのリスト
target_groups = ["d", "e", "f"]

for group in target_groups:
    for index, row in url_data.iterrows():
        media_group = row["group"]
        media_jp = row["media_jp"]
        media_en = row["media_en"]
        url = row["url"]

        # 指定グループのみをスクレイプ
        if media_group != group:
            continue

        # データを格納するためのリストを作成
        data = []

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
                try:
                    link_articles = item.find("a", class_="newsFeed_item_link")["href"]
                    title_articles = item.find("div", class_="newsFeed_item_title").text.strip()
                    date_tag = item.find("div", class_="newsFeed_item_sub").find("time")
                    
                    if date_tag:
                        date_original = date_tag.text.strip()
                    else:
                        date_original = "No date found"
                        print(f"Error: No date found for article: {title_articles}")

                    # データに追加
                    data.append([media_en, media_jp, title_articles, link_articles, date_original])
                except AttributeError as e:
                    print(f"Error parsing item: {e}")

            # インターバルを待つ
            t.sleep(interval)

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
        folder_name = now.strftime(f"html_mediaALL_{group}_%Y%m_%W")
        os.makedirs(folder_name, exist_ok=True)

        # ファイル名を設定
        filename = f"{folder_name}/html_{media_en}_{now.strftime('%Y%m%d_%H%M%S')}.csv"

        # DataFrameをCSVファイルとして書き出し（エンコーディング：CP932）
        df.to_csv(filename, index=False, encoding="CP932", errors="ignore")

        # 作業完了メッセージをプリント
        print(f"Scraping complete for {media_jp}. File saved: {filename}")

print("Scraping finished for all groups")
