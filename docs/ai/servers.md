# `servers.py`

Local model servers: discovery, launching, stopping and thread housekeeping.

Ollama and MLX run on this machine. These helpers find what they serve,
start an MLX server for a cached model, stop the servers the app started, and
keep Qt threads alive until they have really finished.

---

## Constants

| Name | Value |
|------|-------|
| `OLLAMA_BASE` | `'http://127.0.0.1:11434'` |
| `OLLAMA_CHAT` | `f'{OLLAMA_BASE}/api/chat'` |
| `OLLAMA_TAGS` | `f'{OLLAMA_BASE}/api/tags'` |
| `MLX_BASE` | `'http://127.0.0.1:8080'` |
| `MLX_CHAT` | `f'{MLX_BASE}/v1/chat/completions'` |
| `MLX_MODELS` | `f'{MLX_BASE}/v1/models'` |
| `PROBE_TIMEOUT` | `4.0` |
| `PROBE_ATTEMPTS` | `3` |
| `PROBE_RETRY_GAP` | `2.0` |
| `_LOCAL_HOST_ALIASES` | `('localhost', '127.0.0.1', '[::1]', '::1', '0.0.0.0')` |
| `_LAUNCHED_SERVERS` | `[]` |
| `_RETIRED_THREADS` | `[]` |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `local_session` | `()` | Return a requests session that ignores environment proxy settings. |
| `local_get` | `(url, timeout=PROBE_TIMEOUT, headers=None)` | GET a local URL without going through any configured proxy. |
| `host_variants` | `(base_url)` | Yield the loopback spellings worth trying for a local server URL. |
| `fetch_ollama_model_context` | `(model, base_url=OLLAMA_BASE, timeout=PROBE_TIMEOUT)` | Ask Ollama how large a context window a model actually supports. |
| `register_launched_server` | `(proc)` | Track a model server this app started so it can be stopped on exit. |
| `shutdown_launched_servers` | `(timeout=6)` | Stop every model server this app started. |
| `install_server_shutdown_hooks` | `()` | Register app-exit hooks that stop servers this app started. |
| `unload_ollama_model` | `(model, base_url=OLLAMA_BASE, timeout=10)` | Ask Ollama to drop a model from memory immediately. |
| `pids_listening_on` | `(port)` | Return the process ids listening on a TCP port. |
| `port_of` | `(url, default=8080)` | Extract the TCP port from a base URL. |
| `terminate_pids` | `(pids, timeout=6)` | Terminate processes by id, escalating to kill when they do not exit. |
| `park_thread` | `(thread)` | Hold a reference to a thread until Qt reports it finished. |
| `_unpark_thread` | `(thread)` | Drop a parked thread once it has finished running. |
| `retire_thread` | `(thread, grace=8000)` | Stop a QThread and keep it alive until it has really finished. |
| `hf_cache_roots` | `()` | Return the Hugging Face cache directories that exist on this machine. |
| `discover_cached_mlx_models` | `()` | Find MLX-ready models already downloaded into the local model cache. |
| `mlx_server_command` | `(model, port)` | Build the command that starts an MLX server for a model. |
| `discover_local_models` | `(mlx_host=MLX_BASE)` | Collect every model this machine can serve without further setup. |
| `fetch_ollama_models` | `(base_url=OLLAMA_BASE, timeout=PROBE_TIMEOUT)` | List the models installed in a running Ollama server. |
| `fetch_openai_models` | `(base_url, timeout=PROBE_TIMEOUT, api_key='')` | List models advertised by an OpenAI-compatible ``/v1/models`` endpoint. |
