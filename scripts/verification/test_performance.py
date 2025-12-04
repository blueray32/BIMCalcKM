import asyncio
import time
import httpx
import statistics

BASE_URL = "https://157.230.149.106"
ENDPOINTS = [
    "/items?org=demo&project=test",
    "/prices?org=demo&project=test",
    "/match?org=demo&project=test",
    "/progress?org=demo&project=test",
    "/reports?org=demo&project=test",
]
CONCURRENT_REQUESTS = 10


async def fetch(client, url):
    start = time.time()
    try:
        resp = await client.get(url, timeout=10.0, follow_redirects=True)
        duration = time.time() - start
        return url, resp.status_code, duration
    except Exception as e:
        return url, 0, 0.0


async def run_load_test():
    print(f"🚀 Starting load test on {BASE_URL}")
    print(f"👥 Simulating {CONCURRENT_REQUESTS} concurrent users per endpoint...")

    # Disable SSL verification for staging
    async with httpx.AsyncClient(verify=False) as client:
        tasks = []
        for _ in range(CONCURRENT_REQUESTS):
            for url in ENDPOINTS:
                tasks.append(fetch(client, BASE_URL + url))

        results = await asyncio.gather(*tasks)

    # Analyze results
    times_by_url = {}
    errors = 0
    for url, status, duration in results:
        path = url.replace(BASE_URL, "")
        if path not in times_by_url:
            times_by_url[path] = []

        if status == 200:
            times_by_url[path].append(duration)
        else:
            errors += 1
            print(f"❌ Failed: {path} returned {status}")

    print("\n📊 Performance Results:")
    print(f"{'Endpoint':<40} | {'Avg (s)':<10} | {'Max (s)':<10} | {'Min (s)':<10}")
    print("-" * 80)

    all_pass = True
    for path, times in times_by_url.items():
        if not times:
            print(f"{path:<40} | {'N/A':<10} | {'N/A':<10} | {'N/A':<10}")
            continue

        avg_t = statistics.mean(times)
        max_t = max(times)
        min_t = min(times)
        print(f"{path:<40} | {avg_t:<10.3f} | {max_t:<10.3f} | {min_t:<10.3f}")

        if avg_t > 2.0:
            all_pass = False
            print(f"  ⚠️ Slow response detected on {path}")

    if errors > 0:
        print(f"\n❌ {errors} requests failed.")
        all_pass = False

    if all_pass:
        print("\n✅ All endpoints responded within performance targets (< 2s).")
    else:
        print("\n⚠️ Some endpoints exceeded performance targets or failed.")


if __name__ == "__main__":
    asyncio.run(run_load_test())
