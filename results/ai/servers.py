"""Local model servers: discovery, launching, stopping and thread housekeeping.

Ollama and MLX run on this machine. These helpers find what they serve,
start an MLX server for a cached model, stop the servers the app started, and
keep Qt threads alive until they have really finished.
"""
import glob
import logging
import os
import shutil
import subprocess
import sys
import time

import requests

_itk_log = logging.getLogger("IsotopeTrack.results.ai.servers")

OLLAMA_BASE = "http://127.0.0.1:11434"
OLLAMA_CHAT = f"{OLLAMA_BASE}/api/chat"
OLLAMA_TAGS = f"{OLLAMA_BASE}/api/tags"

MLX_BASE = "http://127.0.0.1:8080"
MLX_CHAT = f"{MLX_BASE}/v1/chat/completions"
MLX_MODELS = f"{MLX_BASE}/v1/models"

PROBE_TIMEOUT = 4.0
PROBE_ATTEMPTS = 3
PROBE_RETRY_GAP = 2.0

_LOCAL_HOST_ALIASES = ("localhost", "127.0.0.1", "[::1]", "::1", "0.0.0.0")


def local_session():
    """Return a requests session that ignores environment proxy settings.

    Loopback servers such as Ollama and MLX are unreachable when a system or
    corporate ``HTTP_PROXY`` is exported, because requests would otherwise send
    the request to the proxy instead of the local port.

    Returns:
        requests.Session: Session with ``trust_env`` disabled and proxies off.
    """
    session = requests.Session()
    session.trust_env = False
    session.proxies = {}
    return session


def local_get(url, timeout=PROBE_TIMEOUT, headers=None):
    """GET a local URL without going through any configured proxy.

    Args:
        url (str): Absolute URL to request.
        timeout (float): Per-request timeout in seconds.
        headers (dict): Optional extra request headers.

    Returns:
        requests.Response: The response object.
    """
    with local_session() as session:
        return session.get(url, timeout=timeout, headers=headers)


def host_variants(base_url):
    """Yield the loopback spellings worth trying for a local server URL.

    macOS resolves ``localhost`` to ``::1`` first while Ollama and MLX bind to
    ``127.0.0.1`` only, so a single spelling is not enough to decide the server
    is down.

    Args:
        base_url (str): Base URL such as ``http://localhost:8080``.

    Returns:
        list: Ordered, de-duplicated base URLs to probe.
    """
    base = (base_url or '').strip().rstrip('/')
    if not base:
        return []
    variants = [base]
    for alias in _LOCAL_HOST_ALIASES:
        if f"//{alias}:" in base or base.endswith(f"//{alias}"):
            for replacement in ("127.0.0.1", "localhost"):
                candidate = base.replace(f"//{alias}", f"//{replacement}", 1)
                if candidate not in variants:
                    variants.append(candidate)
            break
    return variants


def fetch_ollama_model_context(model, base_url=OLLAMA_BASE, timeout=PROBE_TIMEOUT):
    """Ask Ollama how large a context window a model actually supports.

    Args:
        model (str): Installed model name, e.g. ``qwen3.8:latest``.
        base_url (str): Ollama base URL.
        timeout (float): Request timeout in seconds.

    Returns:
        int: Context length in tokens, or 0 when it cannot be determined.
    """
    if not model:
        return 0
    for base in host_variants(base_url):
        try:
            with local_session() as session:
                r = session.post(f"{base}/api/show", json={"model": model},
                                 timeout=timeout)
        except Exception:
            continue
        if r.status_code != 200:
            continue
        try:
            info = (r.json() or {}).get('model_info') or {}
        except ValueError:
            continue
        for key, value in info.items():
            if key.endswith('.context_length'):
                try:
                    return int(value)
                except (TypeError, ValueError):
                    continue
    return 0


_LAUNCHED_SERVERS = []


def register_launched_server(proc):
    """Track a model server this app started so it can be stopped on exit.

    Args:
        proc (subprocess.Popen): Running server process.
    """
    if proc is not None:
        _LAUNCHED_SERVERS.append(proc)


def shutdown_launched_servers(timeout=6):
    """Stop every model server this app started.

    Servers the user launched themselves are left untouched, since the app does
    not own them. A terminate is tried first so the model unloads cleanly, then
    a kill if the process ignores it.

    Args:
        timeout (float): Seconds to wait for a clean exit before killing.

    Returns:
        int: Number of processes that were still running and got stopped.
    """
    stopped = 0
    while _LAUNCHED_SERVERS:
        proc = _LAUNCHED_SERVERS.pop()
        try:
            if proc.poll() is not None:
                continue
            proc.terminate()
            stopped += 1
            try:
                proc.wait(timeout=timeout)
            except Exception:
                proc.kill()
        except Exception:
            _itk_log.exception("Handled exception stopping a launched server")
    if stopped:
        _itk_log.info("Stopped %d model server(s) started by the app", stopped)
    return stopped


def install_server_shutdown_hooks():
    """Register app-exit hooks that stop servers this app started."""
    try:
        import atexit
        atexit.register(shutdown_launched_servers)
    except Exception:
        _itk_log.exception("Handled exception registering atexit hook")
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None and not getattr(app, '_itk_ai_shutdown_hooked', False):
            app.aboutToQuit.connect(shutdown_launched_servers)
            app._itk_ai_shutdown_hooked = True
    except Exception:
        _itk_log.exception("Handled exception connecting aboutToQuit hook")


def unload_ollama_model(model, base_url=OLLAMA_BASE, timeout=10):
    """Ask Ollama to drop a model from memory immediately.

    Ollama keeps a model resident for several minutes after the last request.
    Sending an empty generate call with ``keep_alive`` set to zero evicts it and
    frees the RAM straight away.

    Args:
        model (str): Model name to unload.
        base_url (str): Ollama base URL.
        timeout (float): Request timeout in seconds.

    Returns:
        bool: True when the server accepted the unload.
    """
    if not model:
        return False
    for base in host_variants(base_url):
        try:
            with local_session() as session:
                r = session.post(f"{base}/api/generate",
                                 json={"model": model, "keep_alive": 0},
                                 timeout=timeout)
            if r.status_code == 200:
                return True
        except Exception:
            continue
    return False


def pids_listening_on(port):
    """Return the process ids listening on a TCP port.

    Args:
        port (int): TCP port number.

    Returns:
        list: Integer process ids, empty when none are found or lsof is absent.
    """
    lsof = shutil.which('lsof')
    if not lsof:
        return []
    try:
        out = subprocess.run([lsof, '-ti', f'tcp:{int(port)}', '-sTCP:LISTEN'],
                             capture_output=True, text=True, timeout=6)
    except Exception:
        _itk_log.exception("Handled exception in pids_listening_on")
        return []
    pids = []
    for line in (out.stdout or '').split():
        try:
            pids.append(int(line))
        except ValueError:
            continue
    return pids


def port_of(url, default=8080):
    """Extract the TCP port from a base URL.

    Args:
        url (str): URL such as ``http://127.0.0.1:8080``.
        default (int): Value to return when no port is present.

    Returns:
        int: Port number.
    """
    try:
        return int((url or '').rstrip('/').rsplit(':', 1)[-1].split('/')[0])
    except (ValueError, AttributeError):
        return default


def terminate_pids(pids, timeout=6):
    """Terminate processes by id, escalating to kill when they do not exit.

    Args:
        pids (list): Process ids to stop.
        timeout (float): Seconds to wait before escalating.

    Returns:
        int: Number of processes that were signalled.
    """
    import signal
    stopped = 0
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
            stopped += 1
        except Exception:
            _itk_log.exception("Handled exception terminating pid %s", pid)
    deadline = time.monotonic() + timeout
    for pid in pids:
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except OSError:
                break
            time.sleep(0.2)
        else:
            try:
                os.kill(pid, signal.SIGKILL)
            except Exception:
                _itk_log.exception("Handled exception killing pid %s", pid)
    return stopped


_RETIRED_THREADS = []


def park_thread(thread):
    """Hold a reference to a thread until Qt reports it finished.

    Clearing the last reference to a QThread that is still running aborts the
    process, and a worker is usually still inside ``run()`` at the moment its
    completion signal reaches the GUI. Parking is cheap and never blocks.

    Args:
        thread (QThread): Thread to keep alive until it finishes.
    """
    if thread is None:
        return
    try:
        if thread.isFinished():
            return
        _RETIRED_THREADS.append(thread)
        thread.finished.connect(lambda t=thread: _unpark_thread(t))
    except Exception:
        _itk_log.exception("Handled exception parking a thread")


def _unpark_thread(thread):
    """Drop a parked thread once it has finished running."""
    try:
        _RETIRED_THREADS.remove(thread)
    except ValueError:
        pass


def retire_thread(thread, grace=8000):
    """Stop a QThread and keep it alive until it has really finished.

    Letting a still-running QThread be garbage collected aborts the process
    ("QThread: Destroyed while thread is still running"), so a thread that
    outlives its grace period is parked in a module-level list rather than
    dropped, and cleaned up once it reports finished.

    Args:
        thread (QThread): Thread to stop.
        grace (int): Milliseconds to wait for a clean exit.

    Returns:
        bool: True when the thread finished within the grace period.
    """
    if thread is None:
        return True
    try:
        if hasattr(thread, 'stop'):
            thread.stop()
        thread.requestInterruption()
    except Exception:
        _itk_log.exception("Handled exception while asking a thread to stop")
    try:
        if thread.wait(grace):
            return True
    except Exception:
        _itk_log.exception("Handled exception waiting for a thread")
        return False
    _itk_log.warning("Thread %s did not stop within %d ms — parking it",
                     type(thread).__name__, grace)
    _RETIRED_THREADS.append(thread)
    for parked in list(_RETIRED_THREADS):
        try:
            if parked.isFinished():
                _RETIRED_THREADS.remove(parked)
        except Exception:
            _RETIRED_THREADS.remove(parked)
    return False


def hf_cache_roots():
    """Return the Hugging Face cache directories that exist on this machine.

    Honours ``HF_HUB_CACHE``, ``HUGGINGFACE_HUB_CACHE`` and ``HF_HOME`` before
    falling back to the default ``~/.cache/huggingface/hub``.

    Returns:
        list: Existing cache directory paths, de-duplicated.
    """
    candidates = []
    for var in ('HF_HUB_CACHE', 'HUGGINGFACE_HUB_CACHE'):
        value = os.environ.get(var)
        if value:
            candidates.append(value)
    hf_home = os.environ.get('HF_HOME')
    if hf_home:
        candidates.append(os.path.join(hf_home, 'hub'))
    candidates.append(os.path.expanduser('~/.cache/huggingface/hub'))
    candidates.append(os.path.expanduser('~/.cache/mlx-lm'))

    roots = []
    for path in candidates:
        full = os.path.abspath(os.path.expanduser(path))
        if full not in roots and os.path.isdir(full):
            roots.append(full)
    return roots


def discover_cached_mlx_models():
    """Find MLX-ready models already downloaded into the local model cache.

    A repository counts as usable when one of its snapshots holds a
    ``config.json`` together with model weights, which is what
    ``mlx_lm.server --model <repo-id>`` needs to start without downloading.

    Returns:
        list: Hugging Face repo ids, MLX community models first.
    """
    found = set()
    for root in hf_cache_roots():
        for entry in glob.glob(os.path.join(root, 'models--*')):
            if not os.path.isdir(entry):
                continue
            repo = os.path.basename(entry)[len('models--'):].replace('--', '/')
            snapshots = os.path.join(entry, 'snapshots')
            if not os.path.isdir(snapshots):
                continue
            for snap in glob.glob(os.path.join(snapshots, '*')):
                has_config = os.path.exists(os.path.join(snap, 'config.json'))
                has_weights = bool(glob.glob(os.path.join(snap, '*.safetensors'))
                                   or glob.glob(os.path.join(snap, '*.npz')))
                if has_config and has_weights:
                    found.add(repo)
                    break
    return sorted(found, key=lambda r: (not r.lower().startswith('mlx-community/'),
                                        r.lower()))


def mlx_server_command(model, port):
    """Build the command that starts an MLX server for a model.

    Prefers the ``mlx_lm.server`` console script and falls back to running the
    module with the interpreter that is currently executing the application.

    Args:
        model (str): Hugging Face repo id or local model path.
        port (int): TCP port to bind.

    Returns:
        list: Argument vector for ``subprocess.Popen``, or an empty list when
        mlx_lm is not installed for this interpreter.
    """
    script = shutil.which('mlx_lm.server')
    if script:
        return [script, '--model', model, '--port', str(port)]
    try:
        import importlib.util
        if importlib.util.find_spec('mlx_lm') is None:
            return []
    except Exception:
        _itk_log.exception("Handled exception in mlx_server_command")
        return []
    return [sys.executable, '-m', 'mlx_lm.server', '--model', model,
            '--port', str(port)]


def discover_local_models(mlx_host=MLX_BASE):
    """Collect every model this machine can serve without further setup.

    Returns:
        list: Entries of ``{'backend', 'model', 'label', 'ready'}`` where
        ``ready`` marks models a server is already serving, as opposed to
        models that are cached on disk but need a server started.
    """
    entries = []
    try:
        for name in fetch_ollama_models()[0]:
            entries.append({'backend': 'ollama', 'model': name,
                            'label': f"Ollama · {name}", 'ready': True})
    except Exception:
        _itk_log.exception("Handled exception collecting Ollama models")
    try:
        for model_id in fetch_openai_models(mlx_host)[0]:
            entries.append({'backend': 'mlx', 'model': model_id,
                            'label': f"MLX (running) · {model_id.split('/')[-1]}",
                            'ready': True})
    except Exception:
        _itk_log.exception("Handled exception collecting MLX server models")
    served = {e['model'] for e in entries if e['backend'] == 'mlx'}
    for repo in discover_cached_mlx_models():
        if repo in served:
            continue
        entries.append({'backend': 'mlx', 'model': repo,
                        'label': f"MLX (cached) · {repo}", 'ready': False})
    return entries


def fetch_ollama_models(base_url=OLLAMA_BASE, timeout=PROBE_TIMEOUT):
    """List the models installed in a running Ollama server.

    Args:
        base_url (str): Ollama base URL.
        timeout (float): Per-request timeout in seconds.

    Returns:
        tuple: ``(models, reachable, detail)`` where ``models`` is a sorted list
        of model names, ``reachable`` says whether any loopback spelling
        answered, and ``detail`` is a short status string for the UI.
    """
    reachable = False
    detail = ''
    for base in host_variants(base_url):
        try:
            r = local_get(f"{base}/api/tags", timeout=timeout)
        except Exception:
            continue
        reachable = True
        if r.status_code != 200:
            detail = f"HTTP {r.status_code}"
            continue
        try:
            payload = r.json()
        except ValueError:
            detail = "unreadable response"
            continue
        names = []
        for entry in payload.get('models', []) or []:
            name = entry.get('name') or entry.get('model') or ''
            if name:
                names.append(name)
        if names:
            return sorted(set(names)), True, ''
        detail = "no models installed"
    return [], reachable, detail


def fetch_openai_models(base_url, timeout=PROBE_TIMEOUT, api_key=''):
    """List models advertised by an OpenAI-compatible ``/v1/models`` endpoint.

    Args:
        base_url (str): Server base URL, with or without a ``/v1`` suffix.
        timeout (float): Per-request timeout in seconds.
        api_key (str): Optional bearer token.

    Returns:
        tuple: ``(models, reachable, detail)`` mirroring ``fetch_ollama_models``.
    """
    reachable = False
    detail = ''
    headers = {'Content-Type': 'application/json'}
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'
    for base in host_variants(base_url):
        url = base if base.rstrip('/').endswith('/v1') else f"{base}/v1"
        try:
            r = local_get(f"{url}/models", timeout=timeout, headers=headers)
        except Exception:
            continue
        reachable = True
        if r.status_code in (401, 403):
            detail = "auth failed"
            continue
        if r.status_code != 200:
            detail = f"HTTP {r.status_code}"
            continue
        try:
            payload = r.json()
        except ValueError:
            detail = "unreadable response"
            continue
        ids = [m.get('id', '') for m in payload.get('data', []) or [] if m.get('id')]
        if ids:
            return ids, True, ''
        detail = "no models listed"
    return [], reachable, detail
