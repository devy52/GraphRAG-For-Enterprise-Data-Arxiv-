#!/usr/bin/env python3
"""Browser evidence collector for the live Material 3 GraphRAG UI.

The server must be started separately. The script records the same queries in
forced VECTOR and HYBRID evaluation modes, captures screenshots, inspects the
inline graph topology, and records a browser video as WebM. It also converts
that WebM to animated WebP when ffmpeg is available.

This artifact is UI/runtime evidence only; it is never used as a benchmark metric.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from playwright.async_api import async_playwright


DEFAULT_QUERIES = [
    "Who are the primary authors of the GraphRAG-R1 paper proposing process-constrained reinforcement learning?",
    "Which reinforcement learning method does Chuanyue Yu and colleagues use to enhance reasoning in GraphRAG?",
    "Compare the primary evaluation objectives of GraphRAG-Bench and IslamicFaithQA.",
]


async def run_phase(page, base_url: str, mode: str, queries: List[str], out_dir: Path) -> List[Dict[str, Any]]:
    await page.set_extra_http_headers({"X-GraphRAG-Eval-Mode": mode})
    results: List[Dict[str, Any]] = []
    for idx, query in enumerate(queries, 1):
        await page.goto(base_url.rstrip("/") + "/ui/", wait_until="domcontentloaded")
        await page.wait_for_timeout(500)
        # Fairness invariant: the UI cache must be disabled so VECTOR and HYBRID
        # are both evaluated by the backend rather than one reusing the other.
        cache_toggle = page.locator("#cache-toggle")
        if await cache_toggle.is_checked():
            await cache_toggle.uncheck()
        await page.locator("#query-input").fill(query)
        await page.locator("#send-btn").click()
        await page.wait_for_timeout(300)
        await page.wait_for_timeout(2500)

        route_badges = await page.locator(".route-badge").all_inner_texts()
        subgraphs = await page.locator(".inline-subgraph-wrapper").count()
        last_answer = ""
        answers = await page.locator(".assistant-card .assistant-text-content").all_inner_texts()
        if answers:
            last_answer = answers[-1]

        shot = out_dir / f"{mode}_{idx:02d}.webp"
        await page.screenshot(path=str(shot), full_page=True, type="webp", quality=85)
        results.append({
            "mode": mode,
            "query": query,
            "route_badges": route_badges,
            "subgraph_widgets": subgraphs,
            "answer_preview": last_answer[:1000],
            "screenshot": str(shot),
        })
    return results


async def main_async(args) -> None:
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    queries = DEFAULT_QUERIES
    if args.queries_file:
        queries = [q.strip() for q in Path(args.queries_file).read_text(encoding="utf-8").splitlines() if q.strip()]

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=not args.headed)
        context = await browser.new_context(record_video_dir=str(out_dir / "video"), viewport={"width": 1440, "height": 960})
        page = await context.new_page()
        await page.goto(args.base_url.rstrip("/") + "/ui/", wait_until="domcontentloaded")
        results = []
        for mode in ("vector", "hybrid"):
            results.extend(await run_phase(page, args.base_url, mode, queries, out_dir))

        # Inspect the Material 3 graph view separately so topology rendering is recorded.
        await page.goto(args.base_url.rstrip("/") + "/ui/", wait_until="domcontentloaded")
        graph_button = page.locator('button.rail-destination[data-view="graph-view"]')
        if await graph_button.count():
            await graph_button.click()
            await page.wait_for_timeout(1500)
        graph_nodes = await page.locator('#vis-network-canvas canvas').count()
        graph_canvas = await page.locator('#vis-network-canvas').count()
        await page.screenshot(path=str(out_dir / "graph_topology.webp"), full_page=True, type="webp", quality=85)
        results.append({
            "mode": "ui_graph_view",
            "graph_canvas_present": bool(graph_canvas),
            "vis_network_present": bool(graph_nodes),
            "screenshot": str(out_dir / "graph_topology.webp"),
        })
        await context.close()
        video_files = list((out_dir / "video").glob("*.webm"))
        await browser.close()

    artifact = {
        "base_url": args.base_url,
        "query_count": len(queries),
        "results": results,
        "video_files": [str(x) for x in video_files],
        "video_note": "Playwright records WebM; WebP files are keyframe screenshots. Optional ffmpeg conversion creates animated WebP.",
    }
    (out_dir / "browser_session.json").write_text(json.dumps(artifact, indent=2), encoding="utf-8")

    if video_files and shutil.which("ffmpeg"):
        webm = video_files[0]
        animated = out_dir / "browser_session.webp"
        subprocess.run([
            "ffmpeg", "-y", "-i", str(webm),
            "-vf", "fps=6,scale=1280:-1:flags=lanczos", "-loop", "0",
            "-c:v", "libwebp", "-lossless", "0", "-q:v", "60", str(animated)
        ], check=False, capture_output=True)

    print(f"Browser evidence written to {out_dir}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://127.0.0.1:8000")
    p.add_argument("--queries-file")
    p.add_argument("--output-dir", default="data/browser_evidence")
    p.add_argument("--headed", action="store_true")
    args = p.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
