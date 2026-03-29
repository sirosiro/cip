from typing import Optional, List
from enum import Enum
from ..protocol.stack import Packet
import hashlib

# @intent:responsibility 交渉相手の状態（Partner）を管理し、エコーバックによる無限ループ
#                         （同じタイプのメッセージの連続転送）を防止する。
# @intent:responsibility 交渉の状態管理と自律モード (AUTO) の制御を行う。
# @intent:constraint [ARCHITECTURE_MANIFEST] に基づき、正規表現 (re) の使用を禁止する。

class BridgeState(Enum):
    BYPASS = "BYPASS"
    AUTO = "AUTO"

class NegotiationManager:
    """交渉の状態管理、パケットのルーティング、およびモード遷移を担当する。"""
    
    def __init__(self, my_id: str):
        self.my_id = my_id
        self.mode = BridgeState.BYPASS
        self.current_partner: Optional[str] = None
        self.last_received_type: Optional[str] = None
        self.last_sent_type: Optional[str] = None
        self.sent_content_hashes: List[str] = [] # 重複排除のための送信済みハッシュ履歴
        
        # 自律交渉の設定
        self.negotiation_count = 0
        self.max_negotiations = 3

    def set_mode(self, mode: BridgeState):
        self.mode = mode
        if mode == BridgeState.AUTO:
            self.negotiation_count = 0
            self.reset_history()

    def set_partner(self, partner_id: str):
        self.current_partner = partner_id

    def get_partner(self) -> Optional[str]:
        return self.current_partner

    def _normalize(self, text: str) -> str:
        """意味のある文字（英数字・日本語）のみを抽出して正規化する"""
        chars = []
        for char in text:
            if char.isalnum() or '\u3040' <= char <= '\u9fff':
                chars.append(char)
        return "".join(chars)

    def reset_history(self):
        """送信済みコンテンツの履歴をリセットする。"""
        self.sent_content_hashes.clear()

    # @intent:responsibility 送信するパケットに基づいて内部状態を更新し、履歴に記録する。
    def update_state(self, packet: Packet):
        """自分がパケットを送信（転送）した直後に呼ばれ、状態を更新する。"""
        # @intent:rationale 自分が発信した内容を「過去の送信履歴」としてハッシュ管理することで、
        #                   バッファの再送による不要な重複送信を防止する。
        self.last_sent_type = packet.type
        # last_received_type は受信時のみ更新されるべきなので、ここでは触らない

        # @intent:rationale 新しいリクエスト（または権威ある指示）を開始する場合は、
        #                   以前のトランザクションの履歴をクリアし、応答を許可する。
        #                   AUTOモードでは交渉カウンタをインクリメントする。
        if packet.type in ("NEED_CONSENSUS", "SYSTEM"):
            self.reset_history()
            if self.mode == BridgeState.AUTO:
                self.negotiation_count += 1
        
        # 終了タグが送信されたら BYPASS モードに戻る
        if packet.type in ("COMPLETED", "FAILED"):
            self.set_mode(BridgeState.BYPASS)
        
        # 正規化したコンテンツのハッシュを履歴に追加
        normalized = self._normalize(packet.content)
        if normalized:
            h = hashlib.sha256(normalized.encode('utf-8')).hexdigest()
            if h not in self.sent_content_hashes:
                self.sent_content_hashes.append(h)
            if len(self.sent_content_hashes) > 100:
                self.sent_content_hashes.pop(0)

        if packet.type in ("NEED_CONSENSUS", "SYSTEM") and packet.target_id:
            self.set_partner(packet.target_id)

    # @intent:responsibility 受信したメッセージのタイプを記録する。
    def record_receive(self, packet_type: str):
        self.last_received_type = packet_type
        # @intent:rationale 相手から新しいリクエストや権威ある指示が来た場合も、履歴をリセットして応答を許可する。
        if packet_type in ("NEED_CONSENSUS", "SYSTEM"):
            self.reset_history()

    # @intent:responsibility 無限ループおよび同一内容の再送を検知して転送をブロックする。
    def should_route(self, packet: Packet) -> bool:
        """このパケットを転送すべきかどうかを判断する。"""
        # 1. コンテンツベースの重複排除
        normalized = self._normalize(packet.content)
        if not normalized:
            return False
            
        h = hashlib.sha256(normalized.encode('utf-8')).hexdigest()
        if h in self.sent_content_hashes:
            # 同一トランザクション内での重複のみブロック
            return False

        # 2. 交渉プロトコル上の無限ループ防止 (ACCEPTED のエコーバック等)
        # @intent:rationale 相手から ACCEPTED をもらった直後に自分が自動的に ACCEPTED を出すのは
        #                   エコーバック（または意図しない連鎖）の可能性が高いためブロックする。
        if packet.type == "ACCEPTED" and self.last_received_type == "ACCEPTED":
            return False
            
        return True

    # @intent:responsibility パケットタイプに応じて、保存されている交渉相手または
    #                         指定されたターゲットへのルーティング先を決定する。
    def get_route(self, packet: Packet) -> Optional[str]:
        """パケットの送信先IDを決定する。"""
        # @intent:rationale COMPLETED, FAILED はブロードキャストまたは
        #                   特定の相手がいない終了宣言なので転送不要（Bridgeが検知して終了する）。
        if packet.type in ("COMPLETED", "FAILED"):
            return None

        if packet.type in ("NEED_CONSENSUS", "SYSTEM"):
            return packet.target_id
        
        elif packet.type in ("ACCEPTED", "CONFLICT"):
            return packet.target_id or self.current_partner
            
        return None
