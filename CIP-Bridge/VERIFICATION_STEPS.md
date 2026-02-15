# CIP-Bridge Verification Steps (Phase 1 Prototype)

本手順書は、`CIP-Bridge/bridge.py` の基本動作（PTYパススルー、FS-Bus、キーワード検知）をエンジニアが手動で検証するためのものです。

## 1. 準備

*   `gemini-cli` がインストールされ、PATHが通っていること。
*   Python 3 がインストールされていること。

## 2. 基本動作の確認 (Passthrough)

1.  ターミナルで `./CIP-Bridge` ディレクトリに移動します。
2.  `python3 bridge.py` を実行します。
3.  `gemini-cli` の起動画面が表示されることを確認します。
4.  通常通りプロンプトを入力し、AIからの回答が正しく表示されること、および罫線や色などが崩れていないことを確認します。
5.  `Ctrl+C` または `exit` で終了し、ターミナルの表示が元に戻ることを確認します。

## 3. キーワード検知の確認 (Trigger Detection)

1.  `python3 bridge.py` を再度実行します。
2.  AIに対して、あえて `[NEED_CONSENSUS]` という文字列を含む回答をさせるようなプロンプトを入力します。
    *   例: 「『[NEED_CONSENSUS] テスト要求』とだけ出力して」
3.  回答が表示された後、`CIP-Bridge/bridge_events.log` というファイルが生成され、`Detected [NEED_CONSENSUS]` と記録されていることを確認します。

## 4. FS-Bus / SIGUSR1 の確認 (Signal IPC)

1.  `python3 bridge.py` を実行した状態のままにします。
2.  別のターミナルを開き、以下の操作を行います。
    *   `./cip_bus/leader/inbox` ファイルにメッセージを書き込みます。
        *   `echo "外部からの注入テスト" > cip_bus/leader/inbox`
    *   `bridge.pid` を読み取って、プロセスに `SIGUSR1` を送信します。
        *   `kill -USR1 $(cat cip_bus/leader/bridge.pid)`
3.  元のターミナル（Bridgeが動いている方）で、AIに対して "外部からの注入テスト" というプロンプトが自動的に入力され、AIが回答を開始することを確認します。

---

## 5. フィードバック

上記のステップで期待通りに動作しない場合は、エラーログ（もしあれば）と共に報告してください。
特に PTY の挙動については、使用しているターミナル（iTerm2, Terminal.app, VSCode Integrated Terminal 等）によって差異が出る可能性があります。
