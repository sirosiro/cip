# spec.md: CIP-Bridge (v2.6) - Fractal AI Orchestrator

## 1. 目的 (Objective)

`gemini-cli` をラップし、エンジニアとAI、およびAI同士（Leader/Worker）の通信を制御する自律型プロキシツールを構築する。
特定の専門領域にのみ専門家（下位CIP）を配置し、不在時は上位CIPがカバーする「動的フラクタル構造」を実現する。

## 2. アーキテクチャ (Architecture)

### 2.1 動作モード

* **バイパスモード (Bypass Mode):** ユーザ入力を `gemini-cli` へ透過。ANSIエスケープシーケンス（罫線、メニュー選択）を維持する。
* **オートモード (Auto Mode):** ユーザ入力を遮断。上位(Leader)と下位(Worker)間で `FS-Bus` を介した自動対話を行う。

### 2.2 通信基盤 (FS-Bus + Signal IPC)

* **Base Directory:** `./cip_bus/`
* **Registry:** 各インスタンスは `./cip_bus/<ID>/bridge.pid` に自身のPIDを記録。
* **Mailbox:**
    *   送信先へのメッセージ：`./cip_bus/<TargetID>/inbox`
    *   書き込み完了後、対象PIDへ `SIGUSR1` を送信して通知。

* **I/O多重化:** `selectors` モジュール等を用い、標準入力、PTY出力、およびシグナル受信を非同期で監視。

---

## 3. モード遷移トリガー (Triggers)

| イベント | 条件 | 遷移先 |
| --- | --- | --- |
| **手動介入** | ユーザ入力が `@cip ` で開始 | Auto Mode |
| **合意必要** | Leader出力に `[NEED_CONSENSUS]` を検知 | Auto Mode (Negotiation) |
| **合意完了** | Leader出力に `[COMPLETED]` を検知 | Bypass Mode |
| **強制停止** | `Ctrl+C` 入力 | Bypass Mode (Emergency) |

---

## 4. 交渉プロトコル (Communication Protocol)

`DESIGN_PHILOSOPHY.md` に基づき、各CIPは以下の形式で対話する。

1. **Demand:** Leaderが `[NEED_CONSENSUS] @<WorkerID> <Content>` を出力。
2. **Routing:** `CIP-Bridge` が指定IDの `inbox` へ転送。
3. **Audit:** Workerが内容を吟味し、`[CONFLICT] <Reason>` または `[ACCEPTED]` を出力。
4. **Feedback:** `CIP-Bridge` が上記を Leader の `inbox` へ書き戻し、`SIGUSR1` を送信。
5. **Resolution:** 全ての `[ACCEPTED]` を確認後、Leaderが最終案をまとめ `[COMPLETED]` を出力。

---

## 5. 実装要件 (Technical Requirements)

### 5.1 擬似端末 (PTY) 制御

* `pty.spawn()` を使用し、`gemini-cli` に本物の端末であると誤認させる。
* ユーザの十字キー入力等の特殊シーケンスを破壊せずパススルーする。

### 5.2 動的ディスカバリ (Discovery)

* `@cip` 開始時、`./cip_bus/*/bridge.pid` をスキャンし、現在稼働中の Worker リストを Leader のプロンプトに動的に注入する。
* Worker が不在の ID が指定された場合、Leader に対して「Worker不在」のシステムメッセージを返し、Leader 自身に思考を促す。

### 5.3 ログと可視化

* オートモード中の交渉ログは標準出力（画面）には出さず、`negotiation.log` に記録。
* 画面上には「Negotiating with @cpu_emu...」等の進捗ステータスのみ表示。

### 5.4 Worker Bootstrap Process & Fractal Propagation

`CIP-Bridge` は Worker プロセスを検知した際、以下の初期化プロセスを透過的に実行する。

1.  **環境整備 (Philosophy Link):**
    *   Worker のカレントディレクトリに `DESIGN_PHILOSOPHY.md` のシンボリックリンクを作成する。
    *   リンク先は、現在のディレクトリ階層の深さから計算したルートへの相対パスとする（例: `ln -s ../../DESIGN_PHILOSOPHY.md .`）。これにより、多重リンクを回避し、常にルートの実体を参照させる。

2.  **自律的役割判断 (Autonomous Role Discovery):**
    *   Worker の `inbox` に以下のシステムプロンプトを自動投入し、Worker 自身に役割を判断させる。

    ```markdown
    [SYSTEM: Context Initialization]
    あなたはCIPエコシステムのノードとして起動しました。
    現在のカレントディレクトリ（担当領域）を確認し、以下の手順で自身の役割を自律的に決定してください。

    1. **憲法の確認 (Global Philosophy):**
       ルートの設計思想が存在するか確認し、ロードしてください。
       `$ ls -l DESIGN_PHILOSOPHY.md` (シンボリックリンクなら `cat`, 実体なら `read_file`)

    2. **法律の確認 (Local Manifest):**
       このディレクトリのアーキテクチャ定義（`ARCHITECTURE_MANIFEST.md`）をロードしてください。

    3. **部下の確認 (Sub-Node Discovery):**
       さらに下位のディレクトリ（サブモジュール）が存在するか確認してください。
       もし存在すれば、あなたはそれらのリーダー（Local Leader）としての責務も負います。

    全ての確認が完了したら、現在の役割（Worker / Local Leader / Root Leader）と準備完了の旨を `[READY]` と共に出力してください。
    ```

---

## 6. DESIGN_PHILOSOPHY.md への追記（推奨）

本ツールを駆動させるため、CIPには以下の振る舞いを定義する。

* 「あなたは `[NEED_CONSENSUS]` を使うことで、配下の専門家に詳細設計を委託できる」
* 「専門家が不在であると通知された場合、あなたがその役割を兼務し、核心的意図を維持せよ」

---