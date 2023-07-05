#!/usr/bin/env python
# coding: utf-8

import dropbox
import os
from datetime import datetime
import time

# Dropbox APIのアクセストークン
ACCESS_TOKEN = 'sl.BhqKDcUkIMbvkdbiQEN_MAbOZAnFqO9j8dNNEcnVZv0FwA2AqnIyn6a0C0iYlGa20bUCkPhE14JtsmNQaxI79nxM1IBgVb9JNyqeWN_l5EDvauf1I4BT9KTls6bmd5_GkOB4BJc'

# Dropboxへの接続
dbx = dropbox.Dropbox(ACCESS_TOKEN)

# フォルダ名
folder_name = 'xml-files'

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

# XMLファイルをアップロード
def upload_file(file_path, file_name, folder_name):
    try:
        with open(file_path, 'rb') as f:
            file_data = f.read()
        dbx.files_upload(file_data, '/' + folder_name + '/' + file_name)
        print(f"File '{file_name}' uploaded successfully.")
    except dropbox.exceptions.ApiError as e:
        print(f"Failed to upload file '{file_name}': {e}")

# XMLファイルの取得とアップロード
def fetch_and_upload_xml_files():
    current_time = datetime.now().strftime('%Y%m%d_%H%M')
    xml_directory = 'xml-files'
    os.makedirs(xml_directory, exist_ok=True)
    
    rss_feeds = [
        ('top-picks', 'https://news.yahoo.co.jp/rss/topics/top-picks.xml'),
        ('domestic', 'https://news.yahoo.co.jp/rss/topics/domestic.xml'),
        ('world', 'https://news.yahoo.co.jp/rss/topics/world.xml'),
        ('business', 'https://news.yahoo.co.jp/rss/topics/business.xml'),
        ('entertainment', 'https://news.yahoo.co.jp/rss/topics/entertainment.xml'),
        ('sports', 'https://news.yahoo.co.jp/rss/topics/sports.xml'),
        ('it', 'https://news.yahoo.co.jp/rss/topics/it.xml'),
        ('local', 'https://news.yahoo.co.jp/rss/topics/local.xml'),
        ('science', 'https://news.yahoo.co.jp/rss/topics/science.xml')
    ]

    for feed_name, feed_url in rss_feeds:
        xml_file = f'{xml_directory}/{feed_name}_{current_time}.xml'
        subprocess.run(['curl', '-o', xml_file, feed_url])
        time.sleep(3)
        if os.path.isfile(xml_file):
            upload_file(xml_file, os.path.basename(xml_file), folder_name)
        else:
            print(f"File '{xml_file}' does not exist.")

# XMLファイルの取得とアップロードを実行
fetch_and_upload_xml_files()


# In[ ]:




