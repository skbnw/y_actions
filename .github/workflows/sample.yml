import os
import shutil

# コピー元のディレクトリパス
source_directory = "xml-files"

# コピー先のディレクトリパス
destination_directory = os.path.join(source_directory, "copy")

# コピー先のディレクトリが存在しない場合は作成する
os.makedirs(destination_directory, exist_ok=True)

# xml-filesフォルダ内のすべてのファイルを取得
file_list = os.listdir(source_directory)

# xmlファイルをコピーする
for file_name in file_list:
    if file_name.endswith(".xml"):
        source_path = os.path.join(source_directory, file_name)
        destination_path = os.path.join(destination_directory, file_name)
        try:
            shutil.copy2(source_path, destination_path)
            print(f"コピー完了: {file_name}")
        except Exception as e:
            print(f"コピー失敗: {file_name}")
            print(f"エラーメッセージ: {str(e)}")
