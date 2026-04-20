from mcp.server.fastmcp import FastMCP
import os

# スクリプトのディレクトリを基準としたパス設定
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_resource_path(relative_path):
    return os.path.join(BASE_DIR, relative_path)

# MCPサーバーの初期化
mcp = FastMCP("CIP-Core-Intel-Prompting")

# 1. リソースの登録
@mcp.resource("cip://docs/philosophy")
def get_philosophy() -> str:
    # ルートにある DESIGN_PHILOSOPHY.md を直接参照
    path = get_resource_path("DESIGN_PHILOSOPHY.md")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

@mcp.resource("cip://docs/scrivener")
def get_scrivener_spec() -> str:
    # docs/standards/ 配下にある仕様書を直接参照
    path = get_resource_path("docs/standards/CIP_Scrivener.md")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

# 2. プロンプト（指示の自動注入）
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
