# CIP-Bridge ARCHITECTURE_MANIFEST.md

---

### **Part 1: このマニフェストの取扱説明書 (Guide)**

#### 1. 目的 (Purpose)
本ドキュメントは、`gemini-cli` をラップし、AI間の自律的な交渉（Negotiation）を仲介するプロキシツール **CIP-Bridge** の設計思想と仕様を定義します。

#### 2. 憲章の書き方 (Guidelines)
*   **原則:** PTY（擬似端末）の透過性を最優先し、ユーザー体験を損なわないこと。
*   **なぜ:** `gemini-cli` はインタラクティブなUIを持っており、これらが破壊されるとエンジニアの作業効率が著しく低下するためです。

---

### **Part 2: マニフェスト本体 (Content)**

#### 1. 核となる原則 (Core Principles)
*   **透過的プロキシ (Transparent Proxy):** 通常時はユーザーの入出力を一切加工せず `gemini-cli` へ渡すこと。
*   **構造化メッセージング (XML-Tagged Messaging):** エージェント間の通信は、`[TAG]` と `[/TAG]` で囲まれた構造化データとして扱い、解析の堅牢性を確保すること。
*   **Pull型コンテキスト注入 (Pull-Based Context):** 大規模なメッセージやプロンプトは直接 PTY に流し込まず、`current_message.md` 等のファイルを介して AI に自律的に読み取らせること。

#### 2. 主要なアーキテクチャ決定の記録 (Key Architectural Decisions)
*   **Date:** 2026-02-15
*   **Decision:** Python の `pty.spawn()` 相当の機能と非同期 I/O を採用。
*   **Date:** 2026-02-22
*   **Decision:** シグナルハンドラからメインループへの通知アーキテクチャ (Signal-Safe) への移行。
*   **Decision:** エコーバックによる無限ループ回避のため、`[FROM: @...]` タグを含む行の転送を禁止。
*   **Decision:** PTYバッファ溢れ回避のため、長文送信を廃止し、Pull型（ファイル経由）の通知システムを採用。

#### 3. AIとの協調に関する指針 (AI Collaboration Policy)
*   **自律的読み込みの推奨:** AI は `[SYSTEM]` 通知を受け取った際、自律的に `read_file` を実行し、コンテキストを同期する義務を負う。

#### 4. コンポーネント設計仕様 (Component Design Specifications)

### 4.1. PTY Controller (PTY制御)
- **責務:** `gemini-cli` の入出力を制御し、ANSIエスケープシーケンスを維持する。
- **アルゴリズム:** 非ブロッキング I/O 多重化とタイムアウトによるハングアップ防止。

### 4.2. FS-Bus Manager (IPC管理)
- **責務:** `./cip_bus/` を介したメッセージ交換。
- **データフロー (Pull型):**
    1. 受信メッセージを `inbox` から取得。
    2. `current_message.md` に上書き保存（アトミック性を確保）。
    3. AI に対し `read_file current_message.md` を促す通知を PTY に送信。

### 4.3. Stream Analyzer (構造化パース)
- **責務:** `output_buffer` からタグ付きメッセージを抽出する。
- **アルゴリズム:** 文字列検索 (`index`, `slice`) による堅牢な抽出。開始・終了タグのペアが揃った時のみ転送を実行。

### 4.4. Worker Manager (Worker管理)
- **責務:**
    - **Philosophy Inheritance:** 親ディレクトリを遡り `DESIGN_PHILOSOPHY.md` への相対シンボリックリンクを作成。
    - **Bootstrap:** `inbox` 経由で初期化プロンプトを提供し、役割の自律認識を促す。
