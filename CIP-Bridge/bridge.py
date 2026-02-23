#!/usr/bin/env python3
import os
import sys
import pty
import tty
import select
import termios
import signal
import fcntl
import struct
import time
import platform
import shutil
import argparse
from collections import deque

# コマンドオプション(バージョン表示とパス設定確認用)
parser = argparse.ArgumentParser()
parser.add_argument(
    "--version",
    action="version",
    version="CIP-Bridge v2.6.8"
)
parser.parse_args()

# OSに応じた改行コード（Enterキー）の定義
if platform.system() == "Windows":
    ENTER_KEY = b"\r\n"
else:
    ENTER_KEY = b"\r"

# @intent:responsibility [NEED_CONSENSUS] キーワードを検知し、自律モードへの移行と
#                         FS-Bus を介したメッセージ転送を制御する。
#                         また、ウィンドウサイズ変更を透過的に伝播させる。
#                         正規表現(re)を使用せず、基本的な文字列操作のみでパースを行う。

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
        
        # Pull型通信用のメッセージ閲覧ファイル
        self.current_message_path = "current_message.md"
        
        self.mode = "BYPASS"
        self.master_fd = None
        self.old_tty = None
        
        self.pipe_r, self.pipe_w = os.pipe()
        fcntl.fcntl(self.pipe_r, fcntl.F_SETFL, os.O_NONBLOCK)
        fcntl.fcntl(self.pipe_w, fcntl.F_SETFL, os.O_NONBLOCK)

        self.current_negotiation_partner = None
        
        # 無限ループ防止用のフラグ
        # 直前に受信したメッセージのタイプを記憶する (NEED_CONSENSUS / ACCEPTED / CONFLICT)
        self.last_received_type = None
        
        # 送信重複防止用のキャッシュ
        # 直前に送信したメッセージ内容を保持する
        self.last_sent_content = None

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

    def remove_ui_noise(self, text):
        # 正規表現を使わず、CLIツール特有のUIノイズ（スピナー、罫線、プロンプト等）を除去する
        
        # 1. 過去のターンの出力を切り捨てる (最新のプロンプト以降に限定)
        prompt_marker = ">   Type your message"
        p_idx = text.rfind(prompt_marker)
        if p_idx != -1:
            text = text[p_idx:]

        lines = text.splitlines()
        cleaned_lines = []
        
        # 点字スピナーパターン + Sparkle(✦)
        braille_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏✦"
        # 罫線パターン
        border_chars = "╭─╮│╰╯"
        
        for line in lines:
            # 行全体を削除するのではなく、ノイズ文字だけを除去する
            # これにより、ノイズと同じ行にあるタグやテキストを救出する
            temp_line = line
            for c in braille_chars:
                temp_line = temp_line.replace(c, "")
            for c in border_chars:
                temp_line = temp_line.replace(c, "")
            
            stripped = temp_line.strip()
            if not stripped:
                continue

            # 行レベルでのノイズ判定
            if "Using: " in stripped and ".md file" in stripped: continue
            if "Rebooting the humor module" in stripped: continue
            if "(esc to cancel," in stripped: continue
            if "no sandbox (see /docs)" in stripped: continue
            if "Auto (Gemini 3) /model" in stripped: continue
            
            # プロンプト行は削除せず、識別子として残す (Bootstrap検知のため)
            if ">   Type your message" in stripped:
                cleaned_lines.append("> ")
                continue

            cleaned_lines.append(temp_line)
        
        return "\n".join(cleaned_lines)

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
                    
                    # 受信時にUIノイズを除去してから保存
                    clean_content = self.remove_ui_noise(content)

                    # メッセージタイプの記録（無限ループ防止用）
                    if "[NEED_CONSENSUS]" in clean_content:
                        self.last_received_type = "NEED_CONSENSUS"
                    elif "[ACCEPTED]" in clean_content:
                        self.last_received_type = "ACCEPTED"
                    elif "[CONFLICT]" in clean_content:
                        self.last_received_type = "CONFLICT"

                    with open(self.current_message_path, "w") as cf:
                        cf.write(clean_content)
                        cf.flush()
                        os.fsync(cf.fileno())

                    if "[FROM: @" in clean_content:
                        try:
                            start_tag = "[FROM: @"
                            start_idx = clean_content.index(start_tag) + len(start_tag)
                            end_idx = clean_content.index("]", start_idx)
                            self.current_negotiation_partner = clean_content[start_idx:end_idx]
                            self.log_event(f"Set negotiation partner to @{self.current_negotiation_partner}")
                        except ValueError: pass

                    notification = f"\n\n[SYSTEM] 新着メッセージがあります。内容を確認するため、以下のコマンドを実行してください。\n\nread_file {self.current_message_path}\n"
                    
                    self.log_event("Injecting notification to PTY...")
                    os.write(self.master_fd, notification.encode())
                    time.sleep(0.5) # 遅延を増やして確実性を高める
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

    def _send_to_bus(self, target_id, content):
        target_dir = os.path.join("./cip_bus", target_id)
        target_pid_path = os.path.join(target_dir, "bridge.pid")
        target_inbox_path = os.path.join(target_dir, "inbox")

        if not os.path.exists(target_pid_path):
            self.log_event(f"Error: Target @{target_id} not found at {target_pid_path}")
            raise FileNotFoundError(f"Target @{target_id} not found.")

        # 重複送信防止ロジック: 前回の内容と完全に一致、または前回内容が今回内容を含んでいる場合はスキップ
        # (ストリームの伸長は許可するが、全く同じものや、以前送ったものの一部を再送しない)
        if self.last_sent_content and content.strip() == self.last_sent_content:
             return target_id

        with open(target_pid_path, "r") as f:
            target_pid = int(f.read().strip())
        
        os.kill(target_pid, 0)
        
        with open(target_inbox_path, "a") as f:
            f.write(f"\n[FROM: @{self.bus_id}]\n{content.strip()}\n")
            f.flush()
            os.fsync(f.fileno())
        
        self.last_sent_content = content.strip()
        os.kill(target_pid, signal.SIGUSR1)
        return target_id

    def extract_tag_content(self, text, start_tag, end_tag):
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

        # 受信メッセージの無視: ブロック内に他人の [FROM: @ がある場合は無視
        # ただし、自分のID (self.bus_id) の FROM タグは許容する（自己署名）
        if "[FROM: @" in block and f"[FROM: @{self.bus_id}]" not in block:
             return None

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
        except Exception as e:
            self.log_event(f"Negotiation routing error: {e}")
        
        return None

    def route_feedback(self, clean_text):
        if "[ACCEPTED]" in clean_text:
             if not self.current_negotiation_partner:
                 self.log_event("Debug: [ACCEPTED] found but no partner.")
             # else:
             #    self.log_event(f"Debug: Partner is {self.current_negotiation_partner}")

        if not self.current_negotiation_partner:
            if "[ACCEPTED]" in clean_text or "[CONFLICT]" in clean_text:
                if "[FROM: @" in clean_text: return None
                # self.log_event("Debug: Feedback detected but no negotiation partner set.")
            return None
        
        # ACCEPTED の処理
        block, end_idx = self.extract_tag_content(clean_text, "[ACCEPTED]", "[/ACCEPTED]")
        if block:
            # 無限ループ防止: 直前に受信したのが ACCEPTED なら、返信としての ACCEPTED は転送しない
            if self.last_received_type == "ACCEPTED":
                self.log_event("Loop prevention: Blocked redundant ACCEPTED feedback.")
                return end_idx

            # 他人の発言（受信メッセージ）は無視。自分のIDならOK。
            if "[FROM: @" not in block or f"[FROM: @{self.bus_id}]" in block:
                try:
                    self._send_to_bus(self.current_negotiation_partner, block)
                    self.log_event(f"Routed FEEDBACK to @{self.current_negotiation_partner}")
                    return end_idx
                except Exception as e:
                    self.log_event(f"Feedback routing error: {e}")
            else:
                return end_idx

        # CONFLICT の処理
        block, end_idx = self.extract_tag_content(clean_text, "[CONFLICT]", "[/CONFLICT]")
        if block:
            if "[FROM: @" not in block or f"[FROM: @{self.bus_id}]" in block:
                try:
                    self._send_to_bus(self.current_negotiation_partner, block)
                    self.log_event(f"Routed FEEDBACK to @{self.current_negotiation_partner}")
                    return end_idx
                except Exception as e:
                    self.log_event(f"Feedback routing error: {e}")
            else:
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
        # 正規表現を使わず、ANSIエスケープシーケンスを除去する
        result = []
        i = 0
        n = len(text)
        while i < n:
            if text[i] == '\x1b': # ESC
                i += 1
                if i < n:
                    if text[i] == '[': # CSI (Command Sequence Introducer)
                        i += 1
                        # 終端文字 (@から~までの文字) までスキップ
                        while i < n and not ('@' <= text[i] <= '~'):
                            i += 1
                        i += 1
                    elif text[i] == '(': # G0 character set
                        i += 2
                    elif '@' <= text[i] <= '_': # Fe escape sequence
                        i += 1
                    else:
                        i += 1
            else:
                result.append(text[i])
                i += 1
        return "".join(result)

    def remove_thinking_block(self, text):
        # 正規表現を使わず、<thinking>...</thinking> を除去する
        while True:
            start_idx = text.find("<thinking")
            if start_idx == -1:
                break
            end_idx = text.find("</thinking>", start_idx)
            if end_idx == -1:
                break
            # 閉じタグ "</thinking>" は 11文字
            text = text[:start_idx] + text[end_idx + 11:]
        return text

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

                    try:
                        decoded_text = output_buffer.decode('utf-8', errors='ignore')
                    except Exception:
                        decoded_text = ""
                    
                    # パース前にUIノイズ除去と履歴の切り捨てを適用
                    # これにより、画面に残っている過去の閉じタグとの誤マッチを防ぐ
                    clean_text = self.strip_ansi(decoded_text)
                    clean_text = self.remove_thinking_block(clean_text)
                    
                    if not bootstrapped:
                        # Bootstrap検知はUIノイズ除去前のテキストで行う
                        if "> " in clean_text:
                             bootstrapped = True
                             self.log_event("Prompt detected. Starting bootstrap...")
                             time.sleep(1.0)
                             self.inject_bootstrap_prompt()
                             output_buffer = b""
                    
                    # パース用にはUIノイズを除去したテキストを使用
                    parsed_text = self.remove_ui_noise(clean_text)

                    # Keyword Detection (Block Parsing)
                    processed_idx = -1
                    
                    negotiation_end = self.route_negotiation(parsed_text)
                    if negotiation_end and negotiation_end > processed_idx:
                        processed_idx = negotiation_end
                    
                    feedback_end = self.route_feedback(parsed_text)
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
    # current_message.md は .gitignore に追加しない（AIの可視性確保のため）
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

if __name__ == "__main__":
    ensure_gitignore()
    bridge = CIPBridge()
    bridge.run()