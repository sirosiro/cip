import os
import sys
import pty
import tty
import select
import termios
import re
import signal
import fcntl
import struct
import time
from collections import deque

# @intent:responsibility [NEED_CONSENSUS] キーワードを検知し、自律モードへの移行と
#                         FS-Bus を介したメッセージ転送を制御する。
#                         また、ウィンドウサイズ変更を透過的に伝播させる。

class CIPBridge:
    def __init__(self, cmd=["gemini"], bus_id="leader"):
        # @intent:rationale デフォルトのコマンド名を gemini に修正。
        self.cmd = cmd
        self.bus_id = bus_id
        self.bus_dir = f"./cip_bus/{bus_id}"
        self.inbox_path = os.path.join(self.bus_dir, "inbox")
        self.pid_path = os.path.join(self.bus_dir, "bridge.pid")
        self.mode = "BYPASS" # BYPASS or AUTO
        self.master_fd = None
        self.old_tty = None
        # @intent:fix シグナルハンドラからの書き込みを非同期に行うためのキュー。
        self.write_queue = deque()
        self.pipe_r, self.pipe_w = os.pipe()

    def setup_bus(self):
        os.makedirs(self.bus_dir, exist_ok=True)
        with open(self.pid_path, "w") as f:
            f.write(str(os.getpid()))
        # inbox を空で作成
        open(self.inbox_path, "a").close()

    def handle_signal(self, signum, frame):
        # @intent:rationale SIGUSR1 を受信したら inbox を読み取り、キューに追加。
        if signum == signal.SIGUSR1:
            try:
                with open(self.inbox_path, "r") as f:
                    content = f.read().strip()
                if content:
                    # inbox をクリア
                    open(self.inbox_path, "w").close()
                    # @intent:fix 様々な改行シーケンスを試す。
                    # 1. プレーンなテキスト
                    self.write_queue.append(content.encode())
                    # 2. 短いウェイトを入れてから改行を送る（メインループ側で処理）
                    self.write_queue.append(b"\r")
                    self.write_queue.append(b"\n")
                    
                    # セルフパイプに書き込んで select を解除
                    os.write(self.pipe_w, b"x")
            except Exception as e:
                with open("bridge_errors.log", "a") as f:
                    f.write(f"Error in handle_signal: {e}\n")

    def set_winsize(self, fd, row, col, xpix=0, ypix=0):
        # @intent:responsibility PTY のウィンドウサイズを設定する。
        winsize = struct.pack("HHHH", row, col, xpix, ypix)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)

    def handle_winch(self, signum, frame):
        # @intent:responsibility SIGWINCH を受信したら親端末のサイズを取得し、子端末へ設定する。
        if self.master_fd:
            try:
                # 親端末（stdin）のサイズを取得
                winsize = fcntl.ioctl(sys.stdin.fileno(), termios.TIOCGWINSZ, b"\0" * 8)
                rows, cols, xpix, ypix = struct.unpack("HHHH", winsize)
                # 子端末へ設定
                self.set_winsize(self.master_fd, rows, cols, xpix, ypix)
            except Exception:
                pass

    def setup_philosophy_link(self):
        # @intent:responsibility See 4.4 Worker Manager in ARCHITECTURE_MANIFEST.md
        #                       (Philosophy Inheritance & Relative Symlink Creation)
        target_filename = "DESIGN_PHILOSOPHY.md"
        
        if os.path.exists(target_filename):
            return

        current_dir = os.path.abspath(".")
        parent_dir = os.path.dirname(current_dir)
        
        for _ in range(10): # Search up to 10 levels
            target_path = os.path.join(parent_dir, target_filename)
            if os.path.exists(target_path):
                rel_path = os.path.relpath(target_path, ".")
                try:
                    os.symlink(rel_path, target_filename)
                except OSError as e:
                    with open("bridge_errors.log", "a") as f:
                        f.write(f"Failed to create symlink: {e}\n")
                return
            
            if parent_dir == os.path.dirname(parent_dir): # Reached root
                break
            parent_dir = os.path.dirname(parent_dir)

    def inject_bootstrap_prompt(self):
        # @intent:responsibility See 4.4 Worker Manager in ARCHITECTURE_MANIFEST.md
        #                       (Autonomous Role Discovery Prompt Injection)
        prompt = """
[SYSTEM: Context Initialization]
あなたはCIPエコシステムのノードとして起動しました。
現在のカレントディレクトリ（担当領域）を確認し、以下の手順で自身の役割を自律的に決定してください。

1. **憲法の確認 (Global Philosophy):**
   ルートの設計思想が存在するか確認し、ロードしてください。
   `$ ls -l DESIGN_PHILOSOPHY.md` (シンボリックリンクなら `cat`, 実体なら `read_file`)

2. **法律の確認 (Local Manifest):**
   このディレクトリのアーキテクチャ定義（`ARCHITECTURE_MANIFEST.md`）をロードしてください。

3. **部下の確認 (Sub-Node Discovery):**
   さらに下位のディレクトリ（サブモジュール）が存在するか確認してください。
   もし存在すれば、あなたはそれらのリーダー（Local Leader）としての責務も負います。

全ての確認が完了したら、現在の役割（Worker / Local Leader / Root Leader）と準備完了の旨を `[READY]` と共に出力してください。
"""
        # Wait for gemini-cli initialization
        time.sleep(1.0)
        
        try:
            with open(self.inbox_path, "w") as f:
                f.write(prompt.strip())
            os.kill(os.getpid(), signal.SIGUSR1)
        except Exception as e:
             with open("bridge_errors.log", "a") as f:
                f.write(f"Failed to inject bootstrap prompt: {e}\n")

    def run(self):
        self.setup_bus()
        self.setup_philosophy_link()
        signal.signal(signal.SIGUSR1, self.handle_signal)
        signal.signal(signal.SIGWINCH, self.handle_winch)

        self.old_tty = termios.tcgetattr(sys.stdin)
        
        pid, self.master_fd = pty.fork()
        
        if pid == 0:
            try:
                os.execvp(self.cmd[0], self.cmd)
            except FileNotFoundError:
                print(f"\n[Error] Command '{self.cmd[0]}' not found.")
                sys.exit(1)
        
        try:
            tty.setraw(sys.stdin.fileno())
            
            # Initial window size
            self.handle_winch(None, None)

            # Inject bootstrap prompt
            self.inject_bootstrap_prompt()

            output_buffer = b""
            
            while True:
                # 監視対象に self.pipe_r (セルフパイプの読み込み側) を追加
                rfds, _, _ = select.select([sys.stdin, self.master_fd, self.pipe_r], [], [])
                
                # シグナルハンドラからの通知があった場合
                if self.pipe_r in rfds:
                    os.read(self.pipe_r, 1) # パイプを空にする
                    while self.write_queue:
                        data = self.write_queue.popleft()
                        os.write(self.master_fd, data)
                        # 各データの間に微小なディレイを入れて、確実に認識させる
                        time.sleep(0.05)

                if sys.stdin in rfds:
                    data = os.read(sys.stdin.fileno(), 1024)
                    if not data: break
                    os.write(self.master_fd, data)
                    
                if self.master_fd in rfds:
                    try:
                        data = os.read(self.master_fd, 1024)
                    except OSError: break
                    if not data: break
                    
                    # 出力をパススルー
                    os.write(sys.stdout.fileno(), data)
                    sys.stdout.flush()

                    # @intent:responsibility キーワード検知
                    output_buffer += data
                    if b"[NEED_CONSENSUS]" in output_buffer:
                        # 簡易的な検知ロジック
                        with open("bridge_events.log", "a") as f:
                            f.write("Detected [NEED_CONSENSUS]\n")
                        output_buffer = b"" # バッファをリセット

        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_tty)
            if self.master_fd:
                os.close(self.master_fd)
            os.close(self.pipe_r)
            os.close(self.pipe_w)
            print("\n[CIP-Bridge] Finished.")

def ensure_gitignore():
    """
    実行ディレクトリに .gitignore を作成または更新し、
    CIP-Bridge の一時ファイルが Git にコミットされないようにする。
    """
    ignore_file = ".gitignore"
    entries = {
        "cip_bus/",
        "bridge_events.log",
        "*.pid",
        "*.log",
        "__pycache__/"
    }
    
    current_content = set()
    if os.path.exists(ignore_file):
        with open(ignore_file, "r") as f:
            current_content = set(line.strip() for line in f if line.strip() and not line.startswith("#"))

    missing = entries - current_content
    
    if missing:
        try:
            with open(ignore_file, "a") as f:
                # ファイル末尾に改行がない場合の対策
                if os.path.exists(ignore_file) and os.path.getsize(ignore_file) > 0:
                     with open(ignore_file, "rb") as f_rb:
                         f_rb.seek(-1, 2)
                         if f_rb.read(1) != b"\n":
                             f.write("\n")
                
                f.write("\n# Auto-generated by CIP-Bridge\n")
                for entry in missing:
                    f.write(f"{entry}\n")
            # print(f"[CIP-Bridge] Updated .gitignore with: {', '.join(missing)}")
        except Exception as e:
            print(f"[CIP-Bridge] Warning: Failed to update .gitignore: {e}")

if __name__ == "__main__":
    ensure_gitignore()
    bridge = CIPBridge()
    bridge.run()