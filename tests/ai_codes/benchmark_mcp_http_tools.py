import asyncio
import statistics
import time

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


URL = "http://localhost:9101/mcp"
ROUNDS = 3


async def timed(label, coro):
    t0 = time.perf_counter()
    result = await coro
    elapsed = time.perf_counter() - t0
    return label, elapsed, result


def extract_text(result):
    texts = []
    for item in getattr(result, "content", []):
        text = getattr(item, "text", None)
        if text:
            texts.append(text)
    return "\n".join(texts)


async def one_round(round_idx: int):
    metrics = []
    async with streamablehttp_client(URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            metrics.append(await timed(f"round{round_idx}.initialize", session.initialize()))
            metrics.append(await timed(f"round{round_idx}.list_tools", session.list_tools()))
            metrics.append(await timed(f"round{round_idx}.nbrag_stats", session.call_tool("nbrag_stats", {})))
            metrics.append(
                await timed(
                    f"round{round_idx}.nbrag_search_and_fetch",
                    session.call_tool(
                        "nbrag_search_and_fetch",
                        {
                            "collection_name": "funboost",
                            "query": "funboost 多进程消费 is_using_multiprocessing concurrent_num process pool 使用方法",
                            "top_k": 5,
                            "fetch_top_n_raw": 3,
                            "fetch_chars": 4000,
                        },
                    ),
                )
            )
            metrics.append(
                await timed(
                    f"round{round_idx}.nbrag_grep",
                    session.call_tool(
                        "nbrag_grep",
                        {
                            "collection_name": "funboost",
                            "keyword": "multi_process_consume",
                            "context_lines": 12,
                            "max_results": 10,
                        },
                    ),
                )
            )
            metrics.append(
                await timed(
                    f"round{round_idx}.nbrag_get_raw_file",
                    session.call_tool(
                        "nbrag_get_raw_file",
                        {
                            "collection_name": "funboost",
                            "file_path": "D:/codes/funboost_docs/source/articles/c8.md",
                            "line_start": 772,
                            "line_end": 780,
                        },
                    ),
                )
            )
    return metrics


async def main():
    all_metrics = []
    for i in range(1, ROUNDS + 1):
        round_metrics = await one_round(i)
        all_metrics.extend(round_metrics)
        for label, elapsed, result in round_metrics:
            preview = ""
            if label.endswith(("nbrag_stats", "nbrag_grep", "nbrag_get_raw_file", "nbrag_search_and_fetch")):
                text = extract_text(result).replace("\n", " ")[:120]
                preview = f" | preview={text}"
            print(f"{label}: {elapsed:.4f}s{preview}")

    print("\nSummary")
    print("-" * 60)
    by_name = {}
    for label, elapsed, _ in all_metrics:
        key = label.split(".", 1)[1]
        by_name.setdefault(key, []).append(elapsed)

    for key, values in by_name.items():
        print(
            f"{key}: avg={statistics.mean(values):.4f}s min={min(values):.4f}s max={max(values):.4f}s rounds={len(values)}"
        )


if __name__ == "__main__":
    asyncio.run(main())
