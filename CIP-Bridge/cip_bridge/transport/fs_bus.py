import os
import signal
import time
import shutil
from typing import Optional, List
from .base import MessageBus

# @intent:responsibility 共有ファイルシステム（NFS/SMB/Local）をメッセージバスとして利用し、
#                         ディレクトリベースのメッセージ交換とPIDベースのシグナル通知を実装する。
# @intent:constraint [ARCHITECTURE_MANIFEST] に基づき、正規表現 (re) の使用を禁止する。

class FSBus(MessageBus):
    """
    ファイルシステムベースの通信バス実装 (NFS/SMB対応)。
    cip_bus/ ディレクトリ以下のファイルを用いてメッセージ交換を行う。
    """
    def __init__(self, node_id: str, base_dir: str = "./cip_bus"):
        super().__init__(node_id) # Call base class init
        self.node_id = node_id
        self.bus_dir = os.path.abspath(base_dir)
        self.node_dir = os.path.join(self.bus_dir, self.node_id)
        self.inbox_dir = os.path.join(self.node_dir, "inbox")
        self.pid_path = os.path.join(self.node_dir, "bridge.pid")

    def _log(self, msg: str):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open("bridge_events.log", "a") as f:
                f.write(f"[{timestamp}] [DEBUG:FSBus:{self.node_id}] {msg}\n")
        except: pass

    # @intent:responsibility 下位ディレクトリから上位の cip_bus を発見し、リンクを作成することで
    #                         フラクタルな階層構造における通信路を自動確立する。
    def setup_symlink(self):
        # self.bus_dir is an absolute path, so we get its basename to link to
        target_dirname = os.path.basename(self.bus_dir) # typically "cip_bus"
        if os.path.exists(target_dirname): return

        current_dir = os.path.abspath(".")
        parent_dir = os.path.dirname(current_dir)
        
        found = False
        search_dir = parent_dir
        for _ in range(10):
            target_path = os.path.join(search_dir, target_dirname)
            if os.path.exists(target_path) and os.path.isdir(target_path):
                rel_path = os.path.relpath(target_path, ".")
                try:
                    os.symlink(rel_path, target_dirname)
                    self._log(f"Created symlink to {target_path}")
                except OSError: pass
                found = True
                break
            if search_dir == os.path.dirname(search_dir): break
            search_dir = os.path.dirname(search_dir)
        
        if not found and not os.path.exists(self.bus_dir):
             os.makedirs(self.bus_dir, exist_ok=True)

    def setup(self):
        """バスの初期化処理。ディレクトリを作成し、自身のPIDを記録する。"""
        self.setup_symlink()
        if not os.path.exists(self.bus_dir):
            os.makedirs(self.bus_dir)
        
        if os.path.exists(self.node_dir):
            # @intent:rationale 既存のPIDファイルがあれば二重起動チェック
            if os.path.exists(self.pid_path):
                try:
                    with open(self.pid_path, "r") as f:
                        old_pid = int(f.read().strip())
                    os.kill(old_pid, 0)
                    raise RuntimeError(f"CIP-Bridge is already running with PID {old_pid}.")
                except (ProcessLookupError, ValueError, OSError):
                    shutil.rmtree(self.node_dir)

        os.makedirs(self.inbox_dir, exist_ok=True)
        with open(self.pid_path, "w") as f:
            f.write(str(os.getpid()))
        self._log(f"Setup bus at {self.node_dir}")

    # @intent:responsibility メッセージを対象の inbox に書き込み、SIGUSR1 シグナルを送信することで通知する。
    def send(self, target_id: str, content: str) -> bool:
        """指定したノードの inbox にメッセージを書き込み、シグナルで通知する。"""
        target_dir = os.path.join(self.bus_dir, target_id)
        target_inbox = os.path.join(target_dir, "inbox")
        target_pid_path = os.path.join(target_dir, "bridge.pid")

        if not os.path.exists(target_pid_path):
            self._log(f"Error: Target @{target_id} not found at {target_pid_path}")
            return False

        try:
            with open(target_pid_path, "r") as f:
                target_pid = int(f.read().strip())
            os.kill(target_pid, 0)
        except (ProcessLookupError, ValueError, OSError):
            self._log(f"Error: Target @{target_id} (PID {target_pid}) is not running.")
            return False

        # タイムスタンプベースのファイル名でメッセージを作成
        filename = f"{int(time.time()*1000)}_{self.node_id}.msg"
        msg_path = os.path.join(target_inbox, filename)
        
        try:
            with open(msg_path, "w") as f:
                f.write(f"[FROM: @{self.node_id}]\n{content}")
            
            # 相手にシグナル通知
            self.notify(target_id, pid=target_pid)
            return True
        except Exception as e:
            self._log(f"Failed to send message to @{target_id}: {e}")
            return False

    # @intent:responsibility 自分の inbox を読み込み、内容をクリアしてアトミックに取得する。
    def receive(self) -> Optional[str]:
        """自身の inbox からメッセージを1つ取得し、処理後に削除する。"""
        if not os.path.exists(self.inbox_dir):
            return None

        files = sorted(os.listdir(self.inbox_dir))
        if not files:
            return None

        msg_file = files[0]
        msg_path = os.path.join(self.inbox_dir, msg_file)
        
        try:
            with open(msg_path, "r") as f:
                content = f.read()
            os.remove(msg_path)
            return content
        except Exception as e:
            self._log(f"Failed to receive message: {e}")
            return None

    def notify(self, target_id: str, pid: int = None):
        """対象プロセスに SIGUSR1 を送信して通知する。"""
        if pid is None:
            target_pid_path = os.path.join(self.bus_dir, target_id, "bridge.pid")
            try:
                with open(target_pid_path, "r") as f:
                    pid = int(f.read().strip())
            except: return

        try:
            os.kill(pid, signal.SIGUSR1)
        except OSError:
            self._log(f"Target process {pid} not found for notification.")

    def get_active_workers(self) -> List[str]:
        """現在稼働中の他のAIノード（Worker）のリストを取得する。"""
        workers = []
        if not os.path.exists(self.bus_dir):
            return workers

        for entry in os.listdir(self.bus_dir):
            if entry == self.node_id:
                continue
                
            entry_dir = os.path.join(self.bus_dir, entry)
            if not os.path.isdir(entry_dir):
                continue
                
            pid_path = os.path.join(entry_dir, "bridge.pid")
            if os.path.exists(pid_path):
                try:
                    with open(pid_path, "r") as f:
                        pid = int(f.read().strip())
                    os.kill(pid, 0) # プロセスの生存確認
                    workers.append(f"@{entry}")
                except (ProcessLookupError, ValueError, OSError):
                    continue
        return workers

    def cleanup(self):
        """終了処理。自身のノードディレクトリを削除する。"""
        if os.path.exists(self.node_dir):
            try:
                shutil.rmtree(self.node_dir)
            except: pass