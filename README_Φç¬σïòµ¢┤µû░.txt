VideoEase Studio v3.0 - GitHub Releases 自動更新
================================================

■ 起動
Windowsで Python 3 と FFmpeg をインストールして、起動.bat を実行してください。

■ 初回設定（必須）
1. GitHubで自分のリポジトリを作成（例: yourname/VideoEaseStudio）。
2. update_config.json の OWNER/REPO を自分のリポジトリ名に変更します。
3. GitHub Releases に新しいバージョンを公開します。

■ リリースに必要なファイル
タグが v3.1.0 なら以下の2ファイルを添付してください。
- VideoEaseStudio-v3.1.0.zip
- VideoEaseStudio-v3.1.0.zip.sha256

ZIPの内部は VideoEaseStudio/videoease.py、updater.py、apply_update.py、
update_config.json、起動.bat 等が入った構造にしてください。

SHA256ファイルはZIPのSHA256値を64桁の16進文字列で保存します。
PowerShellで: (Get-FileHash .\VideoEaseStudio-v3.1.0.zip -Algorithm SHA256).Hash.ToLower()

■ 自動更新
起動約2秒後に最新版を確認します。画面右上の「更新確認」でも確認可能です。
新バージョンを見つけたら確認ダイアログを表示し、承諾後にダウンロードします。
検証が成功したらアプリを閉じ、別プロセスで更新を適用し再起動します。
再起動時の健康チェックに失敗した場合は旧バージョンを復元します。

■ 注意
- 更新元は設定したGitHubリポジトリのReleaseです。GitHubアカウントとリポジトリを適切に保護してください。
- 旧バージョン v2 はこの自動更新機能を持たないため、v3への切り替えは一度だけ手動で必要です。
- インストール先フォルダに書き込み権限が必要です。Program Filesへの直接配置は非推奨です。
- 起動確認はGUIが立ち上がったことのみを確認します。編集・書き出しの全機能をテストするものではありません。
- 更新後のプログラムに古いファイルが残る場合があります。ユーザーデータの削除を避けるためです。
- Windows実機での動作確認は未実施です。
- GitHub Releasesに公開する新しいZIPは信頼できる作成者が作成したものだけにしてください。
