import asyncio
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
    check("OpenAI-style content is extracted", bot.answer_text({"choices": [{"message": {"content": "hello"}}]}) == "hello")
    check("legacy choice text is extracted", bot.answer_text({"choices": [{"text": "legacy"}]}) == "legacy")
    check("top-level content is extracted", bot.answer_text({"content": "from content"}) == "from content")
    check("top-level text is extracted", bot.answer_text({"text": "from text"}) == "from text")
    check("plain string is preserved", bot.answer_text("plain string") == "plain string")
    check("unknown reply is serialized as JSON", bot.answer_text({"other": "value"}) == '{"other": "value"}')

    with tempfile.TemporaryDirectory(prefix="cue-offline-text-") as tempdir:
        bot.KEYS_FILE = os.path.join(tempdir, "keys.json")
        link = OfflineLink()
        bridge, app, runner, base = await start_server(bot, link)
        session = aiohttp.ClientSession()
        try:
            answer = "baris satu\nbaris dua"
            link.queue_response({"content": answer})
            response = await session.post(
                f"{base}/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "beri dua baris"}]},
            )
            body = await response.json()
            check("HTTP chat preserves multiline text", body["choices"][0]["message"]["content"] == answer)
            check("HTTP request is handled by the local test link", len(link.calls) == 1)
        finally:
            await session.close()
            await stop_server(bridge, runner)

    failed = [row for row in checks if not row[1]]
    print()
    print(f"{len(checks)} checks ran with {len(failed)} failure(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
