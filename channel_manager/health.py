# -*- coding: utf-8 -*-
"""
Health check with latency measurement.
Tests URL liveliness + measures response time for optimal source selection.
"""

import asyncio
import aiohttp
import time


async def _measure_url(session, url, sem, timeout=5):
    """Test a URL and return (url, is_alive, latency_ms)."""
    async with sem:
        start = time.time()
        try:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=timeout),
                ssl=False
            ) as resp:
                elapsed = (time.time() - start) * 1000
                if resp.status < 400 or resp.status == 206:
                    return (url, True, round(elapsed, 1))
                # GET failed, try Range
                try:
                    start2 = time.time()
                    headers = {'Range': 'bytes=0-1'}
                    async with session.get(
                        url, timeout=aiohttp.ClientTimeout(total=timeout),
                        ssl=False, headers=headers
                    ) as resp2:
                        elapsed2 = (time.time() - start2) * 1000
                        if resp2.status < 400 or resp2.status == 206:
                            return (url, True, round(elapsed2, 1))
                except Exception:
                    pass
                return (url, False, None)
        except Exception:
            return (url, False, None)


async def _run_batch(urls, concurrency=20, timeout=5):
    """Run measurement on a batch of URLs."""
    sem = asyncio.Semaphore(concurrency)
    connector = aiohttp.TCPConnector(limit=0, force_close=True)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [_measure_url(session, url, sem, timeout) for url in urls]
        results = await asyncio.gather(*tasks)
    return results


def check_urls(urls, concurrency=20, timeout=5, progress_callback=None):
    """
    Check all URLs and return alive/dead sets with latency data.

    Returns:
        (alive_set, dead_set, latency_dict)
        latency_dict = {url: latency_ms}
    """
    if not urls:
        return set(), set(), {}

    alive = set()
    dead = set()
    latencies = {}

    batch_size = 200
    total = len(urls)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        for batch_start in range(0, total, batch_size):
            batch = urls[batch_start:batch_start + batch_size]
            results = loop.run_until_complete(
                _run_batch(batch, concurrency, timeout)
            )
            for url, is_alive, lat in results:
                if is_alive:
                    alive.add(url)
                    if lat is not None:
                        latencies[url] = lat
                else:
                    dead.add(url)

            if progress_callback:
                done = min(batch_start + batch_size, total)
                progress_callback(done, total)
    finally:
        loop.close()

    return alive, dead, latencies


def pick_best_url(urls, latencies, alive_set):
    """
    Pick the best (lowest latency) URL from a list.

    Args:
        urls: list of candidate URLs
        latencies: dict {url: latency_ms}
        alive_set: set of alive URLs

    Returns:
        (best_url, latency_ms) or (None, None)
    """
    candidates = [u for u in urls if u in alive_set]
    if not candidates:
        return None, None

    best = None
    best_lat = float('inf')

    for url in candidates:
        lat = latencies.get(url, float('inf'))
        if lat < best_lat:
            best_lat = lat
            best = url

    return best, best_lat
