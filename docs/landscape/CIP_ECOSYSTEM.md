# CIP Ecosystem & Landscape

CIP (Core-Intent Prompting) は、2026年の多様化するAIツール群において、それらに**「何を作るべきか（What）」と「なぜそうするのか（Why）」を教え、統率するための「司令塔」**の位置にあります。
ツールが進化すればするほど、それらを指揮するCIPのような「意図の定義能力」の価値が高まると考えられます。

本ドキュメントは、CIPを「思考のOS」として位置づけ、他のAIツールとの関係性や役割分担を定義した「エコシステム・マップ」です。

## 知性の階層構造 (Hierarchy of Intelligence)

各ツールの特性を分析し、CIPとの関係性を以下のような階層グラフとして整理しました。

```text
▲ [ 上位概念: 思考のOS / 脳 ] 
│   
│    【 CIP (Core-Intent Prompting) 】
│    ・役割: 意図の構造化、哲学の定義、生きているマニフェスト
│    ・成果物: DESIGN_PHILOSOPHY.md / ARCHITECTURE_MANIFEST.md
│    ・キーワード: Intent (意図), Why (なぜ), Soul (魂)
│
│            │  ↓ 意図の注入 (Injection)
│            │  ↑ 知性の還流 (Feedback Loop)
│
▼ [ 中間レイヤー: 枠組み / 工場 ]
│   
│    【 GitHub Spec-kit / Tessl / Dify 】
│    ・役割: 仕様の標準化、パイプライン管理、自動化フロー
│    ・関係性: CIPが「魂」を吹き込み、これらが「型」や「仕様」として固定する
│
│            │  ↓ 具体的な指示 (Prompt/Spec)
│            │  ↑ 実行結果・エラー報告
│
▼ [ 実行レイヤー: 手足 / エンジン / 神経系 ]
│
│    【 生成・編集能力 (Creation) 】
│      ├─ Cursor (Composer): 圧倒的な実行力・一括編集
│      ├─ Windsurf (Cascade): 文脈の深掘り・フロー
│      ├─ GitHub Copilot: 瞬発的な補完・戦術
│      └─ Vibe Coding系: 直感的なプロトタイピング
│
│    【 自律エージェント (Autonomy) 】
│      ├─ Claude (Code): 自律的な思考・実行エンジン
│      └─ AWS Kiro: インフラ操作・現場監督
```

---

## CIPの立ち位置と特徴（Why & What）

なぜCIPがこの「最上位」に位置するのか、その理由と特徴です。

### 1. 「ベクトル」ではなく「座標系」である
他のすべてのツールは、開発を加速させる「力（ベクトル）」を持っていますが、CIPはその力がどこへ向かうべきかを定義する「空間（座標系）」であると定義されています。
*   **理由:** CursorやClaudeは強力ですが、指示がなければ「動くがメンテナンス不能なコード」や「意図しない設計」を高速で生成してしまうリスクがあります。CIPはこの暴走を防ぐガードレール（憲法）として機能します。

### 2. AIに対する「OS（オペレーティングシステム）」としての役割
CIPは、AIを単なるチャットボットではなく、プロジェクトの文脈を完全に理解した「パートナー」に変えるための思考のOSです。
*   **特徴:**
    *   **意図の注入:** 抽象的な「設計思想（Philosophy）」をマニフェスト化し、ClaudeやWindsurfといったAIに読み込ませることで、AIの挙動を根本から制御します。
    *   **非依存性:** 特定のツールに依存しないため、AIモデルがClaudeから次世代のものに変わっても、CIPで定義した「設計の知性」は資産として残ります。

### 3. 「生きているマニフェスト」による知性の循環
CIPの最大の特徴は、トップダウンの命令だけでなく、ボトムアップの進化を含んでいる点です。これを「知性の還流（Feedback Loop）」と呼びます。
*   **プロセス:**
    1.  **設計:** CIPで理想を描く。
    2.  **実行:** CursorやKiroなどが実装し、現場の制約（バグやインフラの限界）を発見する。
    3.  **進化:** その発見をCIPのマニフェストに書き戻す（還流させる）。
*   **結果:** マニフェストは不変の石板ではなく、AIとの対話を通じて自己増殖・進化する「DNA」となります。

### 4. 他ツールとの「最強の相乗効果」
CIP単体で使うことよりも、各ツールの特性に合わせて組み合わせることが推奨されています。

---

## Detailed Comparisons (ツール別比較詳細)

各ツールとCIPの具体的な連携方法や使い分けについての詳細レポートです。

### Editor & Creation (実行レイヤー: エディタ・生成)
*   [**CIP vs Cursor (Composer)**](./CIP_vs_Cursor.md)  
    「実行の暴力」を持つComposerに、CIPで「哲学」を与える運用法。
*   [**CIP vs Windsurf (Cascade)**](./CIP_vs_Windsurf.md)  
    文脈を深掘りするCascadeに、CIPで「未来の文脈」を与える運用法。
*   [**CIP vs GitHub Copilot**](./CIP_vs_GitHub-Copilot.md)  
    高速な補完を行うCopilotに、CIPで「設計思想のガードレール」を敷く運用法。

### Agent & Infrastructure (実行レイヤー: 自律エージェント・インフラ)
*   [**CIP vs Claude (Code/Sonnet)**](./CIP_vs_Claude.md)  
    最強の知能Claudeを、CIPで「デジタルの分身」へと進化させる運用法。
*   [**CIP vs AWS Q Developer (Kiro)**](./CIP_vs_AWS-Kiro.md)  
    AWSの現場監督Kiroに、CIPで「ビジネスの魂」を注入する運用法。

### Spec & Management (中間レイヤー: 仕様・管理)
*   [**CIP vs GitHub Spec-kit**](./CIP_vs_HitHub-SpecKit.md)  
    Spec-kitという「パイプライン」に、CIPという「思考のOS」を載せる運用法。
*   [**CIP vs Tessl**](./CIP_vs_Tessl.md)  
    仕様駆動のTesslに、CIPで「進化する仕様」を与える運用法。

### Others (その他)
*   [**CIP vs Others**](./CIP_vs_Others.md)  
    Vibe Coding系、ローカルエージェント、Difyなど、その他の最新ツールとの比較。

