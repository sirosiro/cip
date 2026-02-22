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
import platform
import shutil
from collections import deque

# OSに応じた改行コード（Enterキー）の定義
if platform.system() == "Windows":
    ENTER_KEY = b"\r\n"
else:
    ENTER_KEY = b"\r"

# @intent:responsibility [NEED_CONSENSUS] キーワードを検知し、自律モードへの移行と
#                         FS-Bus を介したメッセージ転送を制御する。
#                         また、ウィンドウサイズ変更を透過的に伝播させる。

class CIPBridge:
    def _find_gemini_command(self):
        env_cmd = os.environ.get("CIP_BRIDGE_CMD")
        if env_cmd: return [env_cmd]
        path_cmd = shutil.which("gemini")
        if path_cmd: return [path_cmd]
        common_paths = [
            os.path.expanduser("~/.volta/bin/gemini"),
            os.path.expanduser("~/.npm-global/bin/gemini"),
            "/usr/local/bin/gemini",
            "/opt/homebrew/bin/gemini"
        ]
        for p in common_paths:
            if os.path.exists(p) and os.access(p, os.X_OK):
                return [p]
        return ["gemini"]

    def __init__(self, cmd=None, bus_id=None):
        self.cmd = cmd if cmd else self._find_gemini_command()
        self.bus_id = bus_id if bus_id else os.path.basename(os.getcwd())
        self.bus_dir = f"./cip_bus/{self.bus_id}"
        self.inbox_path = os.path.join(self.bus_dir, "inbox")
        self.pid_path = os.path.join(self.bus_dir, "bridge.pid")
        
        # @intent:fix Pull型通信用のメッセージ閲覧ファイル
        self.current_message_path = "current_message.md"
        
        self.mode = "BYPASS"
        self.master_fd = None
        self.old_tty = None
        
        self.pipe_r, self.pipe_w = os.pipe()
        fcntl.fcntl(self.pipe_r, fcntl.F_SETFL, os.O_NONBLOCK)
        fcntl.fcntl(self.pipe_w, fcntl.F_SETFL, os.O_NONBLOCK)

        self.current_negotiation_partner = None

    def log_event(self, msg):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open("bridge_events.log", "a") as f:
                f.write(f"[{timestamp}] [{self.bus_id}] {msg}\n")
                f.flush()
                os.fsync(f.fileno())
        except Exception: pass

    def setup_cip_bus_link(self):
        target_dirname = "cip_bus"
        if os.path.exists(target_dirname): return
        current_dir = os.path.abspath(".")
        parent_dir = os.path.dirname(current_dir)
        for _ in range(10):
            target_path = os.path.join(parent_dir, target_dirname)
            if os.path.exists(target_path) and os.path.isdir(target_path):
                rel_path = os.path.relpath(target_path, ".")
                try:
                    os.symlink(rel_path, target_dirname)
                    self.log_event(f"Created symlink to {target_path}")
                except OSError: pass
                return
            if parent_dir == os.path.dirname(parent_dir): break
            parent_dir = os.path.dirname(parent_dir)

    def setup_bus(self):
        self.setup_cip_bus_link()
        os.makedirs(self.bus_dir, exist_ok=True)
        if os.path.exists(self.pid_path):
            try:
                with open(self.pid_path, "r") as f:
                    old_pid = int(f.read().strip())
                os.kill(old_pid, 0)
                print(f"[Error] CIP-Bridge is already running with PID {old_pid}.")
                sys.exit(1)
            except (ProcessLookupError, ValueError, FileNotFoundError): pass
            except Exception as e:
                print(f"[Error] Checking PID file: {e}")
                sys.exit(1)
        with open(self.pid_path, "w") as f:
            f.write(str(os.getpid()))
            f.flush()
            os.fsync(f.fileno())
        
        with open(self.inbox_path, "w") as f:
            pass 

        self.log_event("Bus setup completed.")

    def handle_signal(self, signum, frame):
        if signum == signal.SIGUSR1:
            try:
                os.write(self.pipe_w, b"x")
            except Exception: pass

    def process_inbox(self):
        try:
            with open(self.inbox_path, "r+") as f:
                content = f.read().strip()
                if content:
                    f.seek(0)
                    f.truncate()
                    f.flush()
                    os.fsync(f.fileno())
                    
                    self.log_event(f"Processing inbox message (len: {len(content)})")

                    with open(self.current_message_path, "w") as cf:
                        cf.write(content)
                        cf.flush()
                        os.fsync(cf.fileno())

                    if "[FROM: @" in content:
                        try:
                            start_tag = "[FROM: @"
                            start_idx = content.index(start_tag) + len(start_tag)
                            end_idx = content.index("]", start_idx)
                            self.current_negotiation_partner = content[start_idx:end_idx]
                            self.log_event(f"Set negotiation partner to @{self.current_negotiation_partner}")
                        except ValueError: pass

                    # 通知メッセージを強調。AIが確実にコマンドを実行するように誘導する。
                    notification = f"\n\n[SYSTEM] 新着メッセージがあります。内容を確認するため、以下のコマンドを実行してください。\n\nread_file {self.current_message_path}\n"
                    os.write(self.master_fd, notification.encode())
                    time.sleep(0.1)
                    os.write(self.master_fd, ENTER_KEY)
                    
        except Exception as e:
            self.log_event(f"Error processing inbox: {e}")

    def set_winsize(self, fd, row, col, xpix=0, ypix=0):
        winsize = struct.pack("HHHH", row, col, xpix, ypix)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)

    def handle_winch(self, signum, frame):
        if self.master_fd:
            try:
                winsize = fcntl.ioctl(sys.stdin.fileno(), termios.TIOCGWINSZ, b"\0" * 8)
                rows, cols, xpix, ypix = struct.unpack("HHHH", winsize)
                self.set_winsize(self.master_fd, rows, cols, xpix, ypix)
            except Exception: pass

    def setup_philosophy_link(self):
        target_filename = "DESIGN_PHILOSOPHY.md"
        if os.path.exists(target_filename): return
        current_dir = os.path.abspath(".")
        parent_dir = os.path.dirname(current_dir)
        for _ in range(10):
            target_path = os.path.join(parent_dir, target_filename)
            if os.path.exists(target_path):
                rel_path = os.path.relpath(target_path, ".")
                try:
                    os.symlink(rel_path, target_filename)
                    self.log_event(f"Linked {target_filename} from {rel_path}")
                except OSError: pass
                return
            if parent_dir == os.path.dirname(parent_dir): break
            parent_dir = os.path.dirname(parent_dir)

    def inject_bootstrap_prompt(self):
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

**重要: 交渉プロトコル (The Negotiation Loop)**
他ノードとの通信には、以下のXMLライクなタグを**必ず**使用してください。タグで囲まれていないメッセージは相手に届きません。

*   **要求/指示:**
    ```
    [NEED_CONSENSUS] @target_node
    メッセージ本文...
    [/NEED_CONSENSUS]
    ```

*   **承認:**
    ```
    [ACCEPTED]
    承知しました...
    [/ACCEPTED]
    ```

*   **拒否/対案:**
    ```
    [CONFLICT]
    その方針には懸念があります...
    [/CONFLICT]
    ```

**重要: 初期化完了後の待機義務**
全ての確認が完了したら、現在の役割（Worker / Local Leader / Root Leader）と準備完了の旨を `[READY]` と共に出力し、**それ以外の発言やアクションは一切行わずに待機してください。**
指示があるまで沈黙を守ることが、あなたの最優先任務です。
"""
        self.log_event("Injecting bootstrap prompt...")
        try:
            with open(self.current_message_path, "w") as f:
                f.write(prompt.strip())
                f.flush()
                os.fsync(f.fileno())
            
            notification = f"\n\n[SYSTEM] 初期化コンテキストを受信しました。内容を確認するため、以下のコマンドを実行してください。\n\nread_file {self.current_message_path}\n"
            os.write(self.master_fd, notification.encode())
            time.sleep(0.1)
            os.write(self.master_fd, ENTER_KEY)

        except Exception as e:
            self.log_event(f"Failed to inject bootstrap prompt: {e}")

    def _send_to_bus(self, target_id, content):
        target_dir = os.path.join("./cip_bus", target_id)
        target_pid_path = os.path.join(target_dir, "bridge.pid")
        target_inbox_path = os.path.join(target_dir, "inbox")

        if not os.path.exists(target_pid_path):
            raise FileNotFoundError(f"Target @{target_id} not found.")

        with open(target_pid_path, "r") as f:
            target_pid = int(f.read().strip())
        
        os.kill(target_pid, 0)
        
        with open(target_inbox_path, "a") as f:
            f.write(f"\n[FROM: @{self.bus_id}]\n{content.strip()}\n")
            f.flush()
            os.fsync(f.fileno())
        
        os.kill(target_pid, signal.SIGUSR1)
        return target_id

    def extract_tag_content(self, text, start_tag, end_tag):
        # 文字列操作による堅牢なタグ抽出
        try:
            start_idx = text.index(start_tag)
            end_idx = text.index(end_tag, start_idx + len(start_tag))
            
            content_start = start_idx
            content_end = end_idx + len(end_tag)
            
            extracted_block = text[content_start:content_end]
            return extracted_block, content_end
        except ValueError:
            return None, -1

    def route_negotiation(self, clean_text):
        start_tag = "[NEED_CONSENSUS]"
        end_tag = "[/NEED_CONSENSUS]"
        
        block, end_idx = self.extract_tag_content(clean_text, start_tag, end_tag)
        if not block: return None 

        if "[FROM: @" in block: return None # 受信メッセージの表示は無視

        try:
            lines = block.splitlines()
            first_line = lines[0]
            if "@" in first_line:
                at_idx = first_line.index("@")
                target_part = first_line[at_idx+1:].strip()
                target_id = target_part.split()[0]
                
                self._send_to_bus(target_id, block)
                self.current_negotiation_partner = target_id
                self.log_event(f"Routed [NEED_CONSENSUS] to @{target_id}")
                return end_idx
        except Exception: pass
        
        return None

    def route_feedback(self, clean_text):
        if not self.current_negotiation_partner: return None
        
        # ACCEPTED の処理
        block, end_idx = self.extract_tag_content(clean_text, "[ACCEPTED]", "[/ACCEPTED]")
        if block and "[FROM: @" not in block:
            self._send_to_bus(self.current_negotiation_partner, block)
            self.log_event(f"Routed FEEDBACK to @{self.current_negotiation_partner}")
            return end_idx

        # CONFLICT の処理
        block, end_idx = self.extract_tag_content(clean_text, "[CONFLICT]", "[/CONFLICT]")
        if block and "[FROM: @" not in block:
            self._send_to_bus(self.current_negotiation_partner, block)
            self.log_event(f"Routed FEEDBACK to @{self.current_negotiation_partner}")
            return end_idx
            
        return None

    def send_system_message(self, msg):
        try:
            with open(self.inbox_path, "a") as f:
                f.write(f"\n{msg}\n")
                f.flush()
                os.fsync(f.fileno())
            os.write(self.pipe_w, b"x")
        except Exception: pass

    def strip_ansi(self, text):
        ansi_escape = re.compile(r'(?:\x1B[@-Z\\-_]|\x1B\[[0-?]*[ -/]*[@-~]|\x1B\(B|\x1B\[\?25[hl])')
        return ansi_escape.sub('', text)

    def run(self):
        self.setup_bus()
        self.setup_philosophy_link()
        signal.signal(signal.SIGUSR1, self.handle_signal)
        signal.signal(signal.SIGWINCH, self.handle_winch)

        self.old_tty = termios.tcgetattr(sys.stdin)
        pid, self.master_fd = pty.fork()
        
        if pid == 0:
            try:
                os.execvpe(self.cmd[0], self.cmd, os.environ)
            except Exception as e:
                print(f"\n[Child Process Error] {e}")
                time.sleep(5)
                sys.exit(1)
        
        try:
            tty.setraw(sys.stdin.fileno())
            self.handle_winch(None, None)
            output_buffer = b""
            bootstrapped = False
            
            while True:
                rfds, _, _ = select.select([sys.stdin, self.master_fd, self.pipe_r], [], [], 0.1)
                
                if self.pipe_r in rfds:
                    try:
                        while True:
                            if not os.read(self.pipe_r, 1024): break
                    except BlockingIOError: pass
                    self.process_inbox()

                if sys.stdin in rfds:
                    data = os.read(sys.stdin.fileno(), 1024)
                    if not data: break
                    os.write(self.master_fd, data)
                    
                if self.master_fd in rfds:
                    try:
                        data = os.read(self.master_fd, 1024)
                    except OSError: break
                    if not data: break
                    
                    os.write(sys.stdout.fileno(), data)
                    sys.stdout.flush()

                    output_buffer += data
                    if len(output_buffer) > 20000:
                        output_buffer = output_buffer[-10000:]

                    decoded_text = output_buffer.decode('utf-8', errors='ignore')
                    clean_text = self.strip_ansi(decoded_text)

                    if not bootstrapped:
                        if "> " in clean_text:
                             bootstrapped = True
                             self.log_event("Prompt detected. Starting bootstrap...")
                             time.sleep(1.0)
                             self.inject_bootstrap_prompt()
                             output_buffer = b""

                    # Keyword Detection (Block Parsing)
                    processed_idx = -1
                    
                    negotiation_end = self.route_negotiation(clean_text)
                    if negotiation_end and negotiation_end > processed_idx:
                        processed_idx = negotiation_end
                    
                    feedback_end = self.route_feedback(clean_text)
                    if feedback_end and feedback_end > processed_idx:
                        processed_idx = feedback_end
                        
                    if processed_idx != -1:
                        output_buffer = b""

                    if "Allow execution of:" in clean_text:
                        time.sleep(0.5)
                        os.write(self.master_fd, ENTER_KEY + b"\x08")
                        self.log_event("Auto-approved tool execution.")
                        output_buffer = b""

        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_tty)
            if self.master_fd: os.close(self.master_fd)
            os.close(self.pipe_r)
            os.close(self.pipe_w)
            print("\n[CIP-Bridge] Finished.")

def ensure_gitignore():
    ignore_file = ".gitignore"
    entries = { "cip_bus/", "bridge_events.log", "*.pid", "*.log", "__pycache__/", "current_message.md" }
    current_content = set()
    if os.path.exists(ignore_file):
        with open(ignore_file, "r") as f:
            current_content = set(line.strip() for line in f if line.strip() and not line.startswith("#"))
    missing = entries - current_content
    if missing:
        try:
            with open(ignore_file, "a") as f:
                if os.path.exists(ignore_file) and os.path.getsize(ignore_file) > 0:
                     with open(ignore_file, "rb") as f_rb:
                         f_rb.seek(-1, 2)
                         if f_rb.read(1) != b"\n": f.write("\n")
                f.write("\n# Auto-generated by CIP-Bridge\n")
                for entry in missing: f.write(f"{entry}\n")
        except Exception: pass

if __name__ == "__main__":
    ensure_gitignore()
    bridge = CIPBridge()
    bridge.run()
