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
*   **トランスポートの抽象化 (Transport Abstraction):** 通信媒体（ファイルシステム、ネットワーク等）に依存しない疎結合な設計を維持すること。

#### 2. 主要なアーキテクチャ決定の記録 (Key Architectural Decisions)
*   **Date:** 2026-02-15
*   **Decision:** Python の `pty.spawn()` 相当の機能と非同期 I/O を採用。
*   **Date:** 2026-02-22
*   **Decision:** シグナルハンドラからメインループへの通知アーキテクチャ (Signal-Safe) への移行。
*   **Date:** 2026-02-24
*   **Decision:** 4階層モデル（Transport, Packet, Routing, Negotiation）へのリファクタリング。
*   **Decision:** 依存性の注入（DI）に近い形でコンポーネントを分離し、テスタビリティを向上。

#### 3. AIとの協調に関する指針 (AI Collaboration Policy)
*   **自律的読み込みの推奨:** AI は `[SYSTEM]` 通知を受け取った際、自律的に `read_file` を実行し、コンテキストを同期する義務を負う。
*   **アトミックな通信:** タグの開始から終了までは一つのトランザクションとし、ネスト（入れ子）を禁止する。

#### 4. コンポーネント設計仕様 (Component Design Specifications)

### 4.1. Transport Layer (`MessageBus`)
- **責務:** 物理的なメッセージの送受信。PIDベースのシグナル通知。
- **実装:** `FSBus` (ファイルシステム)。

### 4.2. Packet Layer (`ProtocolStack`)
- **責務:** テキストストリームからのタグ抽出。ANSI/Thinkingブロック除去。
- **データ構造:** `Packet` dataclass。

### 4.3. Routing/Negotiation Layer (`NegotiationManager`)
- **責務:** 交渉相手（Partner）の管理。エコーバックによる無限ループ防止。

### 4.4. Orchestrator (`BridgeCore`)
- **責務:** PTY制御、信号処理、各レイヤーの統合。
- **アルゴリズム:** 非ブロッキング `select.select()` による多重化。

### 4.5. Bootstrapper
- **責務:** 起動時の `DESIGN_PHILOSOPHY.md` リンク作成および初期化プロンプト注入。
