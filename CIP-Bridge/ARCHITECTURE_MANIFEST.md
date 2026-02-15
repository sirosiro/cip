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
*   **キーワード駆動の自律制御 (Keyword-Driven Autonomy):** AIの出力に含まれる特定のキーワード (`[NEED_CONSENSUS]`) を検知した瞬間のみ、自律モードに移行すること。
*   **疎結合な通信 (Loosely Coupled Communication):** エージェント間の通信はファイルシステム (`FS-Bus`) を介して非同期に行い、プロセス間の直接的な依存を排除すること。

#### 2. 主要なアーキテクチャ決定の記録 (Key Architectural Decisions)
*   **Date:** 2026-02-15
*   **Core Principle:** 透過的プロキシ
*   **Decision:** Python の `pty.spawn()` 相当の機能と `selectors` による非同期 I/O を採用。
*   **Rationale:** `gemini-cli` に本物のターミナルであると認識させ、ANSIエスケープシーケンスを維持するため。

#### 3. AIとの協調に関する指針 (AI Collaboration Policy)
*   **モード遷移の透明性:** モードが切り替わる際は、必ずターミナル上にステータス（「Negotiating...」等）を表示し、エンジニアが状況を把握できるようにすること。

#### 4. コンポーネント設計仕様 (Component Design Specifications)

<!--
### 4.1. PTY Controller (PTY制御)
- **責務:** `gemini-cli` を子プロセスとして起動し、マスター/スレーブPTYを介して入出力を制御する。
- **提供するAPI:**
    - `spawn(argv)`: 指定されたコマンドをPTY内で実行する。
    - `read_master()`: ターミナルの出力を読み取る。
    - `write_master(data)`: ターミナルへ入力を送り込む。
- **重要なアルゴリズム:** 非ブロッキングな I/O 多重化（`selectors` を使用）。

### 4.2. FS-Bus Manager (IPC管理)
- **責務:** `./cip_bus/` 配下のディレクトリ構造を用いたメッセージの読み書き。
- **データ構造:**
    - `bridge.pid`: 自身のPID。
    - `inbox`: 外部からの受信メッセージ（追記型テキスト）。
- **状態遷移:** `SIGUSR1` 受信時に `inbox` を読み取って AI へ注入する。

### 4.3. Stream Analyzer (ストリーム解析)
- **責務:** 出力バッファを監視し、キーワード (`[NEED_CONSENSUS]`, `[COMPLETED]`) を検知する。
- **重要なアルゴリズム:** ステートマシンによるエスケープシーケンスのスキップとキーワードマッチング。
-->
