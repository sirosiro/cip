import os
import shutil
import time
import signal
import sys
import pty
import tty
import select
import termios
import fcntl
import struct
import platform
import argparse
from typing import List, Optional

from .transport.fs_bus import FSBus
from .protocol.stack import ProtocolStack, Packet
from .core.negotiator import NegotiationManager
from .utils.text_utils import remove_ui_noise, strip_ansi, remove_thinking_block

# @intent:responsibility コマンドライン引数の処理、 .gitignore の自動生成、 
#                         および BridgeCore の起動（ブートストラップ）を担当するエントリーポイント。

# OSに応じた改行コード
if platform.system() == "Windows":
    ENTER_KEY = b"\r\n"
else:
    ENTER_KEY = b"\r"

# @intent:responsibility 互換性のために bridge.py のクラス名を継承しつつ、 
#                         実体として 4階層モデルの Orchestrator をラップする。
class CIPBridge:
    def __init__(self, cmd=None, bus_id=None):
        self.cmd = cmd if cmd else self._find_gemini_command()
        self.bus_id = bus_id if bus_id else os.path.basename(os.getcwd())
        
        # 4階層モデルの実装
        self.transport = FSBus(self.bus_id)
        self.protocol = ProtocolStack(self.bus_id)
        self.negotiator = NegotiationManager(self.bus_id)
        
        self.master_fd = None
        self.old_tty = None
        self.bootstrapped = False
        self.current_message_path = "current_message.md"
        
        self.pipe_r, self.pipe_w = os.pipe()
        fcntl.fcntl(self.pipe_r, fcntl.F_SETFL, os.O_NONBLOCK)
        fcntl.fcntl(self.pipe_w, fcntl.F_SETFL, os.O_NONBLOCK)

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

    def log_event(self, msg):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open("bridge_events.log", "a") as f:
                f.write(f"[{timestamp}] [{self.bus_id}] {msg}\n")
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

    def handle_signal(self, signum, frame):
        if signum == signal.SIGUSR1:
            try:
                os.write(self.pipe_w, b"x")
            except Exception: pass
        elif signum == signal.SIGWINCH:
            self.handle_winch(signum, frame)

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

    def process_inbox(self):
        content = self.transport.receive()
        if not content: return

        self.log_event(f"Processing inbox message (len: {len(content)})")
        clean_content = remove_ui_noise(content)

        if "[NEED_CONSENSUS]" in clean_content:
             self.negotiator.last_received_type = "NEED_CONSENSUS"
        elif "[ACCEPTED]" in clean_content:
             self.negotiator.last_received_type = "ACCEPTED"
        elif "[CONFLICT]" in clean_content:
             self.negotiator.last_received_type = "CONFLICT"
        
        if "[FROM: @" in clean_content:
            try:
                start_tag = "[FROM: @"
                start_idx = clean_content.index(start_tag) + len(start_tag)
                end_idx = clean_content.index("]", start_idx)
                partner_id = clean_content[start_idx:end_idx]
                self.negotiator.set_partner(partner_id)
                self.log_event(f"Set negotiation partner to @{partner_id}")
            except ValueError: pass

        try:
            with open(self.current_message_path, "w") as cf:
                cf.write(clean_content)
                cf.flush()
                os.fsync(cf.fileno())
        except Exception as e:
            self.log_event(f"Error writing current_message: {e}")

        notification = f"\n\n[SYSTEM] 新着メッセージがあります。内容を確認するため、以下のコマンドを実行してください。\n\nread_file {self.current_message_path}\n"
        self.log_event("Injecting notification to PTY...")
        os.write(self.master_fd, notification.encode())
        time.sleep(0.5)
        os.write(self.master_fd, ENTER_KEY)

    def inject_bootstrap_prompt(self):
        prompt = (
            "[SYSTEM: Context Initialization]\n"
            "あなたはCIPエコシステムのノードとして起動しました。\n"
            "現在のカレントディレクトリ（担当領域）を確認し、以下の手順で自身の役割を自律的に決定してください。\n"
            "\n"
            "1. **憲法の確認 (Global Philosophy):**\n"
            "   ルートの設計思想が存在するか確認し、ロードしてください。\n"
            "   `$ ls -l DESIGN_PHILOSOPHY.md` (シンボリックリンクなら `cat`, 実体なら `read_file`)\n"
            "   **重要: ロードした内容に基づいた分析、考古学的調査、または追加の行動をこの段階で開始してはなりません。**\n"
            "\n"
            "2. **法律の確認 (Local Manifest):**\n"
            "   このディレクトリのアーキテクチャ定義（`ARCHITECTURE_MANIFEST.md`）をロードしてください。\n"
            "   **重要: マニフェストが存在しない場合も、その事実を認識するに留め、不足を補うための自律的な調査を行わないでください。**\n"
            "\n"
            "3. **部下の確認 (Sub-Node Discovery):**\n"
            "   さらに下位のディレクトリ（サブモジュール）が存在するか確認してください。\n"
            "   もし存在すれば、あなたはそれらのリーダー（Local Leader）としての責務も負います。\n"
            "\n"
            "**重要: 交渉プロトコル (The Negotiation Loop)**\n"
            "他ノードとの通信には、以下のXMLライクなタグのいずれかを**必ず**使用してください。\n"
            "**【厳守】本文の全てをタグの「内側」に記述してください。タグの外に書かれた内容は相手に届きません。**\n"
            "タグはネスト（入れ子）にせず、一回の発言につき一つの目的（要求または応答）のために使用します。\n"
            "タグの開始から終了までは「一つの不可分な操作（トランザクション）」です。中身を書き終えたら、必ず終了タグを閉じてください。\n"
            "**注意: [ACCEPTED] や [CONFLICT] などのタグが開かれたまま [READY] を出力することは禁止です。必ずタグを閉じてから [READY] してください。**\n"
            "\n"
            "*   **要求/指示 (他ノードへ動いてもらう場合):**\n"
            "    ```\n"
            "    [NEED_CONSENSUS] @target_node\n"
            "    メッセージ本文（ここに含まれる内容のみが転送されます）\n"
            "    [/NEED_CONSENSUS]\n"
            "    ```\n"
            "\n"
            "*   **承認 (要求に対する返信):**\n"
            "    ```\n"
            "    [ACCEPTED]\n"
            "    承知しました。報告内容：...（ここに含まれる内容のみが転送されます）\n"
            "    [/ACCEPTED]\n"
            "    ```\n"
            "\n"
            "*   **拒否/対案 (要求に対する返信):**\n"
            "    ```\n"
            "    [CONFLICT]\n"
            "    その方針には懸念があります。理由：...（ここに含まれる内容のみが転送されます）\n"
            "    [/CONFLICT]\n"
            "    ```\n"
            "\n"
            "**重要: 待機義務 (Post-Communication)**\n"
            "初期化完了の報告（憲法、法律、部下の状況）は、**タグを使わずに** 画面に出力するだけに留めてください。\n"
            "まだ上位ノードからの具体的な指示がないため、この段階で `[ACCEPTED]` や `[NEED_CONSENSUS]` などの通信タグを使用してはいけません。\n"
            "報告を画面に出力し終えたら、最後に `[READY]` を出力して待機状態に移行してください。\n"
            "**`[READY]` を出力した後は、いかなる理由があっても、次の指示があるまで追加の発言、ファイルのリストアップ、提案、調査を一切行わずに沈黙を守ってください。これがあなたの最優先任務です。**\n"
        )
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

    def run(self):
        self.transport.setup()
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
            
            while True:
                try:
                    rfds, _, _ = select.select([sys.stdin, self.master_fd, self.pipe_r], [], [], 0.1)
                except InterruptedError:
                    continue
                
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

                    try:
                        decoded_text = output_buffer.decode('utf-8', errors='ignore')
                    except Exception:
                        decoded_text = ""
                    
                    if not self.bootstrapped:
                        pre_clean = remove_thinking_block(strip_ansi(decoded_text))
                        if "> " in pre_clean:
                             self.bootstrapped = True
                             self.log_event("Prompt detected. Starting bootstrap...")
                             time.sleep(1.0)
                             self.inject_bootstrap_prompt()
                             output_buffer = b""

                    packets = self.protocol.parse(decoded_text)
                    if packets:
                        for packet in packets:
                            if self.negotiator.should_route(packet):
                                self.negotiator.update_state(packet)
                                target = self.negotiator.get_route(packet)
                                if target:
                                    payload = self.protocol.serialize(packet)
                                    if self.transport.send(target, payload):
                                        self.log_event(f"Routed {packet.type} to @{target}")

                        output_buffer = b""

        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_tty)
            if self.master_fd: os.close(self.master_fd)
            os.close(self.pipe_r)
            os.close(self.pipe_w)
            self.transport.cleanup()
            print("\n[CIP-Bridge] Finished.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", action="version", version="CIP-Bridge v3.0.0 (Refactored)")
    parser.parse_args()

    ignore_file = ".gitignore"
    entries = { "cip_bus/", "bridge_events.log", "*.pid", "*.log", "__pycache__/" }
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

    bridge = CIPBridge()
    bridge.run()

if __name__ == "__main__":
    main()