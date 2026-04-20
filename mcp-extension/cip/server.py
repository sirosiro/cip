from mcp.server.fastmcp import FastMCP
import os

# スクリプトのディレクトリを基準としたパス設定
# これにより、拡張機能としてインストールされた後も正しくリソースを参照できます
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_resource_path(filename):
    return os.path.join(BASE_DIR, filename)

# MCPサーバーの初期化
mcp = FastMCP("CIP-Core-Intel-Prompting")

# 1. リソースの登録：規約ドキュメントをAIがいつでも読めるようにする
@mcp.resource("cip://docs/philosophy")
def get_philosophy() -> str:
    path = get_resource_path("DESIGN_PHILOSOPHY.md")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

@mcp.resource("cip://docs/scrivener")
def get_scrivener_spec() -> str:
    path = get_resource_path("CIP_Scrivener.md")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

# 2. プロンプト（指示の自動注入）：ここが「規約厳守」のキモ
@mcp.prompt()
def cip_architect_mode() -> str:
    """
    AIをCIPシニアアーキテクトに変貌させるためのシステムプロンプト。
    """
    return (
        "あなたはCIP（Core-Intent Prompting）のシニアアーキテクトです。\n"
        "常に cip://docs/philosophy を参照し、規約違反がないか確認してください。\n"
        "ユーザーがコードを求めても、Intent（意図）が不明確な場合は、まず問い直してください。"
    )

if __name__ == "__main__":
    mcp.run()
