import requests
from bs4 import BeautifulSoup
import pandas as pd
import time as t
from datetime import datetime
import os
import re

# SSL証明書の検証を無効化
requests.packages.urllib3.disable_warnings()

# HTML構造の定義（複数クラス候補に対応）
EXPECTED_CLASSES = {
    "news_item": "sc-278a0v-0 iiJVBF",  # 記事コンテナのクラス
    "news_link": r"sc-1gg21n8-0|cDTGMJ",  # ニュースリンクの複数候補
    "title_container": r"sc-3ls169-0|dHAJpi",  # タイトルコンテナの複数候補
    "time": r"sc-ioshdi-1|dRkKNK",  # 時間表示の複数候補
    "source": r"sc-fybyzc-5|SpEDp"  # 媒体名の複数候補
}

# インターバル（秒）
interval = 3

# 現在の日付と時刻を取得
now = datetime.now()

# 対象グループのリスト
target_groups = ["a", "b", "c"]

# ユーザーエージェントの設定
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

class HTMLStructureError(Exception):
    """HTML構造の変更を検出した際に発生する例外"""
    pass

def scrape_news(url_data):
    """ニュースデータをスクレイピングしてCSVに保存"""
    for group in target_groups:
        for index, row in url_data.iterrows():
            media_group = row["group"]
            media_jp = row["media_jp"]
            media_en = row["media_en"]
            url = row["url"]

            # 指定グループのみをスクレイプ
            if media_group != group:
                continue

            # データを格納するリストを作成
            data = []

            # ページ番号を設定
            start_page = 1
            end_page = 100
            page = start_page

            while page <= end_page:
                url_with_page = f"{url}?page={page}"
                try:
                    # HTTP GETリクエストを送信
                    response = requests.get(url_with_page, headers=headers, verify=False)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.text, "html.parser")

                    # 新しいHTML構造に基づいてニュース記事を取得
                    items = soup.find_all("div", class_=EXPECTED_CLASSES["news_item"])

                    if not items:
                        raise HTMLStructureError(f"No articles found for {media_jp} on page {page}")

                    for item in items:
                        try:
                            # ニュースリンクを取得
                            link_tag = item.find("a", class_=re.compile(EXPECTED_CLASSES["news_link"]), href=True)
                            article_link = link_tag["href"] if link_tag else "No link found"

                            # タイトルを取得
                            title_tag = item.find("div", class_=re.compile(EXPECTED_CLASSES["title_container"]))
                            title_articles = title_tag.text.strip() if title_tag else "No title found"

                            # 日付を取得
                            date_tag = item.find("time", class_=re.compile(EXPECTED_CLASSES["time"]))
                            date_original = date_tag.text.strip() if date_tag else "No date found"

                            # ソース（媒体名）を取得
                            source_tag = item.find("span", class_=re.compile(EXPECTED_CLASSES["source"]))
                            source_name = source_tag.text.strip() if source_tag else "No source found"

                            # 必須項目が揃っているか確認
                            if not article_link or not title_articles or not date_original:
                                raise HTMLStructureError(f"Missing required data for an article")

                            # データをリストに追加
                            data.append([media_en, media_jp, title_articles, date_original, source_name, article_link])

                        except Exception as e:
                            raise HTMLStructureError(f"Error parsing item for {media_jp}: {e}")

                    # インターバルを待つ
                    t.sleep(interval)

                    # 作業進捗状況をプリント
                    print(f"Scraped page {page} of {end_page} for {media_jp}")

                    # ページ番号を増加
                    page += 1

                except requests.exceptions.RequestException as e:
                    print(f"Error fetching {url_with_page}: {e}")
                    break
                except HTMLStructureError as e:
                    print(f"Critical error: {e}")
                    raise e  # GitHub Actionsを停止させるため例外を再スロー
                except Exception as e:
                    print(f"Unexpected error processing {url_with_page}: {e}")
                    continue

            # 取得したデータをDataFrameに格納
            if data:
                df = pd.DataFrame(data, columns=["media_en", "media_jp", "title_articles", "date_original", "source_name", "article_link"])

                # 保存ディレクトリを作成
                folder_name = now.strftime(f"html_mediaALL_{group}_%Y%m_%W")
                os.makedirs(folder_name, exist_ok=True)

                # ファイル名を設定
                filename = f"{folder_name}/html_{media_en}_{now.strftime('%Y%m%d_%H%M%S')}.csv"

                # CSVファイルとして保存
                df.to_csv(filename, index=False, encoding="CP932", errors="ignore")
                print(f"Scraping complete for {media_jp}. File saved: {filename}")
            else:
                print(f"No data was collected for {media_jp}")

    print("Scraping finished for all groups")

if __name__ == "__main__":
    # URLのリストを含むCSVファイルを読み込む
    url_data = pd.read_csv("url/media_url_group.csv")
    scrape_news(url_data)
