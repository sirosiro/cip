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

## 5. フラクタル初期化と役割判断の確認 (Fractal Bootstrap)

`bridge.py` がサブディレクトリで起動した際、自動的に環境を構築し、AIに役割を認識させる機能を確認します。

1.  **テスト環境の準備:**
    *   `mkdir -p sandbox/worker_node`
    *   `echo "# Test Manifest" > sandbox/worker_node/ARCHITECTURE_MANIFEST.md`

2.  **CIP-Bridge の起動:**
    *   `cd sandbox/worker_node`
    *   `python3 ../../CIP-Bridge/bridge.py`

3.  **自動挙動の観察:**
    *   起動後、何も入力せずに待機します。
    *   以下の挙動が自動で行われることを確認します：
        1.  `gemini-cli` が起動する。
        2.  `[SYSTEM: Context Initialization]...` というプロンプトが自動入力される。
        3.  `ls -l DESIGN_PHILOSOPHY.md` 等のコマンドが実行される（承認ダイアログは自動でパスする）。
        4.  AIが「憲法を確認しました」「私はWorkerです」等の回答を行い、`[READY]` 状態になる。

4.  **ファイルシステムの確認:**
    *   `bridge.py` を終了後、`ls -la` で以下を確認します：
        *   `DESIGN_PHILOSOPHY.md` -> `../../DESIGN_PHILOSOPHY.md` へのシンボリックリンクが存在すること。
        *   `.gitignore` が生成され、`cip_bus/` 等が含まれていること。

---

## 6. フィードバック

上記のステップで期待通りに動作しない場合は、エラーログ（もしあれば）と共に報告してください。
特に PTY の挙動については、使用しているターミナル（iTerm2, Terminal.app, VSCode Integrated Terminal 等）によって差異が出る可能性があります。