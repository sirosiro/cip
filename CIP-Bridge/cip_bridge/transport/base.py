from abc import ABC, abstractmethod
from typing import Optional

class MessageBus(ABC):
    """
    CIP-Bridgeの通信基盤となる抽象クラス。
    物理層(ファイルシステム、Redis、Networkなど)を隠蔽する。
    """
    
    def __init__(self, bus_id: str):
        self.bus_id = bus_id

    @abstractmethod
    def setup(self):
        """
        バスの初期化処理（ディレクトリ作成、PID記録など）を行う。
        """
        pass

    @abstractmethod
    def send(self, target_id: str, content: str) -> bool:
        """
        指定されたターゲットにメッセージを送信する。
        成功したら True を返す。
        """
        pass

    @abstractmethod
    def receive(self) -> Optional[str]:
        """
        自分宛てのメッセージを取得する。
        メッセージがない場合は None を返す。
        """
        pass

    @abstractmethod
    def notify(self, target_id: str):
        """
        ターゲットに対して「新着メッセージあり」のシグナルを送る。
        """
        pass
    
    @abstractmethod
    def cleanup(self):
        """
        終了時のクリーンアップ処理。
        """
        pass
