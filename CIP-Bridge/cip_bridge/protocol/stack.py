import hashlib
import time
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple
from ..utils.text_utils import extract_tag_content, strip_ansi, remove_thinking_block, remove_ui_noise

# @intent:responsibility 通信の最小単位であるパケットを定義するデータ構造。
@dataclass
class Packet:
    type: str
    content: str
    target_id: Optional[str] = None
    sender_id: Optional[str] = None

# @intent:responsibility テキストストリームから CIP 固有の XML タグを抽出し、
#                         ノイズ除去や Thinking ブロックのフィルタリングを行う。
# @intent:constraint [ARCHITECTURE_MANIFEST] に基づき、正規表現 (re) の使用を禁止する。
class ProtocolStack:
    """メッセージのパース、シリアライズ、フィルタリングを担当するレイヤー。"""
    
    def __init__(self, my_id: str):
        self.my_id = my_id

    def _log(self, msg: str):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open("bridge_events.log", "a") as f:
                f.write(f"[{timestamp}] [DEBUG:ProtocolStack] {msg}\n")
        except: pass

    def preprocess_text(self, raw_text: str) -> str:
        """生テキストからANSIコード、UIノイズを除去し、最後にThinkingブロックを削除する。"""
        text = strip_ansi(raw_text)
        text = remove_ui_noise(text)
        text = remove_thinking_block(text)
        return text

    # @intent:responsibility 自分のIDに基づき、自己署名プロトコル（自分の発言のみを転送対象とする）
    #                         に従ってタグ付きメッセージをパースする。
    def parse(self, raw_text: str) -> List[Packet]:
        """テキストからCIPプロトコルのタグを抽出し、Packetオブジェクトのリストを返す。"""
        clean_text = self.preprocess_text(raw_text)
        packets = []
        last_end_idx = 0

        tags = ["NEED_CONSENSUS", "ACCEPTED", "CONFLICT"]

        # 1. タグの抽出 (文字列検索)
        candidates = []
        for tag in tags:
            start_tag = f"[{tag}]"
            end_tag = f"[/{tag}]"
            
            search_pos = 0
            while True:
                start_idx = clean_text.find(start_tag, search_pos)
                if start_idx == -1: break
                
                end_idx = clean_text.find(end_tag, start_idx + len(start_tag))
                if end_idx == -1: break
                
                full_block_end = end_idx + len(end_tag)
                candidates.append((start_idx, full_block_end, tag))
                search_pos = full_block_end

        candidates.sort()

        for start_idx, end_idx, tag in candidates:
            if start_idx < last_end_idx:
                continue

            block = clean_text[start_idx:end_idx]
            
            # エコー回避: [FROM: @...] が含まれているブロックは他者のエコー。
            # ただし、自分のIDが署名されている場合は、自分が再出力したものなので許可する。
            if "[FROM: @" in block:
                my_signature = f"[FROM: @{self.my_id}]"
                if my_signature not in block:
                    self._log(f"Skipping ECHO tag: {tag} (found other signature)")
                    last_end_idx = end_idx
                    continue

            # 宛先IDの抽出
            target_id = None
            start_tag = f"[{tag}]"
            end_tag = f"[/{tag}]"
            content_inside = block[len(start_tag):-len(end_tag)].lstrip()
            if content_inside.startswith("@"):
                id_end = 1
                while id_end < len(content_inside):
                    c = content_inside[id_end]
                    if c.isalnum() or c == "_" or c == "-":
                        id_end += 1
                    else:
                        break
                extracted_id = content_inside[1:id_end]
                if extracted_id != self.my_id:
                    target_id = extracted_id
            
            packets.append(Packet(
                type=tag,
                content=block,
                target_id=target_id,
                sender_id=self.my_id
            ))
            last_end_idx = end_idx

        return packets

    def serialize(self, packet: Packet) -> str:
        """Packetオブジェクトを送信用のテキスト形式に変換する。"""
        return packet.content
