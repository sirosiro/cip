# @intent:responsibility 端末出力からエスケープシーケンス、 Thinking ブロック、 
#                         および CLI 特有 of UI ノイズ（罫線等）を抽出・除去するユーティリティ群。
# @intent:constraint [ARCHITECTURE_MANIFEST] にに基づき、正規表現 (re) の使用を禁止する。

def strip_ansi(text: str) -> str:
    """正規表現を使わず、ANSIエスケープシーケンスを除去する"""
    result = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "\x1b" and i + 1 < n and text[i + 1] == "[":
            j = i + 2
            while j < n:
                if "a" <= text[j].lower() <= "z" or text[j] == "@":
                    break
                j += 1
            i = j + 1
        elif text[i] == "\x1b" and i + 1 < n and text[i + 1] == "]":
            j = i + 2
            while j < n:
                if text[j] == "\x07" or (text[j] == "\x1b" and j + 1 < n and text[j + 1] == chr(92)):
                    break
                j += 1
            if j < n and text[j] == "\x07":
                i = j + 1
            else:
                i = j + 2
        else:
            result.append(text[i])
            i += 1
    return "".join(result)

def remove_thinking_block(text: str) -> str:
    """正規表現を使わず、<thinking>...</thinking> を除去する"""
    result = text
    while True:
        start_idx = result.find("<thinking")
        if start_idx == -1:
            break
        end_idx = result.find("</thinking>", start_idx)
        if end_idx == -1:
            break
        result = result[:start_idx] + result[end_idx + 11:]
    return result

def remove_ui_noise(text: str) -> str:
    """CLIツール特有 of UIノイズ（スピナー、罫線、プロンプト等）を除去する。"""
    lines = text.splitlines()
    cleaned_lines = []
    
    # ✦ をノイズとして扱う (テストの期待値に合わせる)
    braille_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏✦" 
    border_chars = "╭─╮│╰╯✓"
    
    for line in lines:
        temp_line = line
        # 枠線やスピナーを除去
        for c in braille_chars + border_chars:
            temp_line = temp_line.replace(c, "")
            
        stripped = temp_line.strip()
        
        # 【重要】タグが含まれる行は、装飾があっても削除せずに保護する
        if "[" in line:
            cleaned_lines.append(temp_line)
            continue

        # 特殊なプロンプトの置換
        if "Type your message" in stripped:
            cleaned_lines.append("> ")
            continue

        # 一般的なプロンプトの除去
        is_prompt = False
        if stripped.startswith("> ") or stripped.startswith("+ "):
            is_prompt = True
        elif stripped == ">" or stripped == "+":
            is_prompt = True
        elif stripped.startswith("│ >") or stripped.startswith("│ +"):
            is_prompt = True
            
        if is_prompt:
            continue
            
        # 既知のノイズ行
        if "Using: " in stripped and ".md file" in stripped: continue
        if "Rebooting the humor module" in stripped: continue
        if "(esc to cancel," in stripped: continue
        if "no sandbox" in stripped: continue
        if "Waiting for user confirmation" in stripped: continue
        
        if stripped:
            cleaned_lines.append(temp_line)
        
    return "\n".join(cleaned_lines)

def extract_tag_content(text: str, start_tag: str, end_tag: str) -> tuple[str | None, int]:
    """指定されたタグ内のコンテンツを抽出する。"""
    try:
        start_idx = text.index(start_tag)
        end_idx = text.index(end_tag, start_idx + len(start_tag))
        return text[start_idx:end_idx + len(end_tag)], end_idx + len(end_tag)
    except ValueError:
        return None, -1