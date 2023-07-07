import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from datetime import datetime
import urllib3
import os
import dropbox

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Dropbox APIのアプリキーとアプリシークレットキー
app_key = '86eg2z9yfdea4ki'
app_secret = 'zxdqhotp4dg2bjn'

# アクセスコード（認証コード）を変数として扱う
auth_code = 'TmVaZaXVHl4AAAAAAARvRd6QRjMl-khMweakgAL9o3o'

# OAuth2フローを開始
auth_flow = dropbox.DropboxOAuth2FlowNoRedirect(app_key, app_secret, token_access_type='offline')
authorize_url = auth_flow.start()

# アクセスコードを使用してアクセストークンとリフレッシュトークンを取得
oauth_result = auth_flow.finish(auth_code)
access_token = oauth_result.access_token
refresh_token = oauth_result.refresh_token

# Dropboxへの接続
dbx = dropbox.Dropbox(access_token)

# フォルダ名
folder_name = 'html-scrape'

# フォルダが存在しない場合は作成
def create_folder_if_not_exists(folder_name):
    try:
        dbx.files_create_folder_v2('/' + folder_name)
        print(f"Folder '{folder_name}' created successfully.")
    except dropbox.exceptions.ApiError as e:
        if e.error.is_path() and e.error.get_path().is_conflict():
            print(f"Folder '{folder_name}' already exists.")
        else:
            print(f"Failed to create folder '{folder_name}': {e}")

# フォルダの作成
create_folder_if_not_exists(folder_name)

# URLのリストを含むCSVファイルを読み込む
url_data = pd.read_csv("url/topics_url.csv")

interval = 3  # インターバル（秒）

for index, row in url_data.iterrows():
    ctgry = row["ctgry"]
    base_url = row["url"]

    start_page = 1
    end_page = 100
    page = start_page

    # データを格納するためのリストを作成
    data = []

    while page <= end_page:
        url = f"{base_url}?page={page}"

        # HTTP GETリクエストを送信してHTMLを取得（SSL証明書検証エラーを無効化）
        response = requests.get(url, verify=False)
        html = response.text

        # BeautifulSoupを使用してHTMLをパース
        soup = BeautifulSoup(html, "html.parser")

        # <a class="newsFeed_item_link">要素をすべて取得
        items = soup.find_all("a", class_="newsFeed_item_link")

        # 各要素から必要な情報を取得し、データをリストに追加
        for item in items:
            link_short = item["href"]

            # itemのlink先にアクセスしてmediaを取得
            response_item = requests.get(link_short, verify=False)
            soup_item = BeautifulSoup(response_item.text, "html.parser")
            media_element = soup_item.select_one("span > a > span > span")
            media_jp = media_element.text if media_element is not None else ""

            # itemのlink先にアクセスしてurl_detailを取得
            url_detail_element = soup_item.select_one("article div div p a")
            link_long = url_detail_element["href"] if url_detail_element is not None else ""
            
            # "/images"を含めて削除
            link_long = re.sub(r"/images.*", "", link_long)

            # itemのlink先にアクセスしてtitle_longを取得
            title_long_element = soup_item.select_one("a > p")
            title_long = title_long_element.text if title_long_element is not None else ""

            title_element = item.find("div", class_="newsFeed_item_title")
            title_short = title_element.text.strip() if title_element is not None else ""

            date_element = item.find("time", class_="newsFeed_item_date")
            date_original = date_element.text.strip() if date_element is not None else ""

            # ctgryをデータに追加
            data.append([ctgry, media_jp, title_short, title_long, link_short, link_long, date_original])

        # インターバルを待つ
        time.sleep(interval)

        # 作業進捗状況をプリント
        print(f"Scraping page {page} of category {ctgry}")

        # 次のページへ
        page += 1
        
        # データがなくなった場合に次のURLにスイッチ
        if not items:
            print(f"No more data for {ctgry}. Switching to next URL.")
            break

    # データをDataFrameに変換
    df = pd.DataFrame(data, columns=["ctgry", "media_jp", "title_short", "title_long", "link_short", "link_long", "date_original"])

    # 現在の日付を取得
    now = datetime.now()
    date_string = now.strftime("%Y%m%d_%H%M%S")

    # DataFrameをCSVファイルとして書き出し（エンコーディング：CP932）
    filename = f"./{ctgry}_{date_string}.csv"  # here we modify the filename to be in the current directory
    print(f"Saving to file: {filename}")  # print filename for debugging
    df.to_csv(filename, index=False, encoding="CP932", errors="ignore")

    # ファイルをDropboxにアップロード
    with open(filename, "rb") as file:
        dbx.files_upload(file.read(), f"/{folder_name}/{filename}", mode=dropbox.files.WriteMode.overwrite)

    # 作業完了メッセージをプリント
    print(f"Scraping complete for {ctgry}. File saved: {filename} and uploaded to Dropbox.")
