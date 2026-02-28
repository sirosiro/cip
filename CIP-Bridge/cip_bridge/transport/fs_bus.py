import os
import signal
import time
from typing import Optional

from .base import MessageBus

# @intent:responsibility 共有ファイルシステム（NFS/SMB/Local）をメッセージバスとして利用し、
#                         ディレクトリベースのメッセージ交換とPIDベースのシグナル通知を実装する。
class FSBus(MessageBus):
    """
    ファイルシステムベースの通信バス実装 (NFS/SMB対応)。
    cip_bus/ ディレクトリ以下のファイルを用いてメッセージ交換を行う。
    """
    
    def __init__(self, bus_id: str, base_dir: str = "./cip_bus", logger=None):
        super().__init__(bus_id)
        self.base_dir = base_dir
        self.bus_dir = os.path.join(self.base_dir, self.bus_id)
        self.inbox_path = os.path.join(self.bus_dir, "inbox")
        self.pid_path = os.path.join(self.bus_dir, "bridge.pid")
        self.logger = logger

    def _log(self, msg: str):
        if self.logger:
            self.logger(msg)
        else:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            try:
                with open("bridge_events.log", "a") as f:
                    f.write(f"[{timestamp}] [FSBus:{self.bus_id}] {msg}\n")
            except Exception: pass

    # @intent:responsibility 下位ディレクトリから上位の cip_bus を発見し、リンクを作成することで
    #                         フラクタルな階層構造における通信路を自動確立する。
    def setup_symlink(self):
        target_dirname = os.path.basename(self.base_dir) # "cip_bus"
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
        
        if not found and not os.path.exists(self.base_dir):
             os.makedirs(self.base_dir, exist_ok=True)

    def setup(self):
        self.setup_symlink()
        os.makedirs(self.bus_dir, exist_ok=True)
        
        if os.path.exists(self.pid_path):
            try:
                with open(self.pid_path, "r") as f:
                    old_pid = int(f.read().strip())
                os.kill(old_pid, 0)
                raise RuntimeError(f"CIP-Bridge is already running with PID {old_pid}.")
            except (ProcessLookupError, ValueError, FileNotFoundError):
                pass
            except Exception as e:
                raise e

        with open(self.pid_path, "w") as f:
            f.write(str(os.getpid()))
            f.flush()
            os.fsync(f.fileno())
        
        if not os.path.exists(self.inbox_path):
            with open(self.inbox_path, "w") as f:
                pass 
        
        self._log("Bus setup completed.")

    # @intent:responsibility メッセージを対象の inbox に書き込み、SIGUSR1 シグナルを送信することで通知する。
    def send(self, target_id: str, content: str) -> bool:
        target_dir = os.path.join(self.base_dir, target_id)
        target_pid_path = os.path.join(target_dir, "bridge.pid")
        target_inbox_path = os.path.join(target_dir, "inbox")

        if not os.path.exists(target_pid_path):
            self._log(f"Error: Target @{target_id} not found at {target_pid_path}")
            return False

        try:
            with open(target_pid_path, "r") as f:
                target_pid = int(f.read().strip())
            os.kill(target_pid, 0)
            
            with open(target_inbox_path, "a") as f:
                f.write(f"\n[FROM: @{self.bus_id}]\n{content.strip()}\n")
                f.flush()
                os.fsync(f.fileno())
            
            self.notify(target_id, pid=target_pid)
            return True
            
        except Exception as e:
            self._log(f"Send error to @{target_id}: {e}")
            return False

    def notify(self, target_id: str, pid: int = None):
        if pid is None:
            target_dir = os.path.join(self.base_dir, target_id)
            target_pid_path = os.path.join(target_dir, "bridge.pid")
            try:
                with open(target_pid_path, "r") as f:
                    pid = int(f.read().strip())
            except Exception:
                return

        try:
            os.kill(pid, signal.SIGUSR1)
        except ProcessLookupError:
            self._log(f"Target process {pid} not found for notification.")

    # @intent:responsibility 自分の inbox を読み込み、内容をクリアしてアトミックに取得する。
    def receive(self) -> Optional[str]:
        try:
            if not os.path.exists(self.inbox_path):
                return None

            content = ""
            with open(self.inbox_path, "r+") as f:
                content = f.read().strip()
                if content:
                    f.seek(0)
                    f.truncate()
                    f.flush()
                    os.fsync(f.fileno())
            
            return content if content else None

        except Exception as e:
            self._log(f"Receive error: {e}")
            return None

    def cleanup(self):
        pass
