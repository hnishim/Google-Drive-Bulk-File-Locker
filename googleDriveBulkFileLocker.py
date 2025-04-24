import os.path
import re
import pyperclip # クリップボード操作
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --- 設定 ---
# Google Drive APIのスコープ (フルアクセスが必要)
SCOPES = ['https://www.googleapis.com/auth/drive']
# 認証情報ファイル
CREDENTIALS_FILE = 'credentials.json'
# トークンファイル (初回認証後に自動生成される)
TOKEN_FILE = 'token.json'
# ロックできないMIMEタイプ (必要に応じて追加)
NON_LOCKABLE_MIME_TYPES = [
    'application/vnd.google-apps.form',
    'application/vnd.google-apps.site',
    'application/vnd.google-apps.script',
    'application/vnd.google-apps.shortcut', # ショートカット自体はロックできない
    'application/vnd.google-apps.folder',   # フォルダは対象外 (今回はフォルダ自体をロック対象外とするが、判定には使用)
]
# ロック理由
LOCK_REASON = 'Locked by automated script'

# --- 関数 ---

def authenticate():
    """Google Drive APIの認証を行い、サービスオブジェクトを返す"""
    creds = None
    # token.jsonが存在すれば、既存の認証情報を読み込む
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception as e:
            print(f"トークンファイルの読み込みに失敗しました: {e}")
            creds = None # エラー時は再認証へ

    # 認証情報がない、または無効な場合
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print("認証情報が期限切れのため、リフレッシュしています...")
                creds.refresh(Request())
            except Exception as e:
                print(f"トークンのリフレッシュに失敗しました: {e}")
                # リフレッシュ失敗時は再認証フローへ
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
        else:
            # 新規認証
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"エラー: {CREDENTIALS_FILE} が見つかりません。")
                print("GCPコンソールからダウンロードし、スクリプトと同じディレクトリに配置してください。")
                return None
            print("新規認証が必要です。ブラウザが起動します...")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        # 新しい認証情報をtoken.jsonに保存
        try:
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
            print(f"認証情報を {TOKEN_FILE} に保存しました。")
        except Exception as e:
            print(f"警告: トークンファイルの保存に失敗しました: {e}")

    try:
        service = build('drive', 'v3', credentials=creds)
        print("Google Drive APIへの接続に成功しました。")
        return service
    except HttpError as error:
        print(f"サービス構築中にエラーが発生しました: {error}")
        return None
    except Exception as e:
        print(f"予期せぬエラーが発生しました: {e}")
        return None

def get_id_from_url(url):
    """Google DriveのURLからファイル/フォルダIDを抽出する"""
    # 新しい形式: https://drive.google.com/open?id=<ID>&usp=drive_fs
    match_open = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', url)
    if match_open:
        return match_open.group(1)

    # 従来のフォルダ形式: /folders/ または /drive/folders/ の後の英数字とハイフン、アンダースコアにマッチ
    match_folder = re.search(r'/folders/([a-zA-Z0-9_-]+)', url)
    if match_folder:
        return match_folder.group(1)

    # 従来のファイル形式: /file/d/<ID>/view
    match_file = re.search(r'/file/d/([a-zA-Z0-9_-]+)/view', url)
    if match_file:
        return match_file.group(1)

    # drive/u/0/folders/ のような形式も考慮
    match_u_folder = re.search(r'drive/u/\d+/folders/([a-zA-Z0-9_-]+)', url)
    if match_u_folder:
        return match_u_folder.group(1)

    # drive/u/0/file/d/<ID>/view のような形式も考慮
    match_u_file = re.search(r'drive/u/\d+/file/d/([a-zA-Z0-9_-]+)/view', url)
    if match_u_file:
        return match_u_file.group(1)

    return None

def get_mime_type(service, file_id):
    """指定されたIDのMIMEタイプを取得する"""
    try:
        file = service.files().get(fileId=file_id, fields='mimeType', supportsAllDrives=True).execute()
        return file.get('mimeType')
    except HttpError as error:
        print(f"ID '{file_id}' のMIMEタイプ取得中にエラーが発生しました: {error}")
        return None
    except Exception as e:
        print(f"ID '{file_id}' のMIMEタイプ取得中に予期せぬエラーが発生しました: {e}")
        return None

def get_file_metadata(service, file_id):
    """指定されたIDのファイルメタデータを取得する"""
    try:
        # 取得フィールドに contentRestrictions を追加
        fields = 'id, name, mimeType, capabilities, contentRestrictions'
        file = service.files().get(fileId=file_id, fields=fields, supportsAllDrives=True).execute()
        return file
    except HttpError as error:
        print(f"ID '{file_id}' のメタデータ取得中にエラーが発生しました: {error}")
        return None
    except Exception as e:
        print(f"ID '{file_id}' のメタデータ取得中に予期せぬエラーが発生しました: {e}")
        return None


def list_files_recursive(service, folder_id):
    """指定されたフォルダID配下の全ファイル(サブフォルダ含む)を再帰的に取得"""
    all_files = []
    page_token = None
    # 取得フィールドに contentRestrictions を追加
    query_fields = 'nextPageToken, files(id, name, mimeType, capabilities, contentRestrictions)'
    query = f"'{folder_id}' in parents and trashed = false"

    print(f"フォルダID '{folder_id}' の内容を取得中...")

    while True:
        try:
            response = service.files().list(
                q=query,
                spaces='drive',
                fields=query_fields,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()

            files = response.get('files', [])
            print(f"  フォルダ内で {len(files)} 個のアイテムを発見。")

            for file in files:
                if file.get('mimeType') == 'application/vnd.google-apps.folder':
                    # サブフォルダの場合、再帰的に探索
                    print(f"  サブフォルダ '{file.get('name')}' (ID: {file.get('id')}) を探索中...")
                    all_files.extend(list_files_recursive(service, file.get('id')))
                else:
                    # ファイルの場合、リストに追加
                    all_files.append(file)

            page_token = response.get('nextPageToken', None)
            if page_token is None:
                break # 次のページがなければ終了

        except HttpError as error:
            print(f"フォルダ '{folder_id}' のファイルリスト取得中にエラーが発生しました: {error}")
            break # エラーが発生したらそのフォルダの探索は中断

    return all_files

def lock_file(service, file_id, file_name):
    """指定されたファイルをロック（コンテンツ制限を追加）する"""
    try:
        # コンテンツ制限を設定してファイルを更新
        updated_file = service.files().update(
            fileId=file_id,
            body={'contentRestrictions': [{'readOnly': True, 'reason': LOCK_REASON}]},
            fields='id, name, contentRestrictions', # 更新結果確認用
            supportsAllDrives=True
        ).execute()
        # 制限が実際に適用されたか確認（より確実に）
        restrictions = updated_file.get('contentRestrictions', [])
        if any(r.get('readOnly') for r in restrictions):
             print(f"  成功: ファイル '{file_name}' (ID: {file_id}) をロックしました。")
             return True
        else:
             # APIコールは成功したがreadOnlyになっていない場合（通常はないはず）
             print(f"  警告: ファイル '{file_name}' (ID: {file_id}) のロックAPIは成功しましたが、readOnly制限が適用されませんでした。")
             return False

    except HttpError as error:
        # よくあるエラーを判別
        if error.resp.status == 403:
             # Forbidden: 権限不足、またはロック非対応ファイルの可能性
             print(f"  失敗: ファイル '{file_name}' (ID: {file_id}) をロックできませんでした。理由: {error.reason} (権限不足またはロック非対応の可能性があります)")
        elif error.resp.status == 400:
             # Bad Request: リクエスト自体が不正 (例: 既に別の種類の制限がある?)
              print(f"  失敗: ファイル '{file_name}' (ID: {file_id}) をロックできませんでした。理由: {error.reason} (不正なリクエスト)")
        else:
            print(f"  失敗: ファイル '{file_name}' (ID: {file_id}) のロック中に予期せぬAPIエラーが発生しました: {error}")
        return False
    except Exception as e:
        print(f"  失敗: ファイル '{file_name}' (ID: {file_id}) のロック中に予期せぬエラーが発生しました: {e}")
        return False

# --- メイン処理 ---
if __name__ == '__main__':
    # 1. 認証
    service = authenticate()
    if not service:
        exit()

    # 2. クリップボードからURLを取得
    try:
        drive_url = pyperclip.paste()
        if not drive_url:
            print("エラー: クリップボードが空です。")
            exit()
        print(f"クリップボードからURLを取得しました: {drive_url}")
    except Exception as e:
        print(f"クリップボードからの読み取りに失敗しました: {e}")
        print("pyperclipが正しくインストールされ、動作しているか確認してください。")
        exit()

    # 3. URLからIDを抽出
    item_id = get_id_from_url(drive_url)
    if not item_id:
        print("エラー: クリップボードの内容から有効なGoogle Driveのファイル/フォルダIDが見つかりませんでした。")
        print("対応しているURL形式例:")
        print("  - https://drive.google.com/open?id=xxxxxxxxxxxxxxxxxxx&usp=drive_fs")
        print("  - https://drive.google.com/drive/folders/xxxxxxxxxxxxxxxxxxx")
        print("  - https://drive.google.com/file/d/xxxxxxxxxxxxxxxxxxx/view")
        exit()
    print(f"IDを抽出しました: {item_id}")

    # 4. IDのMIMEタイプを取得してファイルかフォルダか判定
    print(f"ID '{item_id}' のMIMEタイプを取得中...")
    item_mime_type = get_mime_type(service, item_id)

    all_files_to_process = []

    if item_mime_type is None:
        print(f"エラー: ID '{item_id}' のMIMEタイプを取得できませんでした。処理を中断します。")
        exit()
    elif item_mime_type == 'application/vnd.google-apps.folder':
        print(f"ID '{item_id}' はフォルダです。フォルダ内のファイルを再帰的に取得します。")
        # フォルダの場合、再帰的にファイルリストを取得
        all_files_to_process = list_files_recursive(service, item_id)
    else:
        print(f"ID '{item_id}' はファイル (MIMEタイプ: {item_mime_type}) です。このファイルを処理します。")
        # ファイルの場合、そのファイルのメタデータを取得してリストに追加
        file_metadata = get_file_metadata(service, item_id)
        if file_metadata:
            all_files_to_process.append(file_metadata)
        else:
            print(f"エラー: ファイルID '{item_id}' のメタデータを取得できませんでした。処理を中断します。")
            exit()

    print(f"\n合計 {len(all_files_to_process)} 個のアイテムをロック対象として検出しました。")

    # 5. 各アイテムをロック
    print("\nアイテムのロック処理を開始します...")
    locked_count = 0
    skipped_count = 0
    failed_count = 0

    if not all_files_to_process:
        print("ロック対象のアイテムが見つかりませんでした。")
    else:
        for item in all_files_to_process:
            item_id = item.get('id')
            item_name = item.get('name')
            mime_type = item.get('mimeType')
            capabilities = item.get('capabilities', {})
            content_restrictions = item.get('contentRestrictions', []) # 既存の制限を取得

            # フォルダ自体はロック対象外とする
            if mime_type == 'application/vnd.google-apps.folder':
                 print(f"- スキップ: フォルダ '{item_name}' (ID: {item_id}) はロック対象外です。")
                 skipped_count += 1
                 continue

            print(f"- アイテム '{item_name}' (MIME: {mime_type}, ID: {item_id}) を処理中...")

            # --- 既にロックされているかチェック ---
            is_already_locked = False
            for restriction in content_restrictions:
                if restriction.get('readOnly', False):
                    is_already_locked = True
                    break # readOnlyが見つかればチェック終了

            if is_already_locked:
                print(f"  スキップ: アイテム '{item_name}' は既にロックされています。")
                skipped_count += 1
                continue
            # --- チェック完了 ---

            # ロックできないタイプかチェック
            if mime_type in NON_LOCKABLE_MIME_TYPES:
                print(f"  スキップ: MIMEタイプ '{mime_type}' はロックできません。")
                skipped_count += 1
                continue

            # --- Capabilities チェック ---
            can_edit = capabilities.get('canEdit', False) # 編集権限
            # canModifyEditorContentRestrictionを使用
            can_modify_restriction = capabilities.get('canModifyEditorContentRestriction', False)

            if not can_edit:
                print(f"  スキップ: アイテム '{item_name}' への編集権限がありません。")
                skipped_count += 1
                continue

            # API Capabilitiesでロック不可と示されている場合
            # (編集権限があっても、このcapabilityがFalseの場合がある)
            if not can_modify_restriction:
                print(f"  スキップ: APIによるとアイテム '{item_name}' のコンテンツ制限を変更できません。")
                skipped_count += 1
                continue
            # --- チェック完了 ---

            # ロック処理を実行
            if lock_file(service, item_id, item_name):
                locked_count += 1
            else:
                failed_count += 1

    # 6. 結果表示
    print("\n--- 処理結果 ---")
    print(f"ロック成功: {locked_count} 件")
    print(f"スキップ  : {skipped_count} 件 (既にロック済み、ロック非対応タイプ、権限不足、フォルダなど)")
    print(f"ロック失敗: {failed_count} 件 (APIエラーなど)")
    print("---------------")