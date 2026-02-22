# CIP-Bridge 検証手順書

本ドキュメントは、プロジェクトルートに影響を与えない安全なサンドボックス環境（sandbox/）において、`bridge.py` および CIP 通信エコシステムの機能を検証するための手順を定義します。

## 1. 事前準備 (PATHの設定)

`bridge.py` をどこからでも実行できるように、現在のセッションで `PATH` を通します。

```bash
# プロジェクトルートで実行
export PATH="$PWD/CIP-Bridge:$PATH"

# 実行権限の確認（既に付与済みのはずですが、念のため）
# bridge.py -h または bridge.py --version (未実装ならエラーでOK) が動けばパスが通っています
```

---

## 2. 環境構築 (Sandbox Fractal)

Leader（上位）と Worker（下位）の階層構造をシミュレートするため、`sandbox/` 内にフラクタルなディレクトリ構造を作成します。

```bash
# 以前のテストデータをクリーンアップ
rm -rf sandbox/leader_node

# 階層構造の作成: leader_node -> worker_node
mkdir -p sandbox/leader_node/worker_node

# 憲法（DESIGN_PHILOSOPHY.md）のみ Leader のルートに配備
ln DESIGN_PHILOSOPHY.md sandbox/leader_node/
```

---

## 3. Leader ノードのブートストラップ

Leader が正しく初期化され、自身の役割を認識することを確認します。

1.  **Leader の起動:**
    新しいターミナルを開き、再度 `PATH` を設定してから起動します。
    ```bash
    export PATH="$PWD/CIP-Bridge:$PATH" # 新しいターミナルの場合
    cd sandbox/leader_node
    bridge.py
    ```

2.  **期待される挙動:**
    *   **通知:** `[SYSTEM] 初期化コンテキストを受信しました...` というメッセージが表示されます。
    *   **自律アクション:** AI が自動的に `read_file current_message.md` を実行します。
    *   **役割認識:** `DESIGN_PHILOSOPHY.md` を読み込んだ後、AI が `[READY]` と出力し、自身を「Root Leader」または「Local Leader」と定義して待機状態になります。

---

## 4. Worker ノードのブートストラップ

Worker が初期化され、Leader の設計思想（憲法）と連結されることを確認します。

1.  **Worker の起動:**
    別の新しいターミナルを開き、同様に `PATH` を設定して起動します。
    ```bash
    export PATH="$PWD/CIP-Bridge:$PATH"
    cd sandbox/leader_node/worker_node
    bridge.py
    ```

2.  **期待される挙動:**
    *   **Philosophy Linking:** `bridge.py` が自動的に `../DESIGN_PHILOSOPHY.md` へのシンボリックリンクを作成します。
    *   **Bus Linking:** `bridge.py` が自動的に `cip_bus` を `../cip_bus` へリンクします。
    *   **自律アクション:** Leader 同様、`current_message.md` を読み込み、`[READY]` 状態で待機します。

---

## 5. 疎通テスト (双方向ネゴシエーション・ループ)

XMLタグを用いた Pull型通信プロトコルが機能することを確認します。

1.  **アクション (Leader 側のターミナル):**
    Leader AI に対し、以下の指示をコピー＆ペーストして実行させてください。

    ```text
    通信プロトコルのテストを行います。
    @worker_node に対して、[NEED_CONSENSUS] 「君の今のCIP-BridgeAIペアの役割を報告せよ」[/NEED_CONSENSUS] というタグで挟んでメッセージを送信してください。
    それ以外の分析や考古学的調査は不要です。メッセージの送信（出力）のみを行ってください。
    ```

2.  **期待されるフロー:**
    *   **Leader:** `[NEED_CONSENSUS] ... [/NEED_CONSENSUS]` を出力。
    *   **Worker:** 画面に `[SYSTEM] 新着メッセージがあります...` が表示され、自動的に `read_file current_message.md` を実行。
    *   **Worker:** 内容を読み取り、`[ACCEPTED] ... [/ACCEPTED]` タグを付けて返信を出力。
    *   **Leader:** 通知を受け取り、`current_message.md` を読み、Worker からの応答を確認して完了。

---

## 6. 後片付け

検証が完了したら、サンドボックスを削除できます。

```bash
rm -rf sandbox/leader_node
```
