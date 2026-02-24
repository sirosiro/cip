from typing import Optional
from ..protocol.stack import Packet

# @intent:responsibility 交渉相手の状態（Partner）を管理し、エコーバックによる無限ループ
#                         （同じタイプのメッセージの連続転送）を防止する。
class NegotiationManager:
    """
    交渉の状態管理とパケットのルーティングを担当する。
    """
    
    def __init__(self, my_id: str):
        self.my_id = my_id
        self.current_partner: Optional[str] = None
        self.last_received_type: Optional[str] = None  # 無限ループ防止用
        self.last_sent_content: Optional[str] = None

    def set_partner(self, partner_id: str):
        self.current_partner = partner_id

    def get_partner(self) -> Optional[str]:
        return self.current_partner

    # @intent:responsibility 受信メッセージのタイプを記憶し、転送判定に利用する。
    def update_state(self, packet: Packet):
        """
        パケットの種類に基づいて内部状態を更新する。
        """
        if packet.type == "NEED_CONSENSUS":
            self.last_received_type = "NEED_CONSENSUS"
            if packet.target_id:
                self.set_partner(packet.target_id)
        elif packet.type == "ACCEPTED":
            self.last_received_type = "ACCEPTED"
        elif packet.type == "CONFLICT":
            self.last_received_type = "CONFLICT"

    # @intent:responsibility エコーバック（受信した ACCEPTED をそのまま相手に返すなど）
    #                         を検知して転送をブロックする。
    def should_route(self, packet: Packet) -> bool:
        """
        このパケットを転送すべきかどうかを判断する。
        （無限ループ防止ロジックなど）
        """
        if packet.type == "ACCEPTED" and self.last_received_type == "ACCEPTED":
            return False
            
        return True

    # @intent:responsibility パケットタイプに応じて、保存されている交渉相手または
    #                         指定されたターゲットへのルーティング先を決定する。
    def get_route(self, packet: Packet) -> Optional[str]:
        """
        パケットの送信先IDを決定する。
        """
        if packet.type == "NEED_CONSENSUS":
            return packet.target_id
        
        elif packet.type in ("ACCEPTED", "CONFLICT"):
            return self.current_partner
            
        return None
