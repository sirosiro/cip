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

    def run(self):
        self.setup_bus()
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
            
            # 初回のウィンドウサイズ設定
            self.handle_winch(None, None)

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

if __name__ == "__main__":
    bridge = CIPBridge()
    bridge.run()