import asyncio
import os
import sys
import tempfile

import aiohttp

from harness import OfflineLink, load_bot, start_server, stop_server


ORIGIN = "https://dashboard.example.test"


async def main() -> int:
    os.environ["API_KEY"] = ""
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, ok, detail))
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))

    bot = load_bot()
    with tempfile.TemporaryDirectory(prefix="cue-offline-cors-") as tempdir:
        bot.KEYS_FILE = os.path.join(tempdir, "keys.json")
        link = OfflineLink()
        bridge, app, runner, base = await start_server(bot, link)
        session = aiohttp.ClientSession()
        try:
            response = await session.options(
                f"{base}/v1/chat/completions",
                headers={
                    "Origin": ORIGIN,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "authorization,content-type",
                },
            )
            await response.read()
            allow = response.headers.get("Access-Control-Allow-Origin", "")
            headers = response.headers.get("Access-Control-Allow-Headers", "").lower()
            check("preflight is answered", response.status == 204, str(response.status))
            check("requested origin is echoed", allow == ORIGIN, allow)
            check("authorization header is allowed", "authorization" in headers, headers)
            check("content-type header is allowed", "content-type" in headers, headers)
            check("POST method is allowed", "POST" in response.headers.get("Access-Control-Allow-Methods", ""))

            response = await session.get(f"{base}/v1/models", headers={"Origin": ORIGIN})
            body = await response.json()
            check("GET response includes CORS", response.headers.get("Access-Control-Allow-Origin") == ORIGIN)
            ids = [row["id"] for row in body["data"]]
            check("configured model is advertised", bot.MODEL_ID in ids, str(ids))
            check("configured aliases are advertised", all(alias in ids for alias in bot.MODEL_ALIASES), str(ids))
            modalities = body["data"][0]["input_modalities"]
            check("model declares audio input", "audio" in modalities, str(modalities))
            check("model declares video input", "video" in modalities, str(modalities))
            check("model declares image input", "image" in modalities, str(modalities))

            response = await session.options(
                f"{base}/v1/audio/transcriptions",
                headers={"Origin": ORIGIN, "Access-Control-Request-Method": "POST"},
            )
            await response.read()
            check("preflight works on the audio route", response.status == 204)

            link.queue_response({"choices": [{"message": {"content": "offline response"}}]})
            response = await session.post(
                f"{base}/v1/chat/completions",
                headers={"Origin": ORIGIN},
                json={"messages": [{"role": "user", "content": "hello"}]},
            )
            body = await response.json()
            check("actual POST response includes CORS", response.headers.get("Access-Control-Allow-Origin") == ORIGIN)
            check("actual POST uses the offline link", body["choices"][0]["message"]["content"] == "offline response")
        finally:
            await session.close()
            await stop_server(bridge, runner)

    failed = [row for row in checks if not row[1]]
    print()
    print(f"{len(checks)} checks ran with {len(failed)} failure(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
