# AI協調開発フレームワーク (AI Collaborative Development Framework)

本プロジェクトは、人間とAIが「設計意図（Intent）」を核に協力し、高品質で持続可能なソフトウェアを開発するためのフレームワークです。ここではこの手法を **Core-Intent Prompting (CIP)** と呼びます。

## コンセプト
単なるコード補完や生成ではなく、AIを「熟練のアーキテクト」としてパートナーにします。
プロジェクトの憲法となる `ARCHITECTURE_MANIFEST.md` を共同で設計・運用し、「なぜその設計にしたのか」という意図を共有し続けることで、長期的な保守性と一貫性を保証します。

## Background: なぜ生まれたのか
本フレームワークは、AI開発における以下の課題を解決するために誕生しました。

### 1. "Context Drift" への対抗
LLMを用いた開発では、セッションが長くなるにつれてAIが初期の設計思想を忘れ、局所最適化された（しかし全体整合性を欠く）コードを生成し始める「Context Drift」が避けられません。常に「原点」となるコンテキストを注入し続ける仕組みが必要でした。

### 2. 静的解析と逆行工学の限界
既存の静的解析ツールを用いれば、ソースコードからUML（クラス図等）を生成することは可能です。しかし、そこから読み取れるのは「結果としての構造（Skeleton）」だけであり、**「なぜその構造を選んだのか（Soul/Intent）」**までは復元できません。
コードそのものではなく、コードになる前の「純粋な意図」を保存する場所が必要であるという結論に至りました。

---

## Phase 1: Methodology & Infrastructure (Current Status)
現在、本フレームワークの基盤となる手法と、それを支援するインフラストラクチャが確立されています。

* **構造化フォーマットの確立**
    `DESIGN_PHILOSOPHY.md` や `ARCHITECTURE_MANIFEST.md` を、AIが解釈しやすい「Core Prompt」として構造化して記述するフォーマットを定義しました。
* **意図駆動型ワークフロー (Intent-Driven Workflow)**
    コードを書く前に必ずこれらのマニフェストを更新・参照します。さらに、実装時にはAIがコードだけでなく、その背景にある意図を `// @intent:responsibility ...` といった**機械可読なタグ形式のインテント・コメント**として自律的に提案します。
* **AIアーキテクトとしての品質保証 (AI Architect Quality Assurance)**
    AIは単に動くコードを書くだけでなく、エラー時には安易な修正を行わず、**必ず「設計意図（マニフェスト）」に立ち返って根本原因を解決するプロトコル**を遵守します。
* **厳格な開発プロトコル (Strict Development Protocol)**
    アーキテクチャの変更を伴う実装において、AIはコードを書く前に必ずマニフェスト修正案を人間に提示し、承認を得ることを義務付けています。
* **フラクタル・アーキテクチャ (Fractal Placement)**
    大規模プロジェクトに対応するため、マニフェストをディレクトリ単位で再帰的に配置する手法を採用しています。
* **AI間自律通信基盤 (CIP-Bridge)**
    `gemini-cli` を拡張し、複数のAIエージェントが階層構造を持って自律的に協調作業を行うための通信インフラ (`CIP-Bridge`) を実装しました。これにより、人間が介在せずとも、上位ノード（Leader）が下位ノード（Worker）に指示を出し、設計思想を一貫させたまま実装を進めることが可能になります。

---

## Future Roadmap: 今後の進化
CIPは単なるドキュメントテンプレートではなく、開発プロトコルとして進化を続けます。

### Phase 2: Expansion (Near Future)
* **Linter for Intent**
    マニフェストの記述内容と、実際のコード（またはPR）との「意図の乖離」を検知する仕組みの検討。

### Phase 3: Automation & Ecosystem (Long Term)
* **自律的フィードバックループと承認の段階的委譲**
* **動的なマニフェスト進化**
* **CIP Standard**

---

## 実行環境について
本フレームワークは、特定のAIモデルやツールにハードに依存するものではありません。
十分な推論能力とコンテキスト長を持つLLM（Claude 3.5 Sonnet, GPT-4o, Gemini 1.5 Pro等）であれば、プロンプトを読み込ませることで利用可能です。

ただし、**gemini-cli** と **CIP-Bridge** を用いた環境を推奨しています。これにより、AIが自律的にマニフェストを読み込み、役割を認識し、他のAIと連携する高度なワークフローが可能になります。

## 使い方 (How to Use)

### 1. CIP-Bridge を使った自動ブートストラップ (推奨)
`gemini-cli` 環境であれば、`CIP-Bridge` を使用して手動コピーの手間を省けます。

```bash
# プロジェクトルートで実行（パスを通す）
export PATH="$PWD/CIP-Bridge:$PATH"

# 担当ディレクトリに移動して起動
cd your_project_module
bridge.py
```
AIが自動的に `DESIGN_PHILOSOPHY.md` を読み込み、`[READY]` 状態で起動します。

### 2. 手動ブートストラップ (汎用)
その他のチャットツールやIDEでは、以下の手順で利用します。

1.  **プロンプトの準備**: [DESIGN_PHILOSOPHY.md](./DESIGN_PHILOSOPHY.md) の全内容をコピーします。
2.  **AIの起動**: 任意のAIチャットツールを起動します。
3.  **ブートストラップ**: 最初のメッセージとして、コピーした内容を貼り付けて送信します。
4.  **協調作業の開始**: AIが内容を理解し、次のアクションを提案してくるので、指示に従って対話を進めてください。

## 主要ドキュメント
- [DESIGN_PHILOSOPHY.md](./DESIGN_PHILOSOPHY.md): 本フレームワークの根本思想であり、AIパートナーへのブートストラップ・プロンプトです。
- [CIP Ecosystem & Landscape](./docs/landscape/CIP_ECOSYSTEM.md): CIPと他のAIツール（Cursor, Windsurf, Claude, Tessl, Spec-kit等）との関係性や使い分けを定義したエコシステムマップ。
- [CIP-Bridge Architecture](./CIP-Bridge/ARCHITECTURE_MANIFEST.md): CIP-Bridge ツールの設計仕様書。

---

## License
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/deed.ja)

Copyright (c) 2026 Kouichi Shiroma
This work is licensed under a [Creative Commons Attribution 4.0 International License](https://creativecommons.org/licenses/by/4.0/).