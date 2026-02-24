import re

# @intent:responsibility 端末出力からエスケープシーケンス、 Thinking ブロック、 
#                         および CLI 特有の UI ノイズ（罫線等）を抽出・除去するユーティリティ群。

def strip_ansi(text: str) -> str:
    """
    正規表現を使わず、ANSIエスケープシーケンスを除去する
    """
    result = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == '\x1b': # ESC
            i += 1
            if i < n:
                if text[i] == '[': # CSI
                    i += 1
                    while i < n and not ('@' <= text[i] <= '~'):
                        i += 1
                    i += 1
                elif text[i] == '(': # G0 set
                    i += 2
                elif '@' <= text[i] <= '_':
                    i += 1
                else:
                    i += 1
        else:
            result.append(text[i])
            i += 1
    return "".join(result)

def remove_thinking_block(text: str) -> str:
    """
    正規表現を使わず、<thinking>...</thinking> を除去する
    """
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

# @intent:responsibility CLI ツールの出力に含まれるスピナー、罫線、ヘルプメッセージ等を 
#                         行レベルでフィルタリングし、実質的なメッセージのみを抽出する。
def remove_ui_noise(text: str) -> str:
    """
    正規表現を使わず、CLIツール特有のUIノイズ（スピナー、罫線、プロンプト等）を除去する
    """
    prompt_marker = ">   Type your message"
    p_idx = text.rfind(prompt_marker)
    if p_idx != -1:
        text = text[p_idx:]

    lines = text.splitlines()
    cleaned_lines = []
    
    braille_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏✦"
    border_chars = "╭─╮│╰╯"
    
    for line in lines:
        temp_line = line
        for c in braille_chars:
            temp_line = temp_line.replace(c, "")
        for c in border_chars:
            temp_line = temp_line.replace(c, "")
        
        stripped = temp_line.strip()
        if not stripped:
            continue

        if "Using: " in stripped and ".md file" in stripped: continue
        if "Rebooting the humor module" in stripped: continue
        if "(esc to cancel," in stripped: continue
        if "no sandbox (see /docs)" in stripped: continue
        if "Auto (Gemini 3) /model" in stripped: continue
        
        if ">   Type your message" in stripped:
            cleaned_lines.append("> ")
            continue

        cleaned_lines.append(temp_line)
    
    return "\n".join(cleaned_lines)

def extract_tag_content(text: str, start_tag: str, end_tag: str) -> tuple[str | None, int]:
    """
    指定されたタグ内のコンテンツを抽出する。
    """
    try:
        start_idx = text.index(start_tag)
        end_idx = text.index(end_tag, start_idx + len(start_tag))
        
        content_start = start_idx
        content_end = end_idx + len(end_tag)
        
        extracted_block = text[content_start:content_end]
        return extracted_block, content_end
    except ValueError:
        return None, -1