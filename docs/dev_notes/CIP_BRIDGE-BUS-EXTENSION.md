# CIP-Bridge 修正補足案: 疎結合型分散バス・アーキテクチャ

## 1. 概要
本提案は、CIP-Bridge における通信基盤を「データ搬送（Bus）」と「実行通知（Signal）」に分離し、それらを抽象化することで、ローカル、LAN（NFS/SMB）、クラウドといった異なる環境において柔軟な切り替えを可能にするものである。

## 2. 通信プロトコルの分離設計（疎結合化）

### 2.1 データ搬送レイヤー (Data Bus)
実体となるプロンプト、コンテキスト、および生成結果を保持する役割。
- **FS-bus (NFS/SMB)**: 共有フォルダ上のファイル（JSON/YAML/Markdown）
- **Web-bus**: REST API, S3, または Redis 等の KVS
- **Memory-bus**: 同一マシン内での共有メモリ

### 2.2 実行通知レイヤー (Signal)
相手ノードに対し、データ準備完了や割り込みを伝えるトリガーの役割。
- **POSIX Signal (SIGUSR1)**: SSH 経由の `kill` 命令による低遅延通知
- **Polling**: ファイル出現を監視（fswatch / inotify）
- **WebHook**: HTTP リクエストによる通知



## 3. 導入のメリット（なぜこの構成か）

本アーキテクチャを採用することで、以下の利点が得られる。

1. **環境の柔軟性 (Environmental Flexibility)**
   - 自宅では高速な NFS、外出先ではクラウド経由、同一マシン内では共有メモリといった具合に、CIP 本体のロジックを書き換えずに「プラグイン」感覚で通信手段を切り替えられる。
2. **システム負荷の最小化 (Low Overhead)**
   - 受信側の PC が常にファイルを監視（ポーリング）する必要がなく、OS レベルの割り込み（Signal）を待機するだけで済むため、CPU 負荷とバッテリー消費を抑えられる。
3. **Mac システムのクリーン維持 (Zero Pollution)**
   - 特別な常駐ソフトやミドルウェア（Redis 等）をインストールせずとも、Mac 標準の `ssh` と `kill` だけですぐに分散環境が構築できる。
4. **デバッグの容易性 (Debuggability)**
   - FS-bus を使用している場合、通信の中身がただのファイルとして残るため、特別なツールなしでエディタから通信内容や履歴を直接確認・修正できる。
5. **段階的なスケールアップ (Scalability)**
   - 最初は 1 台の MacBook 内の別プロセス間通信から始め、必要に応じて LAN 内の複数台、さらには Web 経由の広域分散へとシームレスに拡張できる。

## 4. 推奨構成：NFS + SIGUSR1 (LAN分散モード)

### ノード管理 (node_reg)
各ノードは起動時、共有フォルダの `nodes/` 配下に自身の情報を書き込む。
- ファイルパス: `/shared/bus/nodes/[hostname].addr`
- 内容: `[IP_ADDRESS] [PID]`

### 実行フロー
1. **送信側**: ペイロード（プロンプト等）を `/shared/bus/payloads/[target].json` に書き込む。
2. **送信側**: 対象の `.addr` ファイルから IP と PID を取得。
3. **送信側**: `ssh [user]@[IP] "kill -SIGUSR1 [PID]"` を実行。
4. **受信側**: `SIGUSR1` トラップにより即座にファイルを読み込み、Gemini-CLI を実行。

## 5. 実装インターフェース案 (CIP-Bridge 抽象クラス)

```python
class CIPBridge:
    def __init__(self, bus_type='fs', signal_type='sigusr1'):
        self.bus = self._init_bus(bus_type)
        self.signal = self._init_signal(signal_type)

    def dispatch(self, payload, target_node):
        # 1. データの配置
        self.bus.write(payload, target_node)
        # 2. 実行通知の送信
        self.signal.notify(target_node)

    def listen(self, callback):
        # シグナル待機またはポーリングを開始
        self.signal.wait(on_receive=callback)
