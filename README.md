<div align="center">

<img width="100%" alt="header" src="https://capsule-render.vercel.app/api?type=waving&height=210&text=Cue%20Bridge%20Bot&fontAlign=50&fontAlignY=36&fontSize=56&desc=OpenAI-Compatible%20Local%20Bridge%20for%20Cue%20AI&descAlign=50&descAlignY=58"/>

<img alt="typing" src="https://readme-typing-svg.demolab.com?font=Inter&size=18&duration=3000&pause=650&center=true&vCenter=true&width=900&lines=OpenAI-Compatible+HTTP+Bridge;Text+%7C+Image+%7C+Audio+%7C+Video+%7C+File+Input;Streaming+and+Non-Streaming+Support;API+Key+Management+%7C+Request+Queue;Systemd+Service+%7C+Multi-Client"/>

<p>
  <img alt="python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white"/>
  <img alt="api" src="https://img.shields.io/badge/API-OpenAI%20Compatible-111111"/>
  <img alt="multimodal" src="https://img.shields.io/badge/Input-Multimodal-111111"/>
  <img alt="author" src="https://img.shields.io/badge/by-Yuurisandesu-111111"/>
</p>

<p>
  <b>Cue Bridge</b> is a local OpenAI-compatible HTTP bridge for Cue AI.<br/>
  It exposes a standard API server on port 1234 that accepts text, image, audio, video, and file input through <code>/v1/chat/completions</code>, with both streaming and non-streaming responses, plus audio transcription and translation endpoints, API key management via a JSON key file, and a request queue to handle concurrent clients, all packaged with a systemd service unit for persistent deployment.<br/>
  Built and distributed by <b>Yuurisandesu</b>.
</p>

</div>

---

## Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Bridge](#running-the-bridge)
- [Connecting a Client](#connecting-a-client)
- [Running as a Service](#running-as-a-service)
- [Features](#features)
- [File Structure](#file-structure)
- [Disclaimer](#disclaimer)

---

## Requirements

- Python 3.10 or later
- pip
- Git

---

## Installation

### Install Python

**Windows:**

1. Download the installer from https://www.python.org/downloads/ and run it
2. On the first screen tick **Add python.exe to PATH**, then continue with the default options
3. Open Command Prompt and verify:

```cmd
python --version
```

**Linux (Ubuntu / Debian):**

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip
python3 --version
```

**macOS:**

```bash
brew install python
python3 --version
```

> If you do not have Homebrew, install it first from https://brew.sh

**Termux (Android):**

```bash
pkg update && pkg upgrade -y
pkg install python git -y
python --version
```

---

### Clone and Install

**Clone the repository:**

```bash
git clone https://github.com/Yuurisan-N1/Cue-Bridge.git
cd Cue-Bridge
```

**Install dependencies:**

```bash
pip install aiohttp python-dotenv
```

---

## Configuration

Copy the example env file and fill in the values:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|---|---|---|
| `SESSION_PATH` | `session/wrapper` | Path to the session file |
| `HOST` | `127.0.0.1` | Address the server binds to |
| `PORT` | `1234` | Port the server listens on |
| `PUBLIC_URL` | _(empty)_ | Public base URL shown in `/v1/models` |
| `MODEL_ID` | `yuuri-gemini-3-flash` | Model name reported by the bridge |
| `MODEL_ALIASES` | `yuuri-3.2-flash` | Comma-separated aliases accepted as the model name |
| `API_KEY` | _(empty)_ | Single static API key; leave empty to use `keys.json` instead |
| `KEYS_FILE` | `keys.json` | Path to the JSON key list when using multiple keys |
| `KEY_PREFIX` | `sk-yuuri-` | Prefix used when generating new keys |
| `QUEUE_MAX` | `8` | Maximum number of requests held in the queue at once |
| `QUEUE_TIMEOUT` | `300` | Seconds a queued request waits before being rejected |
| `REPLY_TIMEOUT` | `180` | Seconds the bridge waits for a reply before returning an error |
| `KEEPALIVE_SECONDS` | `15` | Interval between keep-alive comments in streaming responses |
| `MEDIA_MODE` | `album` | How media files are sent: `album` groups them, `single` sends one at a time |
| `MEDIA_MAX_MB` | `18` | Maximum size in MB for a single attached file |
| `MAX_ATTACHMENTS` | `8` | Maximum number of files allowed in one request |
| `FETCH_TIMEOUT` | `30` | Seconds allowed when downloading a media URL |
| `TEXT_QUIET` | `4` | Seconds to wait after a text message before reading the reply |

### API Key Management

When `API_KEY` is set in `.env`, that single key is accepted on every request. When it is left empty, the bridge reads from `keys.json`. The key file is a JSON object where each key maps to a label:

```json
{
  "sk-yuuri-abc123": "client-one",
  "sk-yuuri-def456": "client-two"
}
```

Leave both `API_KEY` and `keys.json` empty to run the bridge without authentication.

---

## Running the Bridge

**Linux / macOS:**

```bash
python bot.py
```

**Windows:**

```cmd
python bot.py
```

**Termux (Android):**

```bash
python bot.py
```

Once started the bridge logs a ready line and begins accepting requests on the configured port. Press `Ctrl+C` to stop it cleanly.

**Run in background with screen (Linux / macOS / Termux):**

```bash
screen -S cue-bridge
python bot.py
```

Detach with `Ctrl+A` then `D`. Reattach anytime:

```bash
screen -r cue-bridge
```

---

## Connecting a Client

Point any OpenAI-compatible client at:

```
Base URL : http://127.0.0.1:1234/v1
API Key  : any key from keys.json, or the value of API_KEY, or any string if auth is disabled
Model    : yuuri-gemini-3-flash
```

**curl text example:**

```bash
curl http://127.0.0.1:1234/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-yuuri-abc123" \
  -d '{
    "model": "yuuri-gemini-3-flash",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

**curl streaming example:**

```bash
curl http://127.0.0.1:1234/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-yuuri-abc123" \
  -d '{
    "model": "yuuri-gemini-3-flash",
    "stream": true,
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

**curl image example:**

```bash
curl http://127.0.0.1:1234/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-yuuri-abc123" \
  -d '{
    "model": "yuuri-gemini-3-flash",
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "What is in this image?"},
        {"type": "image_url", "image_url": {"url": "https://example.com/photo.jpg"}}
      ]
    }]
  }'
```

**curl audio transcription example:**

```bash
curl http://127.0.0.1:1234/v1/audio/transcriptions \
  -H "Authorization: Bearer sk-yuuri-abc123" \
  -F model=yuuri-gemini-3-flash \
  -F file=@recording.mp3
```

The bridge works with any client that supports a custom base URL, including Open WebUI, SillyTavern, and Chatbox.

---

## Running as a Service

A systemd unit file is included for persistent deployment on Linux.

**Copy the files to the deployment path:**

```bash
sudo mkdir -p /opt/cue-bridge
sudo cp -r . /opt/cue-bridge
sudo useradd --system --no-create-home cue
sudo chown -R cue:cue /opt/cue-bridge
```

**Create a virtual environment and install dependencies:**

```bash
sudo -u cue python3 -m venv /opt/cue-bridge/.venv
sudo -u cue /opt/cue-bridge/.venv/bin/pip install aiohttp python-dotenv
```

**Install and start the service:**

```bash
sudo cp /opt/cue-bridge/bridge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable cue-bridge
sudo systemctl start cue-bridge
```

**Check the status and tail the log:**

```bash
sudo systemctl status cue-bridge
sudo tail -f /var/log/cue-bridge.log
```

---

## Features

### OpenAI-Compatible API
The bridge exposes a local HTTP server that speaks the OpenAI API format. Any client that accepts a custom base URL works with it without modification.

### Multimodal Input
Requests can carry text, images, audio clips, video clips, and arbitrary files alongside the message content. Files can be passed as inline data URLs, base64-encoded payloads, or remote HTTP URLs. The bridge downloads and prepares each attachment before forwarding the request.

### Streaming and Non-Streaming
Both `stream: true` and `stream: false` are supported. Streaming responses send SSE chunks in the OpenAI delta format and close with a `[DONE]` marker. Keep-alive comments are sent on a configurable interval to prevent proxy timeouts during long responses.

### Audio Transcription and Translation
The `/v1/audio/transcriptions` endpoint returns a verbatim transcript of an audio file in the language it was recorded in. The `/v1/audio/translations` endpoint returns an English translation of the same audio. Both endpoints accept multipart form uploads in the Whisper API shape.

### API Key Management
The bridge supports a single static key via the env file or a list of named keys via a JSON file. Requests without a valid key are rejected with a 401 response. Running without authentication is also supported by leaving both options empty.

### Request Queue
Incoming requests are held in a bounded queue when the bridge is busy. The queue size and the maximum wait time are both configurable. Requests that exceed the timeout are rejected with a 503 response rather than hanging.

### Health and Model Endpoints
`GET /health` returns a 200 response as long as the bridge is running. `GET /v1/models` returns the configured model ID and its aliases in the OpenAI models list format.

### Systemd Service
The included `bridge.service` unit runs the bridge as a dedicated system user with automatic restart on failure, log capture to a file, and no new privileges, ready for deployment on any systemd-based Linux host.

---

## File Structure

```text
Cue-Bridge/
├── tests/
│   ├── cors.py                          # CORS header tests
│   ├── harness.py                       # Test runner and shared fixtures
│   ├── keys_and_queue.py                # API key auth and queue limit tests
│   └── text_reply.py                    # Text completion response tests
├── bot.py                               # Bridge server, API handlers, media pipeline, queue
├── bridge.service                       # Systemd unit file for persistent deployment
├── .env.example                         # Environment variable template
├── requirements.txt                     # Python dependencies
├── LICENSE                              # License file
└── README.md                            # This file
```

---

## Disclaimer

This tool is built for educational and technical exploration purposes. Use it wisely and at your own responsibility.

---

<div align="center">
<img width="100%" alt="footer" src="https://capsule-render.vercel.app/api?type=waving&height=120&section=footer"/>
</div>