"""MCP HTTP 客户端工具：处理 session 和 SSE 响应。"""
import json
import time
import requests
from typing import Any

MCP_URL = "http://localhost:9101/mcp"


def _sse_json(resp: requests.Response) -> list[dict]:
    """解析 SSE 格式响应，取出 data: 行转 JSON。"""
    resp.encoding = "utf-8"
    text = resp.text
    results = []
    for line in text.split("\n"):
        if line.startswith("data: "):
            try:
                results.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return results


def _mcp_request(method: str, params: dict, session_id: str) -> list[dict]:
    """发一条 JSON-RPC 请求到 MCP 服务器，返回 SSE 解析后的 JSON 响应列表。"""
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    resp = requests.post(
        MCP_URL, json=payload,
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "mcp-session-id": session_id,
        },
        timeout=60,
    )
    return _sse_json(resp)


def _call_mcp_tool_text(tool_name: str, arguments: dict | None = None) -> str:
    """调用 MCP 工具，返回原始文本结果。"""
    # 1. 拿 session
    get_resp = requests.get(MCP_URL, headers={"Accept": "text/event-stream"}, timeout=10)
    session_id = get_resp.headers.get("mcp-session-id", "")
    if not session_id:
        return "Error: 无法获取 MCP session ID"

    # 2. initialize
    init_responses = _mcp_request("initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "retrieval_quality_check", "version": "1.0"},
    }, session_id)
    if any("error" in r for r in init_responses):
        err = next(r["error"] for r in init_responses if "error" in r)
        return f"Error: 初始化失败 - {err.get('message', str(err))}"

    # 3. notifications/initialized
    _mcp_request("notifications/initialized", {}, session_id)

    # 4. tools/call
    args = arguments or {}
    call_responses = _mcp_request("tools/call", {"name": tool_name, "arguments": args}, session_id)
    for r in call_responses:
        if "result" in r:
            content = r["result"].get("content", [])
            is_error = r["result"].get("isError", False)
            texts = []
            for item in content:
                if item.get("type") == "text":
                    texts.append(item.get("text", ""))
            result_text = "\n".join(texts)
            if is_error:
                return f"Error (MCP reported): {result_text}"
            return result_text
        if "error" in r:
            return f"Error: {r['error'].get('message', str(r['error']))}"

    return "Error: 无有效响应"


def call_mcp_tool(tool_name: str, arguments: dict | None = None) -> str:
    """调用 MCP 工具，返回文本结果，并附带本次调用总耗时。

    耗时包含：获取 session、initialize、initialized 通知和 tools/call。"""
    started_at = time.perf_counter()
    try:
        result_text = _call_mcp_tool_text(tool_name, arguments)
    except Exception as exc:
        elapsed = time.perf_counter() - started_at
        return f"[调用抛出异常] {type(exc).__name__}: {exc}\n\n[耗时统计] {tool_name}: {elapsed:.3f} 秒"

    elapsed = time.perf_counter() - started_at
    return f"{result_text}\n\n[耗时统计] {tool_name}: {elapsed:.3f} 秒"


# 快速测试
if __name__ == "__main__":
    print("测试 nbrag_help:")
    print(call_mcp_tool("nbrag_help")[:300])
    print()
    print("测试 nbrag_stats:")
    print(call_mcp_tool("nbrag_stats")[:300])
    print()
    print("测试 nbrag_search:")
    print(call_mcp_tool("nbrag_search", {"query": "试用期", "collection_name": "worker_rights", "top_k": 2, "include_content": False})[:300])
