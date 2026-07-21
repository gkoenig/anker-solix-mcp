# Anker Solix MCP Server

[![CI](https://github.com/gkoenig/anker-solix-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/gkoenig/anker-solix-mcp/actions/workflows/ci.yml)
[![Security](https://github.com/gkoenig/anker-solix-mcp/actions/workflows/security.yml/badge.svg)](https://github.com/gkoenig/anker-solix-mcp/actions/workflows/security.yml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

An [MCP](https://modelcontextprotocol.io) (Model Context Protocol) server that
exposes data from an Anker Solix solar setup — Solarbank, expansion battery
packs, and Smartmeter — as tools an LLM agent (Claude Desktop, Claude Code, or
any other MCP host) can call directly. Ask things like *"how much solar power
are we producing right now?"* or *"what's the battery state of charge?"* and
have the assistant fetch live numbers instead of you opening the Anker app.

Built against and tested with a **Solarbank 2 E1600 Pro** + **1600 expansion
battery pack** + **Anker Smartmeter**, but the tools are written generically
enough to work with any Solix devices linked to your Anker account.

> ⚠️ **Unofficial.** This project talks to Anker's cloud API via the
> reverse-engineered, community-maintained
> [`anker-solix-api`](https://github.com/thomluther/anker-solix-api) library
> (the same one behind the [Home Assistant Anker Solix
> integration](https://github.com/thomluther/anker-solix-ha)). It is not
> affiliated with or endorsed by Anker Innovations, and Anker can change their
> API at any time and break this.

---

## Contents

- [How this fits together](#how-this-fits-together)
- [Repository structure](#repository-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the server standalone](#running-the-server-standalone)
- [Connecting to an MCP client](#connecting-to-an-mcp-client)
- [Running over HTTP](#running-over-http)
- [Available tools](#available-tools)
- [Design notes](#design-notes)
- [Development](#development)
- [Continuous integration & security](#continuous-integration--security)
- [Extending](#extending)

---

## How this fits together

MCP (Model Context Protocol) is a small, open protocol for connecting an LLM
application ("host", e.g. Claude Desktop or Claude Code) to external tools and
data. The pieces:

- **MCP host** — the chat application (Claude Desktop, Claude Code, etc). It
  reads the model's requests to call a tool, invokes the tool, and feeds the
  result back into the conversation.
- **MCP server** — *this project*. A small program that declares a set of
  **tools** (name, description, input schema, and an implementation) and
  speaks the MCP protocol over a transport.
- **Transport** — how the host and server talk. This server supports two:
  - **stdio** (the default) — the host launches it as a subprocess and
    exchanges JSON-RPC messages over its stdin/stdout. No network port, no
    auth handshake, the host manages the process lifecycle. This is what you
    want for Claude Desktop/Claude Code on the same machine (see
    [Connecting to an MCP client](#connecting-to-an-mcp-client)).
  - **streamable-http** — the server instead listens on a TCP port and
    speaks MCP over HTTP (with SSE for streaming responses), so it can run as
    a long-lived, independently-deployed service that one or more remote MCP
    hosts connect to (see [Running over HTTP](#running-over-http)).

```
┌─────────────────┐   JSON-RPC over stdio   ┌───────────────────────┐   HTTPS   ┌──────────────┐
│  MCP host        │ ─────────────────────▶ │  anker-solix-mcp       │ ────────▶ │ Anker cloud   │
│ (Claude Desktop,  │ ◀───────────────────── │  (this server, a       │ ◀──────── │ API           │
│  Claude Code, …)  │   tool calls/results    │  subprocess)           │  data     │ (unofficial)  │
└─────────────────┘                         └───────────────────────┘           └──────────────┘
```

Within the server, each **tool** is just a Python `async` function decorated
with `@mcp.tool()`. The [official Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk)'s
`FastMCP` class turns the function's type hints and docstring into the JSON
schema and description the model sees — you write plain Python, the protocol
plumbing (schema generation, JSON-RPC framing, transport) is handled for you.

## Repository structure

```
anker-solix-mcp/
├── pyproject.toml            # package metadata, dependencies, console-script entry point
├── uv.lock                    # locked, reproducible dependency versions (uv-managed, committed)
├── .python-version             # pins the interpreter uv uses/installs for this project (3.12)
├── .env.example               # template for Anker account credentials
├── .github/
│   ├── workflows/
│   │   ├── ci.yml              # lint (ruff) + type check (pyright) + test (pytest), every push
│   │   └── security.yml        # pip-audit (dependency CVEs) + CodeQL, every push + weekly
│   └── dependabot.yml         # weekly version-update PRs (Python deps + GitHub Actions)
├── src/
│   └── anker_solix_mcp/
│       ├── server.py          # builds the FastMCP app, registers tool modules, runs stdio or HTTP transport
│       ├── _dev.py            # module-level `mcp` object for `uv run mcp dev` (MCP Inspector) only
│       ├── config.py          # loads Settings (credentials, refresh interval, transport) from the environment
│       ├── client.py          # AnkerSolixClient: lazy auth + refresh-throttled wrapper around AnkerSolixApi
│       ├── http_auth.py       # BearerTokenMiddleware: static-token gate for the HTTP transports
│       ├── util.py            # sanitize() (credential redaction), filter_devices() (heuristic type filter)
│       └── tools/
│           ├── sites.py       # list_sites, get_site_overview
│           ├── devices.py     # list_devices, get_device
│           ├── solarbank.py   # list_solarbanks, get_solarbank_status, get_solarbank_schedule
│           ├── smartmeter.py  # list_smartmeters, get_smartmeter_status
│           ├── energy.py      # get_energy_statistics, get_energy_analysis
│           └── maintenance.py # refresh_data, get_account_info
└── tests/
    ├── test_util.py           # redaction / filtering unit tests
    ├── test_http_auth.py      # BearerTokenMiddleware accept/reject cases
    └── test_server.py         # smoke-tests the assembled server against a fake client (no network)
```

Each `tools/*.py` module exposes one `register(mcp, client) -> None` function
that attaches its tools to the shared `FastMCP` instance, closing over a
shared `AnkerSolixClient`. `server.py` is just the assembly point — this
keeps each domain's tools in one place and makes it easy to add a new file
for a new domain (see [Extending](#extending)).

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) — used for everything (dependency
  management, virtualenv creation, running the server and tests). Install it
  with `curl -LsSf https://astral.sh/uv/install.sh | sh` or see the [uv install
  docs](https://docs.astral.sh/uv/getting-started/installation/).
- An Anker account with at least one Solix system registered in the Anker app.
- **Nothing else** — you don't need Python preinstalled. This project pins
  Python **3.12** (required by the upstream `anker-solix-api` library) via
  `.python-version`/`requires-python`, and `uv` will transparently download
  that exact interpreter the first time you run a `uv` command here if it's
  not already on your machine.

## Installation

```bash
git clone <this-repo-url> anker-solix-mcp
cd anker-solix-mcp
uv sync
```

`uv sync` reads `pyproject.toml` + the committed `uv.lock`, downloads Python
3.12 if needed, creates a project-local `.venv/`, and installs every
dependency (including the dev-only ones like `pytest`, from the `dev`
dependency group) at the exact locked versions. Nothing needs activating —
every command below is run through `uv run ...`, which transparently uses
that `.venv`.

`anker-solix-api` isn't published on PyPI, so it's pulled straight from its
GitHub repo (see the `anker-solix-api @ git+https://...` entry in
`pyproject.toml`, pinned to a commit in `uv.lock`) — `uv` supports Git
dependencies natively, no extra configuration needed.

If you ever change a dependency in `pyproject.toml` by hand, run `uv lock` to
update `uv.lock` to match (or use `uv add <package>` / `uv remove <package>`,
which update both files for you in one step).

## Configuration

Copy the example env file and fill in your Anker account credentials (the
same ones you use to log into the Anker mobile app):

```bash
cp .env.example .env
$EDITOR .env
```

| Variable                | Required | Description                                                                 |
| ----------------------- | -------- | ----------------------------------------------------------------------------|
| `ANKER_EMAIL`           | yes      | Anker account email                                                         |
| `ANKER_PASSWORD`        | yes      | Anker account password                                                      |
| `ANKER_COUNTRY`         | no       | Two-letter country code used at signup (default `DE`)                      |
| `ANKER_REFRESH_SECONDS` | no       | Minimum seconds between automatic data refreshes (default `60`)            |
| `ANKER_SITE_ID`         | no       | Default site ID, if you have more than one Anker Solix system              |
| `ANKER_MCP_TRANSPORT`   | no       | `stdio` (default), `streamable-http`, or `sse`. See [Running over HTTP](#running-over-http) |
| `ANKER_MCP_HOST`        | no       | Bind address for HTTP transports (default `127.0.0.1`)                     |
| `ANKER_MCP_PORT`        | no       | Bind port for HTTP transports (default `8000`)                             |
| `ANKER_MCP_PATH`        | no       | HTTP path the MCP endpoint is mounted at (default `/mcp`)                  |
| `ANKER_MCP_AUTH_TOKEN`  | no       | Bearer token required on every HTTP request. Strongly recommended for any HTTP transport not bound to `127.0.0.1`; see [Running over HTTP](#running-over-http) |

Credentials are only ever read from the environment/`.env` file and used to
authenticate against Anker's own API — nothing is sent anywhere else. Tool
outputs are also passed through a redaction step (see [Design
notes](#design-notes)) so tokens/passwords can't leak into a conversation
even if they show up in a raw API response.

**Never commit your `.env` file.** It's already listed in `.gitignore`.

## Running the server standalone

Before wiring this into an MCP host, it's worth checking it actually talks to
your account. The MCP Python SDK ships an inspector UI for exactly this:

```bash
uv run mcp dev src/anker_solix_mcp/_dev.py
```

This opens the **MCP Inspector** in your browser, where you can call each
tool by hand and see the raw JSON it returns. It points at `_dev.py` rather
than `server.py` because the `mcp dev` CLI needs a module-level `FastMCP`
object to introspect, and `server.py` deliberately doesn't build one at
import time (`build_server()` takes an explicit client; `main()` only
constructs one after loading `Settings`) — that's what keeps importing
`server.py` free of any credential/network requirement, e.g. for the test
suite. `_dev.py` is the one place that trades that off for the Inspector's
sake, so it still needs `ANKER_EMAIL`/`ANKER_PASSWORD` set.

Alternatively, just run the server directly (it will sit waiting for stdio
input, which is expected):

```bash
uv run anker-solix-mcp
```

## Connecting to an MCP client

Clone the repo to a local folder once, then point each MCP client at that
checkout:

```bash
mkdir -p ~/src
cd ~/src
git clone https://github.com/gkoenig/anker-solix-mcp.git
cd anker-solix-mcp
uv sync
```

### Claude Code

Use that local path in Claude Code's MCP settings:

```bash
claude mcp add anker-solix -- uv --directory ~/src/anker-solix-mcp run anker-solix-mcp
```

Or add it by hand to your Claude Code MCP settings:

```json
{
  "mcpServers": {
    "anker-solix": {
      "command": "uv",
      "args": ["--directory", "~/src/anker-solix-mcp", "run", "anker-solix-mcp"]
    }
  }
}
```

### Claude Desktop

Use the same local checkout in `claude_desktop_config.json` (Settings →
Developer → Edit Config), then restart Claude Desktop.

### Cline

Cline stores MCP servers in `cline_mcp_settings.json`, using the same
`mcpServers` shape as the other clients here. Add the server entry there and
replace the path with your local checkout:

```json
{
  "mcpServers": {
    "anker-solix": {
      "command": "uv",
      "args": ["--directory", "~/src/anker-solix-mcp", "run", "anker-solix-mcp"]
    }
  }
}
```

Save the file, reload Cline, and ask it to call tools like "list my sites"
or "show solarbank status".

### Any other MCP host

Any host that can launch a local process and speak MCP-over-stdio can use
this server — point it at `uv run anker-solix-mcp` (or the equivalent
`python -m anker_solix_mcp` inside the project's virtualenv) with the working
directory set to this repo (or `ANKER_EMAIL`/`ANKER_PASSWORD`/etc. exported
directly in the host's environment instead of a `.env` file).

## Running over HTTP

Everything above assumes **stdio**: the MCP host runs on the same machine and
launches this server itself. If instead you want to run the server as a
standalone, long-lived service — e.g. on a home server/NAS/Raspberry Pi near
your network, with one or more MCP hosts (a laptop, a phone client, several
people) connecting to it remotely — use the **streamable-http** transport
instead.

### Starting it

```bash
ANKER_MCP_TRANSPORT=streamable-http \
ANKER_MCP_HOST=127.0.0.1 \
ANKER_MCP_PORT=8000 \
ANKER_MCP_AUTH_TOKEN=$(openssl rand -hex 32) \
  uv run anker-solix-mcp
```

Or set the same variables in your `.env` file (see `.env.example`) — note
`ANKER_MCP_AUTH_TOKEN` needs to be a fixed value there, not regenerated each
run, since clients need to know it. The process now behaves like a normal
web server: it stays running, logs to stderr, and listens on
`http://<host>:<port><path>` (default path `/mcp`) until you stop it
(Ctrl+C or `SIGTERM` — the Anker API session is closed cleanly on shutdown).

Point an HTTP-capable MCP client at that URL, passing the token as a bearer
header, e.g. for Claude Code:

```bash
claude mcp add --transport http anker-solix http://127.0.0.1:8000/mcp \
  --header "Authorization: Bearer <the ANKER_MCP_AUTH_TOKEN value>"
```

or in a client's MCP settings JSON:

```json
{
  "mcpServers": {
    "anker-solix": {
      "type": "http",
      "url": "http://127.0.0.1:8000/mcp",
      "headers": {
        "Authorization": "Bearer <the ANKER_MCP_AUTH_TOKEN value>"
      }
    }
  }
}
```

For Cline, this same file works: keep using `mcpServers`, but switch the
entry to the HTTP shape above when you run the server with
`ANKER_MCP_TRANSPORT=streamable-http`. For local stdio use, keep the
Cline-specific entry from [Connecting to an MCP client](#connecting-to-an-mcp-client).

### What changes vs. stdio, and what to consider

Moving from stdio to HTTP turns this from "a subprocess only the host that
launched it can see" into "a network service" — several things that stdio
gave you for free now become your responsibility:

- **Exposure / access control.** Anyone who can reach the port can call every
  tool here — read-only, but that still means your Solix site/device data
  and Anker account info (see [Available tools](#available-tools)) are
  readable by whoever connects. Set `ANKER_MCP_AUTH_TOKEN` (see
  [Configuration](#configuration)) to require a matching
  `Authorization: Bearer <token>` header on every request —
  `anker_solix_mcp.http_auth.BearerTokenMiddleware` rejects anything else
  with `401`. This is a deliberately simple static-token check, not full
  OAuth: `mcp[cli]`'s `FastMCP` does support plugging in a real
  `TokenVerifier`/OAuth provider (`FastMCP(auth=...)`), but that requires
  standing up OAuth protected-resource metadata (an `issuer_url`, discovery
  endpoints, ...) — overkill for a single-account personal server. If you
  need that flow (e.g. multiple distinct users/identities, token expiry,
  scopes), swap in a real `TokenVerifier` instead of `ANKER_MCP_AUTH_TOKEN`.
  Without the token set, the server logs a startup warning and accepts
  unauthenticated requests — only acceptable on loopback or an
  already-trusted network (see below).
- **Recommended: keep it off the public internet.** A bearer token guards
  the endpoint, but it's still sent as plain HTTP unless something adds TLS
  (see below) — layer on network-level protection too:
  1. **Loopback only** (`ANKER_MCP_HOST=127.0.0.1`, the default) if the MCP
     host runs on the same machine — gets you nothing over stdio, so prefer
     stdio in that case.
  2. **Private network / VPN** — bind to your LAN interface (or `0.0.0.0`)
     but only reach it over a VPN you control (Tailscale, WireGuard) or your
     home LAN, never a port forwarded to the public internet.
  3. **Reverse proxy in front** (Caddy, nginx, Traefik) if you do need
     access from outside your network: terminate TLS there (streamable-http
     has no TLS of its own) — keep `ANKER_MCP_AUTH_TOKEN` set either way, so
     the token and TLS cover different risks (who's allowed vs. is the
     traffic readable in transit).
- **Single process, not a fleet.** `AnkerSolixClient` throttles refreshes
  and authenticates lazily using in-process state (an `asyncio.Lock` and a
  last-refresh timestamp — see `client.py`). That only works correctly
  within one process: don't run multiple `uv run anker-solix-mcp` instances
  or a multi-worker server (e.g. `uvicorn --workers N`) in front of the same
  Anker account, or the refresh throttle stops meaning anything and you risk
  hammering Anker's API from several unsynchronized processes at once. One
  process comfortably serves many concurrent MCP clients/sessions.
- **Keep it running.** Unlike stdio (where the host starts/stops the
  process for you), you're now responsible for the process lifecycle:
  run it under a process supervisor — a `systemd` user/system service, a
  Docker container with `restart: unless-stopped`, `tmux`/`screen` for a
  quick manual setup — so it survives reboots and crashes and its logs (it
  logs to stderr) go somewhere you can check.
- **Credentials still come from the environment.** Nothing changes here —
  `ANKER_EMAIL`/`ANKER_PASSWORD`/etc. are still read once at process start
  (from the environment or `.env` in the working directory). Make sure
  whatever supervises the process sets them the same way you would for
  stdio; there's no per-request credential handling to worry about since
  this is still a single-account tool, not a multi-tenant service.
- **`sse` transport** is also available (`ANKER_MCP_TRANSPORT=sse`) for
  older MCP clients that predate streamable-http, but it's deprecated in the
  MCP spec — prefer `streamable-http` unless you specifically need it.

## Available tools

| Tool                     | Description                                                                                       |
| ------------------------ | --------------------------------------------------------------------------------------------------|
| `list_sites`              | List every Anker power system ("site") on the account, keyed by site ID.                          |
| `get_site_overview`       | Full cached detail record for one site (power-flow summary, if reported).                         |
| `list_devices`            | List every device (Solarbank, expansion pack, Smartmeter, …) keyed by serial number.               |
| `get_device`              | Full, unfiltered cached detail record for one device.                                              |
| `list_solarbanks`         | Devices that look like Solarbanks / expansion battery packs.                                       |
| `get_solarbank_status`    | Battery SoC, solar input, output power, charge/discharge power, temperature, etc.                  |
| `get_solarbank_schedule`  | The configured charge/discharge schedule / output-power plan, if present.                          |
| `list_smartmeters`        | Devices that look like Anker Smartmeters.                                                          |
| `get_smartmeter_status`   | Current grid import/export power and other reported fields.                                        |
| `get_energy_statistics`   | Fresh (non-cached) energy totals: production, charge/discharge, grid import/export, home usage.    |
| `get_energy_analysis`     | Time-series energy breakdown for a site (day/week/month/year); `range_type="day"` returns intraday (~20-min) points for sub-daily queries like night-time usage. |
| `refresh_data`            | Force an immediate refresh of all cached data, bypassing the throttle.                             |
| `get_account_info`        | Basic Anker account info (nickname, etc.), credentials redacted.                                   |

All tools are **read-only** — none of them changes a device setting. That's a
deliberate scope choice (see [Design notes](#design-notes) and
[Extending](#extending) if you want to add control tools yourself).

## Design notes

**Why tools return mostly raw, pass-through data.** `anker-solix-api` talks to
an undocumented private API — its cached data's exact shape varies by device
model and firmware, and can change without notice. Rather than hardcoding
field names that might not match your specific setup (and silently dropping
data that doesn't fit an assumed schema), most tools return the underlying
library's cached dict close to as-is, scoped to the relevant site/device.
Modern LLMs are good at reading arbitrary JSON and picking out the field the
user asked about, so this trades a bit of "raw JSON in the transcript" for
resilience against upstream schema drift. `list_solarbanks` /
`list_smartmeters` apply a best-effort heuristic filter (matching known model
codes / type strings) but fall back to returning everything if nothing
matches, rather than silently returning an empty result.

**Redaction.** Every tool response is passed through `util.sanitize()`, which
recursively redacts any dict key that looks like a credential (`password`,
`token`, `secret`, `cookie`, `auth_*`, …) before it's returned. This is
defense-in-depth on top of never printing credentials directly — the account
cache in particular could plausibly carry session-related fields.

**Refresh throttling.** `AnkerSolixClient.refresh()` is throttled to
`ANKER_REFRESH_SECONDS` (default 60s) so a burst of tool calls within one
conversation turn costs a single round trip to Anker's API, not one per tool.
`get_energy_statistics`, `get_energy_analysis` and `refresh_data` intentionally bypass the throttle,
since "give me the latest number" is the most common reason to call them.

**Lazy authentication.** The Anker API client and its HTTP session are only
created on first use (inside `AnkerSolixClient._ensure_api`), not at import
time — so importing the server module, or running its test suite, never
makes a network call or requires credentials to be present.

## Development

```bash
uv sync            # dev dependency group (pytest, pytest-asyncio, ruff, pyright, pip-audit) is included by default
uv run pytest
uv run ruff check .          # lint
uv run ruff format .         # format (add --check to only verify, e.g. in CI)
uv run pyright               # type check
```

`tests/test_server.py` builds the MCP server against a small fake client (see
`FakeAnkerSolixClient`), so the test suite runs with no Anker credentials and
no network access. `tools/*.py` and `build_server()` take the client as
`AnkerSolixClientProtocol` (see `client.py`) rather than the concrete
`AnkerSolixClient` specifically so that duck-typed stand-in type-checks too.

To add or upgrade a dependency, prefer `uv add <package>` (or `uv add --group
dev <package>` for a dev-only tool) over hand-editing `pyproject.toml` — it
resolves and updates `uv.lock` for you in the same step. Run `uv lock
--upgrade` occasionally to pick up new compatible versions, including a newer
commit of `anker-solix-api` if the upstream library has moved on.

## Continuous integration & security

Every push, on every branch, runs three GitHub Actions jobs
([`.github/workflows/ci.yml`](.github/workflows/ci.yml)):

| Job        | Command                                          |
| ---------- | ------------------------------------------------- |
| Lint       | `uv run ruff check .` + `uv run ruff format --check .` |
| Type check | `uv run pyright`                                   |
| Test       | `uv run pytest`                                    |

Security scanning runs on every push plus a weekly schedule
([`.github/workflows/security.yml`](.github/workflows/security.yml)):

- **`pip-audit`** — checks every resolved dependency version (from the locked
  environment) against known CVE databases.
- **CodeQL** — GitHub's static analysis, scanning this project's own Python
  source for security-relevant bug patterns (separate from dependency CVEs).

[`.github/dependabot.yml`](.github/dependabot.yml) additionally opens PRs for
version updates on a weekly schedule, for both Python dependencies (`uv`
ecosystem) and the GitHub Actions used in the workflows themselves. Note that
`anker-solix-api` is a git dependency with no fixed tag, so Dependabot can
version-bump every other dependency here but not that one specifically —
re-run `uv lock --upgrade` periodically to pick up newer commits of it.

## Extending

To add a new tool:

1. Add an `async def` function to an existing `tools/*.py` module (or create
   a new module for a new domain), decorated with `@mcp.tool()` inside that
   module's `register(mcp, client)` function.
2. Write a clear docstring — the MCP client (and, in turn, the model) sees it
   as the tool's description, so be explicit about what the tool returns and
   when to call it.
3. If it's a new module, register it in `build_server()` in `server.py`.
4. Add a test in `tests/` using `FakeAnkerSolixClient` (extend it if your tool
   needs data the fake doesn't provide yet).

To add a **device-control** tool (e.g. changing the Solarbank's output power
or charge schedule via `AnkerSolixApi.set_station_parm` /
`set_device_attributes`), consider gating it behind explicit user
confirmation in your MCP host, since unlike the read-only tools here, a
mistaken call would actually change how your hardware behaves.
