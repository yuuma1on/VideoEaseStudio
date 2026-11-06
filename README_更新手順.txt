VideoEase Studio v3.1.2 更新配信準備

これはWindows EXE本体ではなく、GitHub ActionsでEXEと更新ZIPを作るソース一式です。
1. ZIPの VideoEaseStudio フォルダーの中身（.githubを含む）をGitHubリポジトリのルートにアップロードし、mainにコミット。
2. GitHubの Settings > Actions > General > Workflow permissions を Read and write permissions に設定（必要な場合）。
3. GitHubでタグ v3.1.2 をmainの最新コミットに作成してpush。GitHubの画面からReleaseを先に手動作成しないこと。
4. Actionsタブで Build and publish VideoEase Studio の成功を確認。
5. Releasesに VideoEaseStudio-v3.1.2.zip と .sha256 が生成されたら、手元のv3.1.1 EXEの「更新確認」を押す。

注意：v3.1.1の更新・復元機能はWindows実機で未検証です。最初はインストールフォルダーをコピーしてからテストしてください。
GitHub Actionsの無料枠やリポジトリ設定によりビルドできない場合があります。
