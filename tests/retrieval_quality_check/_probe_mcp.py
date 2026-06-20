"""探测 MCP - 先 tools/list 看可用工具名。"""
import requests, json

URL = "http://localhost:9101/mcp"

get_resp = requests.get(URL, headers={"Accept": "text/event-stream"}, timeout=10)
session_id = get_resp.headers.get("mcp-session-id", "")
print(f"Session ID: {session_id}")

# tools/list
payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
resp = requests.post(URL, json=payload,
                     headers={"Accept": "application/json, text/event-stream",
                              "Content-Type": "application/json",
                              "mcp-session-id": session_id}, timeout=10)
print(f"Status: {resp.status_code}")
text = resp.text
# 解析 SSE
for line in text.split("\n"):
    if line.startswith("data: "):
        data = json.loads(line[6:])
        print(json.dumps(data, indent=2, ensure_ascii=False)[:2000])
