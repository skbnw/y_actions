import requests
from bs4 import BeautifulSoup
import pandas as pd
import time as t
from datetime import datetime
import os

# SSL証明書の検証を無効化
requests.packages.urllib3.disable_warnings()

# HTML構造の定義
EXPECTED_CLASSES = {
    "news_link": "sc-1gg21n8-0",  # ニュースリンクのクラス
    "title_container": "sc-3ls169-0",  # タイトルコンテナのクラス
    "time": "sc-ioshdi-1",  # 時間表示のクラス
}

class HTMLStructureError(Exception):
    """HTML構造の変更を検出した際に発生する例外"""
    pass

def validate_html_structure(soup):
    """HTML構造を検証する関数"""
    # ニュースリンクの存在確認
    items = soup.find_all("a", class_=re.compile(EXPECTED_CLASSES["news_link"]))
    if not items:
        raise HTMLStructureError(f"Expected class containing '{EXPECTED_CLASSES['news_link']}' for news links not found")
    return items

def scrape_news_item(item):
    """個別のニュースアイテムをスクレイピングする関数"""
    try:
        # タイトルを取得
        title_tag = item.find("div", class_=re.compile(EXPECTED_CLASSES["title_container"]))
        if not title_tag:
            return None, None
        title_articles = title_tag.text.strip()

        # 日付を取得
        date_tag = item.find("time", class_=re.compile(EXPECTED_CLASSES["time"]))
        date_original = date_tag.text.strip() if date_tag else "No date found"

        return title_articles, date_original
    except Exception as e:
        print(f"Error parsing item: {e}")
        return None, None

def main():
    # URLのリストを含むCSVファイルを読み込む
    url_data = pd.read_csv("url/media_url_group.csv")
    interval = 3  # インターバル（秒）
    
    # 現在の日付と時刻を取得
    now = datetime.now()
    
    # 対象グループのリスト
    target_groups = ["d", "e", "f"]

    # ユーザーエージェントの設定
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    for group in target_groups:
        for index, row in url_data.iterrows():
            media_group = row["group"]
            media_jp = row["media_jp"]
            media_en = row["media_en"]
            url = row["url"]
            
            # 指定グループのみをスクレイプ
            if media_group != group:
                continue
                
            # データを格納するためのリスト
            data = []
            
            # スクレイピングの処理を実行
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
                    
                    try:
                        # HTML構造の検証と記事の取得
                        items = validate_html_structure(soup)
                    except HTMLStructureError as e:
                        print(f"\n警告: HTMLの構造が変更されました！")
                        print(f"エラー内容: {str(e)}")
                        print("スクレイピングを中止します。HTML構造の確認が必要です。")
                        return
                    
                    if not items:
                        print(f"No more data for {media_jp}. Switching to next URL.")
                        break
                    
                    # 各記事の情報を取得
                    for item in items:
                        title_articles, date_original = scrape_news_item(item)
                        if title_articles and date_original:
                            data.append([media_en, media_jp, title_articles, date_original])
                    
                    # インターバルを待つ
                    t.sleep(interval)
                    
                    # 作業進捗状況をプリント
                    print(f"Scraped page {page} of {end_page} for {media_jp}")
                    
                    # ページの増加
                    page += 1
                    
                except requests.exceptions.RequestException as e:
                    print(f"Error fetching {url_with_page}: {e}")
                    break
                except Exception as e:
                    print(f"Unexpected error processing {url_with_page}: {e}")
                    continue
            
            if data:
                # 取得した情報をDataFrameに格納
                df = pd.DataFrame(data, columns=["media_en", "media_jp", "title_articles", "date_original"])
                
                # 保存するディレクトリを作成
                folder_name = now.strftime(f"html_mediaALL_{group}_%Y%m_%W")
                os.makedirs(folder_name, exist_ok=True)
                
                # ファイル名を設定
                filename = f"{folder_name}/html_{media_en}_{now.strftime('%Y%m%d_%H%M%S')}.csv"
                
                # DataFrameをCSVファイルとして保存
                df.to_csv(filename, index=False, encoding="CP932", errors="ignore")
                print(f"Scraping complete for {media_jp}. File saved: {filename}")
            else:
                print(f"No data was collected for {media_jp}")

    print("Scraping finished for all groups")

if __name__ == "__main__":
    main()
