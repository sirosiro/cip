import os
import sys
import pty
import tty
import termios
import select
import signal
import fcntl
import time
from typing import List, Optional
from ..transport.fs_bus import FSBus
from ..protocol.stack import ProtocolStack, Packet
from ..core.negotiator import NegotiationManager, BridgeState

ENTER_KEY = b"\r"

# @intent:responsibility CLIアプリケーション（Gemini）と CIP-Bridge のオーケストレーションを行う。
#                         PTY の入出力を監視し、通信プロトコルに従ってメッセージのルーティングを行う。
# @intent:constraint [ARCHITECTURE_MANIFEST] に基づき、正規表現 (re) の使用を禁止する。

class BridgeCore:
    def __init__(self, cmd: List[str] = None, bus_id: str = None, base_dir: str = "./cip_bus"):
        self.cmd = cmd if cmd else self._find_gemini_command()
        self.bus_id = bus_id if bus_id else os.path.basename(os.getcwd())
        self.base_dir = base_dir

        self.transport = FSBus(self.bus_id, base_dir=self.base_dir)
        self.protocol = ProtocolStack(self.my_id)
        self.negotiator = NegotiationManager(self.my_id)
        
        self.master_fd = None
        self.old_tty = None
        self.bootstrapped = False
        
        self.pipe_r, self.pipe_w = os.pipe()
        fcntl.fcntl(self.pipe_r, fcntl.F_SETFL, os.O_NONBLOCK)
        fcntl.fcntl(self.pipe_w, fcntl.F_SETFL, os.O_NONBLOCK)

        self.current_message_path = "current_message.md"

    @property
    def my_id(self):
        return self.bus_id

    def _find_gemini_command(self) -> List[str]:
        env_cmd = os.environ.get("CIP_BRIDGE_CMD")
        if env_cmd: return [env_cmd]
        for path in ["/usr/local/bin/gemini", "/opt/homebrew/bin/gemini"]:
            if os.path.exists(path): return [path]
        return ["gemini"]

    def log_event(self, message: str):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_file = "bridge_events.log"
        with open(log_file, "a") as f:
            f.write(f"[{timestamp}] [BridgeCore:{self.bus_id}] {message}\n")

    def setup_philosophy_link(self):
        """DESIGN_PHILOSOPHY.md および docs ディレクトリへのシンボリックリンクを作成する。"""
        # 1. 憲法 (DESIGN_PHILOSOPHY.md) のリンク
        target_md = "../DESIGN_PHILOSOPHY.md"
        link_md = "DESIGN_PHILOSOPHY.md"
        if os.path.exists(target_md) and not os.path.exists(link_md):
            try:
                os.symlink(target_md, link_md)
                self.log_event(f"Linked DESIGN_PHILOSOPHY.md from {target_md}")
            except Exception as e:
                self.log_event(f"Failed to link DESIGN_PHILOSOPHY.md: {e}")
                
        # 2. ドキュメントレジストリ (_docs) のリンク
        # @intent:rationale フラクタル構造下で、下位ノードのAIが CIP_Scriber 等の
        #                   グローバルな仕様書にアクセスできるようにするため。
        target_docs = "../docs"
        link_docs = "_docs"
        
        # ルートの docs を探索 (最大10階層上まで)
        search_dir = ".."
        found_docs = False
        for _ in range(10):
            potential_docs = os.path.join(search_dir, "docs")
            if os.path.exists(potential_docs) and os.path.isdir(potential_docs):
                if not os.path.exists(link_docs):
                    try:
                        os.symlink(potential_docs, link_docs)
                        self.log_event(f"Linked _docs from {potential_docs}")
                    except Exception as e:
                        self.log_event(f"Failed to link _docs: {e}")
                found_docs = True
                break
            search_dir = os.path.join(search_dir, "..")

    def handle_signal(self, signum, frame):
        os.write(self.pipe_w, b"\x00")

    def handle_winch(self, signum, frame):
        if self.master_fd:
            try:
                import array, struct
                s = array.array('H', [0, 0, 0, 0])
                fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, s)
                fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, s)
            except Exception: pass

    def process_inbox(self):
        content = self.transport.receive()
        if not content: return

        self.log_event(f"Processing inbox message (len: {len(content)})")
        clean_content = content.strip()

        # 交渉状態の更新
        tags = ["NEED_CONSENSUS", "ACCEPTED", "CONFLICT", "COMPLETED", "FAILED"]
        for t in tags:
            if f"[{t}]" in clean_content:
                self.negotiator.record_receive(t)
                break
        
        if "[FROM: @" in clean_content:
            try:
                start_tag = "[FROM: @"
                id_start = clean_content.find(start_tag) + len(start_tag)
                id_end = clean_content.find("]", id_start)
                sender_id = clean_content[id_start:id_end]
                self.negotiator.set_partner(sender_id)
                self.log_event(f"Set negotiation partner to @{sender_id}")
            except Exception: pass

        with open(self.current_message_path, "w") as f:
            f.write(clean_content)
        
        self.inject_notification()

    def inject_notification(self):
        # @intent:responsibility AIに新着メッセージの確認を促す。
        # @intent:rationale Gemini CLIのプロンプト状態をリセットするために \x15 (CTRL+U) を送り、
        #                   実行を確実にするために適度な待機 (time.sleep) と空の改行を組み合わせる。
        if not self.master_fd: return
        time.sleep(0.5)
        # 以前のコミット ef9e127 で最適化された遅延パターンを復元
        msg = f"\x15\r\n[SYSTEM] 新着メッセージがあります。画面にエコーしないで read_file で {self.current_message_path} を読め"
        os.write(self.master_fd, msg.encode('utf-8'))
        time.sleep(0.1)
        cmd = "\r"
        os.write(self.master_fd, cmd.encode('utf-8'))
        self.log_event("Injecting notification and command to PTY...")

    def inject_system_message(self, message: str):
        """AIに対して割り込みのシステムメッセージを送信する（非同期遅延実行）。"""
        if not self.master_fd: return
        
        # @intent:rationale AIの出力直後（[/NEED_CONSENSUS]検知直後など）は、CLIがプロンプトを描画する前であり、
        #                   このタイミングでPTYに入力すると「ペースト」と判定されて \r が改行として処理され、
        #                   プロンプトに送信待ちのまま残ってしまう。
        #                   これを防ぐため、別スレッドで待機し、CLIが入力受付状態に戻ってから注入する。
        import threading
        def delayed_inject():
            try:
                time.sleep(2.0) # CLIがプロンプト表示に戻るまで待機
                
                with open(self.current_message_path, "w") as f:
                    f.write(f"[SYSTEM_MESSAGE]\n{message}\n")
                
                time.sleep(0.1)
                os.write(self.master_fd, b"\x15") # CTRL+U (クリア)
                time.sleep(0.1)
                
                msg = f"\r\n[SYSTEM] システムからの割り込み通知があります。画面にエコーしないで read_file で {self.current_message_path} を読め"
                os.write(self.master_fd, msg.encode('utf-8'))
                
                # ペーストモード判定を避けるため、Enterの前に少し待機
                time.sleep(0.5) 
                os.write(self.master_fd, b"\r")
                self.log_event(f"Injected system message via delayed thread: {message}")
            except Exception as e:
                self.log_event(f"Delayed injection failed: {e}")
                
        threading.Thread(target=delayed_inject, daemon=True).start()

    def inject_bootstrap_prompt(self):
        if not self.master_fd: return
        
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
            "3. **組織の確認 (Worker Discovery):**\n"
            "   部下（Worker）の存在や構成については、**自分からディレクトリを調査しないでください。**\n"
            "   必要になった場合、または人間から指示された場合にのみ `@list` コマンドを発行して、現在稼働中の正確な Worker リストをシステムから取得してください。\n"
            "\n"
            "**重要: 交渉プロトコル (The Negotiation Loop)**\n"
            "他ノードとの通信には、以下のXMLライクなタグのいずれかを**必ず**使用してください。\n"
            "**【厳守】本文の全てをタグの「内側」に記述してください。タグの外に書かれた内容は相手に届きません。**\n"
            "タグはネスト（入れ子）にせず、一回の発言につき一つの目的（要求または応答）のために使用します。\n"
            "タグの開始から終了までは「一つの不可分な操作（トランザクション）」です。中身を書き終えたら、必ず終了タグを閉じてください。\n"
            "\n"
            "*   **要求/指示 (他ノードへ動いてもらう場合):**\n"
            "    ```\n"
            "    [NEED_CONSENSUS] @target_node\n"
            "    メッセージ本文\n"
            "    [/NEED_CONSENSUS]\n"
            "    ```\n"
            "\n"
            "*   **承認 (要求に対する返信):**\n"
            "    ```\n"
            "    [ACCEPTED]\n"
            "    承知しました。報告内容：...\n"
            "    [/ACCEPTED]\n"
            "    ```\n"
            "\n"
            "*   **拒否/対案 (要求に対する返信):**\n"
            "    ```\n"
            "    [CONFLICT]\n"
            "    その方針には懸念があります。理由：...\n"
            "    [/CONFLICT]\n"
            "    ```\n"
            "\n"
            "**重要: 自律交渉モードと終了条件**\n"
            "1. **`@cip` 指示:** 人間から `@cip` で始まる指示を受けた場合、あなたは「交渉責任者」として自律的にWorker（専門家）と合意形成を行う義務があります。処理が終わるまで人間は介入しません。\n"
            "2. **直列的対話:** 複数のWorkerに指示を出す場合は、**必ず1つのWorkerに指示を出し、その返答を待ってから**次のWorkerへ指示を出してください。同時に複数に `[NEED_CONSENSUS]` を出してはいけません。\n"
            "3. **3回制限:** Workerとの合意形成（NEED_CONSENSUSの再送）は**最大3回**までに留めてください。3回で決まらない場合は「失敗」とみなし、人間に判断を仰いでください。\n"
            "4. **終了宣言:** 全ての調整が完了したら、必ず最後に **`[COMPLETED]`** を出力して終了してください。不調に終わった場合は **`[FAILED]`** を出力してください。これらのタグにより人間に制御が戻ります。\n"
            "5. **Worker不在:** 指定したWorkerが不在というシステム通知を受けた場合、待機せず自らその役割を兼任して方針を決定してください。\n"
            "\n"
            "**重要: 待機義務 (Post-Communication)**\n"
            "初期化完了の報告（憲法、法律、部下の状況）は、**タグを使わずに** 画面に出力するだけに留めてください。\n"
            "報告を画面に出力し終えたら、最後に `[READY]` を出力して待機状態に移行してください。\n"
            "**`[READY]` を出力した後は、いかなる理由があっても、次の指示があるまで追加の発言、ファイルのリストアップ、提案、調査を一切行わずに沈黙を守ってください。**\n"
        )
        
        try:
            with open(self.current_message_path, "w") as f:
                f.write(prompt.strip())
            
            time.sleep(0.5)
            # @intent:responsibility 起動時にAIに対してCIPノードとしての振る舞いを注入する。
            # 以前のコミット ef9e127 で最適化された遅延パターンを復元
            notification = f"[SYSTEM] 初期化コンテキストを受信しました。画面にエコーしないで read_file で {self.current_message_path} を読め"
            os.write(self.master_fd, notification.encode('utf-8'))
            time.sleep(0.1)
            cmd = "\r"
            os.write(self.master_fd, cmd.encode('utf-8'))
            self.log_event("Injecting bootstrap prompt and command to PTY...")
        except Exception as e:
            self.log_event(f"Failed to inject bootstrap prompt: {e}")

    def run(self):
        # @intent:responsibility メインのイベントループ。標準入力、PTY出力、自己パイプを監視する。
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
                time.sleep(1)
                sys.exit(1)
        
        try:
            tty.setraw(sys.stdin.fileno())
            self.handle_winch(None, None)
            output_buffer = b""
            
            while True:
                try:
                    rfds, _, _ = select.select([sys.stdin, self.master_fd, self.pipe_r], [], [], 0.1)
                except (InterruptedError, select.error):
                    continue
                
                if self.pipe_r in rfds:
                    try:
                        while True:
                            if not os.read(self.pipe_r, 1024): break
                    except (BlockingIOError, OSError): pass
                    # @intent:rationale 新着メッセージ受信時は、AI側のプロンプト入力と同期させるため
                    #                   過去の出力を一旦リセットする。
                    output_buffer = b""
                    self.process_inbox()

                if sys.stdin in rfds:
                    data = os.read(sys.stdin.fileno(), 1024)
                    if not data: break
                    
                    # @intent:rationale トリガーの検知 (@cip, @list)
                    if b"\r" in data or b"\n" in data:
                        try:
                            decoded_out = output_buffer.decode('utf-8', errors='ignore')
                            from ..utils.text_utils import strip_ansi
                            clean_out = strip_ansi(decoded_out)
                            lines = [line for line in clean_out.split("\n") if line.strip()]
                            if lines:
                                last_line = lines[-1]
                                
                                # @list トリガー: Workerのリストを明示的に取得する
                                if "> @list" in last_line or last_line.strip().startswith("@list"):
                                    self.log_event("List trigger detected: Sending active workers.")
                                    workers = self.transport.get_active_workers()
                                    workers_list = ", ".join(workers) if workers else "なし"
                                    # 先に入力(Enter)をPTYに処理させる
                                    os.write(self.master_fd, data)
                                    time.sleep(0.2)
                                    self.inject_system_message(f"現在稼働中の Worker (モジュール) のリスト: [{workers_list}]。これら以外のWorkerは存在しません。マニフェストの閲覧は行わず、指示は委譲してください。")
                                    continue
                                
                                # @cip トリガー: 自律交渉モードへの移行
                                elif "> @cip" in last_line or last_line.strip().startswith("@cip"):
                                    self.negotiator.set_mode(BridgeState.AUTO)
                                    self.log_event("Trigger detected: Switching to AUTO mode.")
                                    workers = self.transport.get_active_workers()
                                    workers_list = ", ".join(workers) if workers else ""
                                    # 先に入力(Enter)をPTYに処理させる
                                    os.write(self.master_fd, data)
                                    time.sleep(0.2)
                                    self.inject_system_message(f"現在アクティブなWorker: [{workers_list}]。これら以外のWorkerは不在です。合意形成は最大3回以内に行い、完遂なら [COMPLETED]、不調なら [FAILED] を出力せよ。")
                                    continue
                        except: pass
                    
                    # AUTOモード中は人間の入力を遮断（ただしCTRL+C等のシグナルは通したい場合があるため要検討）
                    if self.negotiator.mode == BridgeState.AUTO:
                        # 簡易的な実装として、特定のシグナル以外は無視する
                        if b"\x03" in data: # CTRL+C
                             self.negotiator.set_mode(BridgeState.BYPASS)
                             self.log_event("User interrupted: Switching to BYPASS mode.")
                        else:
                             continue

                    os.write(self.master_fd, data)
                    
                if self.master_fd in rfds:
                    try:
                        data = os.read(self.master_fd, 1024)
                    except OSError: break
                    if not data: break
                    
                    os.write(sys.stdout.fileno(), data)
                    sys.stdout.flush()

                    output_buffer += data
                    
                    try:
                        decoded_text = output_buffer.decode('utf-8', errors='ignore')
                    except Exception:
                        decoded_text = ""
                        
                    # @intent:rationale パケットの状態に応じた動的バッファ管理
                    # 開始タグがある（パケット構築中）場合は切り捨てず保護する
                    has_start_tag = False
                    for tag in ["NEED_CONSENSUS", "ACCEPTED", "CONFLICT", "COMPLETED", "FAILED"]:
                        if f"[{tag}]" in decoded_text:
                            has_start_tag = True
                            break
                            
                    if not has_start_tag:
                        # タグがない（平常時、ノイズ蓄積中）は短く保つ
                        if len(output_buffer) > 50000:
                            output_buffer = output_buffer[-10000:]
                    else:
                        # タグがある場合でも、異常な無限出力を防ぐための安全装置 (5MB)
                        if len(output_buffer) > 5 * 1024 * 1024:
                            self.log_event("WARNING: Buffer exceeded 5MB during packet construction. Truncating.")
                            output_buffer = output_buffer[-10000:]

                    # 再度デコード（バッファが切り詰められた可能性があるため）
                    try:
                        decoded_text = output_buffer.decode('utf-8', errors='ignore')
                    except Exception:
                        decoded_text = ""
                        
                    # プロンプト検知によるブートストラップ
                    from ..utils.text_utils import strip_ansi
                    clean_text = strip_ansi(decoded_text)
                    
                    if not self.bootstrapped:
                        if "> " in clean_text:
                             self.bootstrapped = True
                             self.log_event("Prompt detected. Starting bootstrap...")
                             time.sleep(1.0)
                             self.inject_bootstrap_prompt()
                             output_buffer = b""

                    if "Allow execution of:" in clean_text:
                        os.write(self.master_fd, ENTER_KEY + b"\x08")
                        self.log_event("Auto-approved tool execution.")
                        output_buffer = b"" # バッファをクリアして連続発火（ちらつき）を防止

                    # パケット解析
                    packets = self.protocol.parse(decoded_text)
                    if packets:
                        for packet in packets:
                            # 【追加】自分が送信元としてパースされたパケットのみを処理する（エコーバック対策）
                            if packet.sender_id != self.my_id:
                                continue
                                
                            if self.negotiator.should_route(packet):
                                self.negotiator.update_state(packet)
                                
                                # @intent:rationale 不在Workerへの[NEED_CONSENSUS]検知
                                # 重複排除(update_state)の後に実行することで、エコーによる二重発火を防止する
                                if packet.type == "NEED_CONSENSUS" and packet.target_id:
                                    active_workers = self.transport.get_active_workers()
                                    if f"@{packet.target_id}" not in active_workers:
                                        self.inject_system_message(f"@{packet.target_id} は現在不在です。Leaderがその役割を兼任し、独断で方針を決定してください。")

                                # 交渉上限チェック（Leaderが次のNEED_CONSENSUSを出そうとした際）
                                if self.negotiator.mode == BridgeState.AUTO:
                                    if self.negotiator.negotiation_count >= self.negotiator.max_negotiations:
                                        if packet.type == "NEED_CONSENSUS":
                                            self.inject_system_message("交渉回数が上限（3回）に達しました。これ以上の調整は不要です。現状の対立点を整理し [FAILED] を出力して終了してください。")

                                target = self.negotiator.get_route(packet)
                                if target:
                                    payload = self.protocol.serialize(packet)
                                    if self.transport.send(target, payload):
                                        self.log_event(f"Routed {packet.type} to @{target}")
                                    else:
                                        self.log_event(f"Failed to send {packet.type} to @{target}")
                        
                        # @intent:rationale AIが連続して出力した [READY] などの後続データを失わないよう
                        #                   最後に処理したパケットの終了タグ以降の部分のみをバッファに残す。
                        last_packet = packets[-1]
                        end_marker = f"[/{last_packet.type}]"
                        last_pos = decoded_text.rfind(end_marker)
                        if last_pos != -1:
                            remaining_text = decoded_text[last_pos + len(end_marker):]
                            output_buffer = remaining_text.encode('utf-8')

        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_tty)
            if self.master_fd:
                try:
                    os.close(self.master_fd)
                except OSError: pass
            try:
                os.close(self.pipe_r)
                os.close(self.pipe_w)
            except OSError: pass
            self.transport.cleanup()
            print("\n[CIP-Bridge] Finished.")

if __name__ == "__main__":
    core = BridgeCore()
    core.run()