from dataclasses import dataclass
from typing import List, Optional
from ..utils.text_utils import extract_tag_content, strip_ansi, remove_thinking_block, remove_ui_noise

# @intent:responsibility 通信の最小単位であるパケットを定義するデータ構造。
@dataclass
class Packet:
    type: str  # NEED_CONSENSUS, ACCEPTED, CONFLICT, SYSTEM
    content: str
    target_id: Optional[str] = None
    sender_id: Optional[str] = None

# @intent:responsibility テキストストリームから CIP 固有の XML タグを抽出し、
#                         ノイズ除去や Thinking ブロックのフィルタリングを行う。
class ProtocolStack:
    """
    メッセージのパース、シリアライズ、フィルタリングを担当するレイヤー。
    """
    
    def __init__(self, my_id: str):
        self.my_id = my_id

    def preprocess_text(self, raw_text: str) -> str:
        """
        生テキストからANSIコード、Thinkingブロック、UIノイズを除去する。
        """
        text = strip_ansi(raw_text)
        text = remove_thinking_block(text)
        text = remove_ui_noise(text)
        return text

    # @intent:responsibility 自分のIDに基づき、自己署名プロトコル（自分の発言のみを転送対象とする）
    #                         に従ってタグ付きメッセージをパースする。
    def parse(self, raw_text: str) -> List[Packet]:
        """
        テキストからCIPプロトコルのタグを抽出し、Packetオブジェクトのリストを返す。
        """
        clean_text = self.preprocess_text(raw_text)
        packets = []

        # 1. NEED_CONSENSUS の抽出
        consensus_block, _ = extract_tag_content(clean_text, "[NEED_CONSENSUS]", "[/NEED_CONSENSUS]")
        if consensus_block:
            target_id = None
            lines = consensus_block.splitlines()
            if lines and "@" in lines[0]:
                try:
                    at_idx = lines[0].index("@")
                    target_part = lines[0][at_idx+1:].strip()
                    target_id = target_part.split()[0]
                except ValueError: pass
            
            # 自己署名チェック
            if "[FROM: @" not in consensus_block or f"[FROM: @{self.my_id}]" in consensus_block:
                packets.append(Packet(
                    type="NEED_CONSENSUS",
                    content=consensus_block,
                    target_id=target_id,
                    sender_id=self.my_id
                ))

        # 2. ACCEPTED の抽出
        accepted_block, _ = extract_tag_content(clean_text, "[ACCEPTED]", "[/ACCEPTED]")
        if accepted_block:
            if "[FROM: @" not in accepted_block or f"[FROM: @{self.my_id}]" in accepted_block:
                packets.append(Packet(
                    type="ACCEPTED",
                    content=accepted_block,
                    sender_id=self.my_id
                ))

        # 3. CONFLICT の抽出
        conflict_block, _ = extract_tag_content(clean_text, "[CONFLICT]", "[/CONFLICT]")
        if conflict_block:
             if "[FROM: @" not in conflict_block or f"[FROM: @{self.my_id}]" in conflict_block:
                packets.append(Packet(
                    type="CONFLICT",
                    content=conflict_block,
                    sender_id=self.my_id
                ))

        return packets

    def serialize(self, packet: Packet) -> str:
        """
        Packetオブジェクトを送信用のテキスト形式に変換する。
        """
        return packet.content
