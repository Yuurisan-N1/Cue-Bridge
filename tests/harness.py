import ast
import asyncio
import base64
import json
import os
import sys
import tempfile
import types
from pathlib import Path
from typing import Any

import aiohttp
from aiohttp import web


class _OfflineConnectionStatus:
    def is_connected(self) -> bool:
        return False


class OfflineLink:
    def __init__(self, responses: list[dict] | None = None) -> None:
        self.client = _OfflineConnectionStatus()
        self.lock = asyncio.Lock()
        self.waiting = 0
        self.served = 0
        self.responses = list(responses or [])
        self.calls: list[dict] = []
        self.delay = 0.0

    def queue_response(self, response: dict) -> None:
        self.responses.append(response)

    async def ask(self, payload: dict, attachments: list[Any]) -> dict:
        snapshots = []
        for item in attachments:
            snapshots.append({"manifest": item.manifest_row(), "bytes": Path(item.path).read_bytes()})
        self.calls.append({"payload": payload, "attachments": snapshots})
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.responses:
            return self.responses.pop(0)
        return {"choices": [{"message": {"content": "offline default"}}]}


def load_bot() -> types.ModuleType:
    source_path = Path(__file__).with_name("bot.py")
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    allowed_roots = set(sys.stdlib_module_names) | {"aiohttp"}

    class OfflineImportStripper(ast.NodeTransformer):
        def __init__(self) -> None:
            self.removed_names: set[str] = set()

        def visit_ImportFrom(self, node):
            root = (node.module or "").split(".", 1)[0]
            if root not in allowed_roots:
                self.removed_names.update(
                    alias.asname or alias.name for alias in node.names if alias.name != "*"
                )
                return None
            return node

        def visit_Import(self, node):
            kept = []
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in allowed_roots:
                    kept.append(alias)
                else:
                    self.removed_names.add(alias.asname or root)
            if not kept:
                return None
            node.names = kept
            return node

        def visit_Expr(self, node):
            call = node.value
            if (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id in self.removed_names
            ):
                return None
            return self.generic_visit(node)

        def visit_arg(self, node):
            if isinstance(node.annotation, ast.Name) and node.annotation.id in self.removed_names:
                node.annotation = None
            return self.generic_visit(node)

    stripper = OfflineImportStripper()
    tree = stripper.visit(tree)
    ast.fix_missing_locations(tree)
    module_name = f"_offline_bot_test_{os.getpid()}_{id(tree)}"
    module = types.ModuleType(module_name)
    module.__file__ = str(source_path)
    sys.modules[module_name] = module
    exec(compile(tree, str(source_path), "exec"), module.__dict__)
    return module


async def start_server(bot: types.ModuleType, link: OfflineLink):
    bridge = bot.Bridge(link)
    await bridge.start_session()
    app = bot.build_app(bridge)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    return bridge, app, runner, f"http://127.0.0.1:{port}"


async def stop_server(bridge, runner) -> None:
    await bridge.close_session()
    await runner.cleanup()


def png_bytes() -> bytes:
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg=="
    )


def wav_bytes() -> bytes:
    return (
        b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
        b"D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    )


def mp4_bytes() -> bytes:
    return b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 40


def data_url(mime: str, raw: bytes) -> str:
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")


async def main() -> int:
    os.environ["API_KEY"] = ""
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, ok, detail))
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))

    bot = load_bot()
    with tempfile.TemporaryDirectory(prefix="cue-offline-harness-") as tempdir:
        bot.KEYS_FILE = os.path.join(tempdir, "keys.json")
        bot.MEDIA_MAX_BYTES = 1024 * 1024
        link = OfflineLink()
        bridge, app, runner, base = await start_server(bot, link)
        session = aiohttp.ClientSession()
        try:
            response = await session.get(f"{base}/health")
            body = await response.json()
            check("health endpoint works offline", response.status == 200 and body["status"] == "ok")

            response = await session.get(f"{base}/v1/models")
            body = await response.json()
            capabilities = body["data"][0]["capabilities"]
            check(
                "models lists image audio and video input",
                capabilities["vision"] and capabilities["audio_input"] and capabilities["video_input"]
                and not capabilities["audio_output"],
                json.dumps(capabilities),
            )

            link.queue_response({"choices": [{"message": {"content": "plain answer"}}]})
            response = await session.post(
                f"{base}/v1/chat/completions",
                json={"model": "yuuri-3.2-flash", "messages": [{"role": "user", "content": "hi"}]},
            )
            body = await response.json()
            check("plain text chat returns an OpenAI-style answer", body["choices"][0]["message"]["content"] == "plain answer")
            check("plain text payload reaches the offline link", link.calls[-1]["payload"]["messages"][-1]["content"] == "hi")

            link.queue_response({"choices": [{"message": {"content": "the image shows a dot"}}]})
            response = await session.post(
                f"{base}/v1/chat/completions",
                json={"messages": [{"role": "user", "content": [
                    {"type": "text", "text": "what is this"},
                    {"type": "image_url", "image_url": {"url": data_url("image/png", png_bytes())}},
                ]}]},
            )
            body = await response.json()
            snapshot = link.calls[-1]["attachments"]
            check("image request is handled", body["choices"][0]["message"]["content"] == "the image shows a dot")
            check("image bytes are handed to the offline link", len(snapshot) == 1 and snapshot[0]["manifest"]["kind"] == "image")

            link.queue_response({"choices": [{"message": {"content": "audio heard"}}]})
            response = await session.post(
                f"{base}/v1/chat/completions",
                json={"messages": [{"role": "user", "content": [
                    {"type": "text", "text": "describe the sound"},
                    {"type": "input_audio", "input_audio": {"data": base64.b64encode(wav_bytes()).decode(), "format": "wav"}},
                ]}]},
            )
            body = await response.json()
            audio_snapshot = link.calls[-1]["attachments"]
            check("audio request is handled", body["choices"][0]["message"]["content"] == "audio heard")
            check("audio bytes are handed to the offline link", len(audio_snapshot) == 1 and audio_snapshot[0]["manifest"]["kind"] == "audio")

            link.queue_response({"choices": [{"message": {"content": "video shows motion"}}]})
            response = await session.post(
                f"{base}/v1/chat/completions",
                json={"messages": [{"role": "user", "content": [
                    {"type": "text", "text": "what happens"},
                    {"type": "video_url", "video_url": {"url": data_url("video/mp4", mp4_bytes())}},
                ]}]},
            )
            body = await response.json()
            video_snapshot = link.calls[-1]["attachments"]
            check("video request is handled", body["choices"][0]["message"]["content"] == "video shows motion")
            check("video bytes are handed to the offline link", len(video_snapshot) == 1 and video_snapshot[0]["manifest"]["kind"] == "video")

            link.queue_response({"choices": [{"message": {"content": "streamed answer"}}]})
            link.delay = 0.25
            bot.KEEPALIVE_SECONDS = 0.05
            response = await session.post(
                f"{base}/v1/chat/completions",
                json={"stream": True, "messages": [{"role": "user", "content": "stream please"}]},
            )
            raw = await response.text()
            frames = [line[6:] for line in raw.splitlines() if line.startswith("data: ") and line != "data: [DONE]"]
            joined = "".join(json.loads(frame)["choices"][0]["delta"].get("content", "") for frame in frames)
            check("streaming carries the answer", joined == "streamed answer", joined)
            check("streaming emits keep-alive while waiting", ": keep-alive" in raw)
            check("streaming ends with done", raw.rstrip().endswith("[DONE]"))
            link.delay = 0.0
            bot.KEEPALIVE_SECONDS = 15.0

            link.queue_response({"content": '{"text": "halo dunia"}'})
            form = aiohttp.FormData()
            form.add_field("file", wav_bytes(), filename="clip.wav", content_type="audio/wav")
            response = await session.post(f"{base}/v1/audio/transcriptions", data=form)
            body = await response.json()
            check("transcription unwraps text", body.get("text") == "halo dunia", json.dumps(body))

            link.queue_response({"content": '{"text": "hello world"}'})
            form = aiohttp.FormData()
            form.add_field("file", wav_bytes(), filename="clip.wav", content_type="audio/wav")
            response = await session.post(f"{base}/v1/audio/translations", data=form)
            body = await response.json()
            check("translation unwraps text", body.get("text") == "hello world", json.dumps(body))

            response = await session.post(f"{base}/v1/audio/speech", json={"input": "hi"})
            check("speech reports unavailable", response.status == 501)

            response = await session.post(f"{base}/v1/chat/completions", json={"messages": []})
            check("empty messages are rejected", response.status == 400)

            response = await session.post(
                f"{base}/v1/chat/completions",
                json={"messages": [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "ftp://invalid/file.png"}}]}]},
            )
            check("unsupported media URL is rejected", response.status == 400)

            saved_cap = bot.MEDIA_MAX_BYTES
            bot.MEDIA_MAX_BYTES = 1024
            big = b"x" * 2048
            response = await session.post(
                f"{base}/v1/chat/completions",
                json={"messages": [{"role": "user", "content": [{"type": "input_audio", "input_audio": {"data": base64.b64encode(big).decode(), "format": "wav"}}]}]},
            )
            bot.MEDIA_MAX_BYTES = saved_cap
            check("oversized media is rejected", response.status == 413)

            response = await session.post(
                f"{base}/v1/chat/completions",
                json={"modalities": ["text", "audio"], "messages": [{"role": "user", "content": "speak"}]},
            )
            check("audio output requests are rejected", response.status == 400)
        finally:
            await session.close()
            await stop_server(bridge, runner)

    failed = [row for row in checks if not row[1]]
    print()
    print(f"{len(checks)} checks ran with {len(failed)} failure(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
