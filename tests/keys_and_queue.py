import asyncio
import json
import os
import sys
import tempfile

import aiohttp

from harness import OfflineLink, load_bot, start_server, stop_server


async def main() -> int:
    os.environ["API_KEY"] = ""
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, ok, detail))
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))

    bot = load_bot()
    with tempfile.TemporaryDirectory(prefix="cue-offline-keys-") as tempdir:
        keyfile = os.path.join(tempdir, "keys.json")
        bot.KEYS_FILE = keyfile
        link = OfflineLink()
        bridge, app, runner, base = await start_server(bot, link)
        session = aiohttp.ClientSession()
        try:
            store = app["keys"]
            check("bridge starts open before keys are minted", not store.active())

            made = store.mint(10, "teman")
            check("ten API keys are minted", len(made) == 10, str(len(made)))
            check("keys use the expected prefix and length", all(key.startswith("sk-yuuri-") and len(key) == 57 for _, key in made))
            check("key store becomes protected", store.active())

            with open(keyfile, encoding="utf-8") as reader:
                saved = json.load(reader)
            stored_text = json.dumps(saved)
            check("key file contains none of the minted plain-text keys", all(key not in stored_text for _, key in made))

            response = await session.post(
                f"{base}/v1/chat/completions", json={"messages": [{"role": "user", "content": "no key"}]}
            )
            check("missing API key is refused", response.status == 401)

            response = await session.post(
                f"{base}/v1/chat/completions",
                headers={"Authorization": "Bearer sk-yuuri-not-a-real-key"},
                json={"messages": [{"role": "user", "content": "bad key"}]},
            )
            check("incorrect API key is refused", response.status == 401)

            good = made[0][1]
            link.queue_response({"choices": [{"message": {"content": "authorized answer"}}]})
            response = await session.post(
                f"{base}/v1/chat/completions",
                headers={"Authorization": f"Bearer {good}"},
                json={"messages": [{"role": "user", "content": "first"}]},
            )
            body = await response.json()
            check("valid Bearer key passes", body["choices"][0]["message"]["content"] == "authorized answer")

            link.queue_response({"choices": [{"message": {"content": "header answer"}}]})
            response = await session.post(
                f"{base}/v1/chat/completions",
                headers={"x-api-key": made[1][1]},
                json={"messages": [{"role": "user", "content": "header"}]},
            )
            check("x-api-key header works", response.status == 200)

            store.revoke(made[0][0])
            response = await session.post(
                f"{base}/v1/chat/completions",
                headers={"Authorization": f"Bearer {good}"},
                json={"messages": [{"role": "user", "content": "revoked"}]},
            )
            check("revoked key no longer works", response.status == 401)

            usage = {row["id"]: row["requests"] for row in store.report()}
            check("usage is counted for authorized calls", usage.get(made[0][0]) == 1 and usage.get(made[1][0]) == 1)
            public_fields = {"id", "label", "enabled", "created", "requests", "last_used"}
            check("key report exposes only public usage fields", all(set(row) == public_fields for row in store.report()))

            response = await session.get(f"{base}/health")
            health = await response.json()
            check("health endpoint remains available", health["status"] == "ok")
            check("health exposes queue capacity", health["queue"]["limit"] == bot.QUEUE_MAX)
            check("offline test link reports no pending work", health["queue"]["waiting"] == 0)
        finally:
            await session.close()
            await stop_server(bridge, runner)

    failed = [row for row in checks if not row[1]]
    print()
    print(f"{len(checks)} checks ran with {len(failed)} failure(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
