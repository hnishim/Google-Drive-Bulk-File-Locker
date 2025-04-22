# Google Drive File Locker

指定されたGoogle Driveフォルダ内のすべてのファイル（サブフォルダ内も含む）を再帰的にロック（編集不可に）するPythonスクリプトです。クリップボードからフォルダURLを読み取り、Google Drive APIを使用して処理を実行します。

**注意:** このスクリプトはファイルのコンテンツ制限機能を利用してロックを実現します。GoogleフォームやGoogleサイトなど、一部のファイルタイプはロックできません。また、スクリプトを実行するアカウントは対象ファイルに対する編集権限が必要です。

## 機能

* クリップボードにコピーされたGoogle DriveフォルダURLを自動で読み取り
* 指定されたフォルダ配下のファイルを再帰的に探索
* 編集権限があり、ロック可能なファイルをロック（読み取り専用に設定）
* 既にロックされているファイル、ロック不可能なファイルタイプ（Googleフォーム等）、編集権限がないファイルはスキップ
* OAuth 2.0認証を使用（初回実行時にブラウザでの認証が必要）

## 前提条件

* Python 3.7以上
* Google Cloud Platform (GCP) アカウント
* 必要なPythonライブラリ（`requirements.txt` に記載）

## セットアップ手順

### 1. Google Cloud Platform (GCP) 設定

1.  **GCPプロジェクトの作成または選択:**
    * [Google Cloud Console](https://console.cloud.google.com/)にアクセスし、プロジェクトを選択または新規作成します。
2.  **Google Drive APIの有効化:**
    * ナビゲーションメニュー >「APIとサービス」>「ライブラリ」で「Google Drive API」を検索し、有効にします。
3.  **OAuth 同意画面の設定:**
    * 「APIとサービス」>「OAuth 同意画面」で設定を行います。
    * **User Type:** 「外部」を選択（テスト段階ではこれでOK）。
    * **アプリ情報:** アプリ名（例: `Drive File Locker`）、ユーザーサポートメール、デベロッパーの連絡先情報を入力します。
    * **スコープ:** 「スコープを追加または削除」をクリックし、`Google Drive API` の `.../auth/drive` スコープを追加します。（全ファイルへのアクセス権限）
    * **テストユーザー:** 「+ ADD USERS」をクリックし、このスクリプトを使用するご自身のGoogleアカウントのメールアドレスを追加します。
    * 設定を保存します。
4.  **認証情報（OAuth 2.0 クライアント ID）の作成:**
    * 「APIとサービス」>「認証情報」に移動します。
    * 「+ 認証情報を作成」>「OAuth クライアント ID」を選択します。
    * **アプリケーションの種類:** 「デスクトップアプリ」を選択します。
    * 名前（例: `Drive Locker Desktop Client`）を入力し、「作成」をクリックします。
    * 作成されたクライアントIDの右側にあるダウンロードアイコンをクリックし、JSONファイルをダウンロードします。
    * ダウンロードしたファイルを **`credentials.json`** という名前に変更し、このプロジェクトのルートディレクトリ（`lock_drive_files.py` と同じ場所）に配置します。

### 2. Python 環境の準備

1.  このリポジトリをクローンまたはダウンロードします。
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```
2.  Python 仮想環境を構築し有効化します。
    ```bash
    python3 -m venv <newenvname>
    source [newenvname]/bin/activate
    ```
3.  必要なライブラリをインストールします。
    ```bash
    pip install -r requirements.txt
    ```

## 使い方
事前に2. で作成した仮想環境を `source [newenvname]/bin/activate` で有効化してください。

1.  ロックしたいGoogle Driveフォルダをブラウザで開き、その**フォルダのURL**をクリップボードにコピーします。
    * 例: `https://drive.google.com/drive/folders/xxxxxxxxxxxxxxxxxxx`
2.  ターミナル（コマンドプロンプト）でスクリプトを実行します。
    ```bash
    python lock_drive_files.py
    ```
3.  **初回実行時のみ:**
    * ブラウザが自動的に起動し、Googleアカウントへのアクセス許可を求める画面が表示されます。
    * GCPでテストユーザーとして登録したアカウントを選択し、「許可」または「Allow」をクリックします。
    * 認証が成功すると、`token.json` というファイルがスクリプトと同じディレクトリに作成されます。これには認証情報が保存されており、次回以降の実行時に利用されます。
4.  スクリプトがファイルの探索とロック処理を開始します。処理状況はターミナルに出力されます。
5.  処理完了後、ロック成功、スキップ、失敗の件数が表示されます。

## 設定ファイル

* **`credentials.json`**: GCPからダウンロードしたOAuthクライアント情報。 **このファイルは絶対に公開しないでください。`.gitignore` に追加することを強く推奨します。**
* **`token.json`**: 初回認証後に自動生成されるアクセストークン情報。 **このファイルも公開せず、`.gitignore` に追加してください。**

## 注意事項

* **権限:** スクリプトを実行するGoogleアカウントは、対象フォルダおよびその中のすべてのファイルに対する**編集権限**が必要です。
* **ロックできないファイル:** Googleフォーム (`application/vnd.google-apps.form`)、Googleサイト (`application/vnd.google-apps.site`)、Google Apps Script (`application/vnd.google-apps.script`)、ショートカット (`application/vnd.google-apps.shortcut`) などはロックできません。これらは自動的にスキップされます。
* **API制限:** Google Drive APIには使用量制限があります。非常に大量のファイルを処理する場合、制限に達する可能性があります。
* **エラー処理:**基本的なエラー処理は含まれていますが、すべてのケースに対応しているわけではありません。

## .gitignore の推奨

セキュリティと不要なファイルの管理のため、以下の内容で `.gitignore` ファイルを作成することを推奨します。

```gitignore
# Credentials / Tokens
credentials.json
token.json

# Python cache
__pycache__/
*.py[cod]
*$py.class

# Environment
.env
venv/
ENV/