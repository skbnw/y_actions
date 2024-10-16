#!/usr/bin/env python
# coding: utf-8

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from datetime import datetime
import urllib3
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# URLのリストを作成
url_list = [
    {"ctgry": "top-picks", "url": "https://news.yahoo.co.jp/topics/top-picks"}, 
    {"ctgry": "domestic", "url": "https://news.yahoo.co.jp/topics/domestic"},
    {"ctgry": "world", "url": "https://news.yahoo.co.jp/topics/world"},
    {"ctgry": "business", "url": "https://news.yahoo.co.jp/topics/business"},
    {"ctgry": "entertainment", "url": "https://news.yahoo.co.jp/topics/entertainment"},
    {"ctgry": "sports", "url": "https://news.yahoo.co.jp/topics/sports"},
    {"ctgry": "it", "url": "https://news.yahoo.co.jp/topics/it"},
    {"ctgry": "science", "url": "https://news.yahoo.co.jp/topics/science"},
    {"ctgry": "local", "url": "https://news.yahoo.co.jp/topics/local"}
]

interval = 3  # インターバル（秒）

# 現在の日付を取得
now = datetime.now()
date_string_folder = now.strftime("%Y%m")  # YYYYMM
date_string_file = now.strftime("%Y%m%d_%H%M")  # YYYYMMDD_hhmm

# フォルダを作成
output_folder = f"html-pickup_{date_string_folder}"
os.makedirs(output_folder, exist_ok=True)

for url_info in url_list:
    ctgry = url_info["ctgry"]
    base_url = url_info["url"]

    start_page = 1
    end_page = 100
    page = start_page

    # データを格納するためのリストを作成
    data = []

    while page <= end_page:
        url = f"{base_url}?page={page}"

        try:
            # HTTP GETリクエストを送信してHTMLを取得（SSL証明書検証エラーを無効化）
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, verify=False)
            response.raise_for_status()
            html = response.text
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {url}: {e}")
            break

        # BeautifulSoupを使用してHTMLをパース
        soup = BeautifulSoup(html, "html.parser")

        # <li class="newsFeed_item">の中の<a>タグを取得
        items = soup.find_all("li", class_="newsFeed_item")

        # 各要素から必要な情報を取得し、データをリストに追加
        for item in items:
            link_tag = item.find("a", class_="sc-1gg21n8-0 cDTGMJ")
            link_short = link_tag["href"] if link_tag and link_tag.get("href") else None

            if not link_short:
                print(f"Error: No link found for item in category {ctgry}")
                continue

            # itemのリンク先にアクセスして情報を取得
            try:
                response_item = requests.get(link_short, headers=headers, verify=False)
                response_item.raise_for_status()
                soup_item = BeautifulSoup(response_item.text, "html.parser")

                media_element = soup_item.select_one("article div a span span")
                media_jp = media_element.text if media_element else "Media info not found"

                url_detail_element = soup_item.select_one("article div div p a")
                link_articles = url_detail_element["href"] if url_detail_element else ""

                link_articles = re.sub(r"/images.*", "", link_articles)

                title_long_element = soup_item.select_one("a > p")
                title_articles = title_long_element.text if title_long_element else ""

                title_element = item.find("div", class_="sc-3ls169-0 dHAJpi")
                title_pickup = title_element.text.strip() if title_element else ""

                date_element = item.find("time")
                date_original = date_element.text.strip() if date_element else ""

                # データに追加
                data.append([ctgry, media_jp, title_pickup, title_articles, link_short, link_articles, date_original])
            except requests.exceptions.RequestException as e:
                print(f"Error fetching item link {link_short}: {e}")
                continue

        # インターバルを待つ
        time.sleep(interval)

        # 作業進捗状況をプリント
        print(f"Scraping page {page} of category {ctgry}")

        # 次のページへ
        page += 1

        # データがなくなった場合にループを終了
        if not items:
            break

    # データをDataFrameに変換
    df = pd.DataFrame(data, columns=["ctgry", "media_jp", "title_pickup", "title_articles", "link_pickup", "link_articles", "date_original"])

    # DataFrameをCSVファイルとして書き出し（エンコーディング：CP932）
    filename = f"html_{ctgry}_{date_string_file}.csv"
    file_path = os.path.join(output_folder, filename)
    print(f"Saving to file: {file_path}")
    df.to_csv(file_path, index=False, encoding="CP932", errors="ignore")

    # 作業完了メッセージをプリント
    print(f"Scraping complete for {ctgry}. File saved: {file_path}")

print("Scraping finished for all categories")
