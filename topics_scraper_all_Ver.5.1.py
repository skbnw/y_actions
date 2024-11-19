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
import sys
from typing import Dict, List, Optional

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 期待されるクラス名を定義
EXPECTED_CLASSES = {
    "news_item": "newsFeed_item",  # ニュースアイテムのクラス
    "title_container": "sc-3ls169-0",  # タイトルコンテナのクラス
    "time": "sc-ioshdi-1",  # 時間表示のクラス
    "time_container": "sc-ioshdi-0"  # 時間コンテナのクラス
}

class HTMLStructureError(Exception):
    """HTML構造の変更を検出した際に発生する例外"""
    pass

def validate_class_names(soup: BeautifulSoup, item_selector: str) -> None:
    """
    HTML構造のクラス名を検証する
    
    Args:
        soup: BeautifulSoupオブジェクト
        item_selector: 検証するアイテムのセレクタ
        
    Raises:
        HTMLStructureError: クラス名が期待と異なる場合
    """
    # ニュースアイテムの存在確認
    items = soup.find_all("li", class_=EXPECTED_CLASSES["news_item"])
    if not items:
        raise HTMLStructureError(f"Expected class '{EXPECTED_CLASSES['news_item']}' for news items not found")
    
    for item in items[:1]:  # 最初のアイテムのみチェック
        # タイトルコンテナの確認
        title_container = item.find("div", class_=re.compile(EXPECTED_CLASSES["title_container"]))
        if not title_container:
            raise HTMLStructureError(f"Expected class containing '{EXPECTED_CLASSES['title_container']}' for title container not found")
        
        # 時間表示の確認
        time_element = item.find("time", class_=re.compile(EXPECTED_CLASSES["time"]))
        if not time_element:
            raise HTMLStructureError(f"Expected class containing '{EXPECTED_CLASSES['time']}' for time element not found")
        
        # 時間コンテナの確認
        time_container = item.find("div", class_=re.compile(EXPECTED_CLASSES["time_container"]))
        if not time_container:
            raise HTMLStructureError(f"Expected class containing '{EXPECTED_CLASSES['time_container']}' for time container not found")

def scrape_news_item(item: BeautifulSoup, headers: Dict) -> Optional[List]:
    """個別のニュースアイテムをスクレイピング"""
    try:
        # リンクの取得
        link_tag = item.find("a")
        if not link_tag or not link_tag.get("href"):
            print("Error: No link found for item")
            return None
            
        link_short = link_tag["href"]
        
        # 詳細ページの取得
        response_item = requests.get(link_short, headers=headers, verify=False)
        response_item.raise_for_status()
        soup_item = BeautifulSoup(response_item.text, "html.parser")
        
        # メディア情報の取得
        media_element = soup_item.select_one("article div a span")
        media_jp = media_element.text if media_element else "Media info not found"
        
        # 詳細リンクの取得
        url_detail_element = soup_item.select_one("article div div p a")
        link_articles = url_detail_element["href"] if url_detail_element else ""
        link_articles = re.sub(r"/images.*", "", link_articles)
        
        # タイトルの取得
        title_long_element = soup_item.select_one("article p")
        title_articles = title_long_element.text if title_long_element else ""
        
        # ピックアップタイトルの取得
        title_element = item.find("div", class_=re.compile(EXPECTED_CLASSES["title_container"]))
        title_pickup = title_element.text.strip() if title_element else ""
        
        # 日付の取得
        date_element = item.find("time", class_=re.compile(EXPECTED_CLASSES["time"]))
        date_original = date_element.text.strip() if date_element else ""
        
        return [media_jp, title_pickup, title_articles, link_short, link_articles, date_original]
    
    except Exception as e:
        print(f"Error processing news item: {str(e)}")
        return None

def main():
    # URLのリスト
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
    date_string_folder = now.strftime("%Y%m")
    date_string_file = now.strftime("%Y%m%d_%H%M")
    
    # 出力フォルダの作成
    output_folder = f"html-pickup_{date_string_folder}"
    os.makedirs(output_folder, exist_ok=True)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    for url_info in url_list:
        ctgry = url_info["ctgry"]
        base_url = url_info["url"]
        data = []
        page = 1

        while page <= 100:
            url = f"{base_url}?page={page}"
            try:
                response = requests.get(url, headers=headers, verify=False)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                
                # HTML構造の検証
                try:
                    validate_class_names(soup, "li.newsFeed_item")
                except HTMLStructureError as e:
                    print(f"\n警告: HTMLの構造が変更されました！")
                    print(f"エラー内容: {str(e)}")
                    print("スクレイピングを中止します。HTML構造の確認が必要です。")
                    sys.exit(1)
                
                items = soup.find_all("li", class_=EXPECTED_CLASSES["news_item"])
                if not items:
                    break

                for item in items:
                    result = scrape_news_item(item, headers)
                    if result:
                        data.append([ctgry] + result)

                print(f"Scraping page {page} of category {ctgry}")
                page += 1
                time.sleep(interval)

            except requests.exceptions.RequestException as e:
                print(f"Error fetching {url}: {e}")
                break

        # データをDataFrameに変換
        if data:
            df = pd.DataFrame(data, columns=[
                "ctgry", "media_jp", "title_pickup", "title_articles",
                "link_pickup", "link_articles", "date_original"
            ])
            
            # CSVファイルとして保存
            filename = f"html_{ctgry}_{date_string_file}.csv"
            file_path = os.path.join(output_folder, filename)
            print(f"Saving to file: {file_path}")
            df.to_csv(file_path, index=False, encoding="CP932", errors="ignore")
            print(f"Scraping complete for {ctgry}. File saved: {file_path}")

    print("Scraping finished for all categories")

if __name__ == "__main__":
    main()
