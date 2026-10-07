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
from urllib.parse import urljoin

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 期待されるクラス名を定義
EXPECTED_CLASSES = {
    "news_link": "sc-1gg21n8-0",  # ニュースリンクのクラス
    "title_container": "sc-3ls169-0",  # タイトルコンテナのクラス
    "time": "sc-ioshdi-1",  # 時間表示のクラス
    "time_container": "sc-ioshdi-0"  # 時間コンテナのクラス
}

class HTMLStructureError(Exception):
    """HTML構造の変更を検出した際に発生する例外"""
    pass

PICKUP_HREF_PATTERN = re.compile(r"^(?:https?://news\.yahoo\.co\.jp)?/pickup/\d+")


def find_news_links(soup: BeautifulSoup) -> List:
    """
    ニュースリンク（ピックアップ記事へのaタグ）を取得する。
    Yahoo!ニュースのクラス名（sc-xxxx）は頻繁に変わるため、
    1. 従来のクラス名
    2. href が /pickup/数字 で、内部に<time>を持つaタグ
    3. href が /pickup/数字 の aタグ（<main>内を優先）
    の順でフォールバックして検出する。
    """
    items = soup.find_all("a", class_=re.compile(EXPECTED_CLASSES["news_link"]))
    if items:
        return items

    pickup_links = soup.find_all("a", href=PICKUP_HREF_PATTERN)
    with_time = [a for a in pickup_links if a.find("time")]
    if with_time:
        return with_time

    main = soup.find("main")
    if main:
        main_links = main.find_all("a", href=PICKUP_HREF_PATTERN)
        if main_links:
            return main_links
    return pickup_links


def extract_title(item: BeautifulSoup) -> str:
    """ピックアップタイトルを取得する（クラス名が変わっていても取得できるようにする）"""
    title_element = item.find("div", class_=re.compile(EXPECTED_CLASSES["title_container"]))
    if title_element:
        return title_element.get_text(strip=True)

    # <time>内の文字列を除外し、最も長いテキストをタイトルとみなす
    candidates = []
    for text in item.find_all(string=True):
        if text.find_parent("time") is not None:
            continue
        stripped = text.strip()
        if stripped:
            candidates.append(stripped)
    return max(candidates, key=len) if candidates else ""


def extract_time(item: BeautifulSoup) -> str:
    """日時表示を取得する（クラス名が変わっていても取得できるようにする）"""
    date_element = item.find("time", class_=re.compile(EXPECTED_CLASSES["time"]))
    if not date_element:
        date_element = item.find("time")
    return date_element.get_text(strip=True) if date_element else ""


def validate_class_names(soup: BeautifulSoup) -> None:
    """
    HTML構造を検証する（ニュースリンクが1件も検出できない場合のみエラー）

    Args:
        soup: BeautifulSoupオブジェクト

    Raises:
        HTMLStructureError: ニュースリンクが検出できない場合
    """
    items = find_news_links(soup)
    if not items:
        raise HTMLStructureError(
            f"News links not found (class '{EXPECTED_CLASSES['news_link']}' / href '/pickup/<id>')"
        )

    # クラス名が変わっている場合は警告のみ出して処理を続行する
    if not soup.find("a", class_=re.compile(EXPECTED_CLASSES["news_link"])):
        print(f"注意: クラス '{EXPECTED_CLASSES['news_link']}' が見つからないため、href パターンで記事リンクを検出しました")

def scrape_news_item(item: BeautifulSoup, headers: Dict) -> Optional[List]:
    """個別のニュースアイテムをスクレイピング"""
    try:
        # リンクの取得（アイテム自体がaタグ）
        link_short = item.get("href")
        if not link_short:
            print("Error: No link found for item")
            return None
        link_short = urljoin("https://news.yahoo.co.jp/", link_short)
            
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
        title_pickup = extract_title(item)
        
        # 日付の取得
        date_original = extract_time(item)
        
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
        seen_links = set()
        page = 1

        while page <= 100:
            url = f"{base_url}?page={page}"
            try:
                response = requests.get(url, headers=headers, verify=False)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                
                # HTML構造の検証（1ページ目でリンクが検出できない場合のみ中止）
                if page == 1:
                    try:
                        validate_class_names(soup)
                    except HTMLStructureError as e:
                        print(f"\n警告: HTMLの構造が変更されました！")
                        print(f"エラー内容: {str(e)}")
                        print("スクレイピングを中止します。HTML構造の確認が必要です。")
                        sys.exit(1)
                
                # 記事リンクの取得（クラス名変更にも対応）
                items = find_news_links(soup)
                if not items:
                    break

                # 重複リンクを除外（同一ページ内・ページ間）
                new_items = []
                for item in items:
                    href = urljoin("https://news.yahoo.co.jp/", item.get("href", ""))
                    if href and href not in seen_links:
                        seen_links.add(href)
                        new_items.append(item)
                if not new_items:
                    break

                for item in new_items:
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
