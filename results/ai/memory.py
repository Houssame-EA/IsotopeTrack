"""How much memory this computer has, how much a model needs, and which model fits.

The assistant's settings use this to mark the model recommended for the
computer and to warn before loading one that will not fit. Sizes are
estimates: a model needs its weights plus working memory for the
conversation and the runtime.
"""
import glob
import json
import logging
import os
import re
import subprocess
import sys

_itk_log = logging.getLogger("IsotopeTrack.results.ai.memory")

GB = 1024 ** 3

OVERHEAD_FACTOR = 1.15
"""Working memory for the conversation, as a share of the weights."""

OVERHEAD_FIXED = 1.5 * GB
"""Fixed memory the model server needs besides the weights."""

GPU_SHARE = 0.75
"""Share of the RAM the GPU may use by default on a Mac; more than this cannot load."""

RECOMMEND_SHARE = 0.5
"""Share of the RAM a recommended model may take, leaving the rest for other work."""

WEIGHT_PATTERNS = ('*.safetensors', '*.npz', '*.gguf')


def system_memory():
    """Total and currently available memory of this computer.

    Available memory counts free memory plus memory the system can hand
    back at once (inactive and purgeable pages on a Mac).

    Returns:
        tuple: ``(total_bytes, available_bytes)``; either is ``None`` when
        it cannot be read.
    """
    try:
        import psutil
        vm = psutil.virtual_memory()
        return int(vm.total), int(vm.available)
    except Exception:
        pass
    try:
        if sys.platform == 'darwin':
            return _macos_memory()
        if sys.platform.startswith('linux'):
            return _linux_memory()
        if sys.platform.startswith('win'):
            return _windows_memory()
    except Exception:
        _itk_log.exception("Could not read the memory of this computer")
    return None, None


def _macos_memory():
    """Total and available memory on macOS from sysctl and vm_stat."""
    total = int(subprocess.run(['sysctl', '-n', 'hw.memsize'], capture_output=True,
                               text=True, timeout=4).stdout.strip())
    out = subprocess.run(['vm_stat'], capture_output=True, text=True, timeout=4).stdout
    return total, parse_vm_stat(out)


def parse_vm_stat(text):
    """Available bytes from ``vm_stat`` output: free, inactive, speculative and purgeable pages.

    Args:
        text (str): Output of ``vm_stat``.

    Returns:
        int: Bytes, or ``None`` when the output cannot be read.
    """
    m = re.search(r'page size of (\d+) bytes', text)
    if not m:
        return None
    page = int(m.group(1))
    pages = 0
    for key in ('Pages free', 'Pages inactive', 'Pages speculative', 'Pages purgeable'):
        hit = re.search(rf'{key}:\s+(\d+)', text)
        if hit:
            pages += int(hit.group(1))
    return pages * page


def _linux_memory():
    """Total and available memory from /proc/meminfo."""
    values = {}
    with open('/proc/meminfo') as fh:
        for line in fh:
            key, _, rest = line.partition(':')
            values[key] = int(rest.split()[0]) * 1024
    return values.get('MemTotal'), values.get('MemAvailable')


def _windows_memory():
    """Total and available memory on Windows."""
    import ctypes

    class MemoryStatus(ctypes.Structure):
        """The MEMORYSTATUSEX structure."""
        _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                    ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
                    ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                    ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong),
                    ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]
    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(MemoryStatus)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
    return int(status.ullTotalPhys), int(status.ullAvailPhys)


def folder_weight_bytes(path):
    """Size of the weight files in a model folder.

    Args:
        path (str): Folder holding the model.

    Returns:
        int: Bytes, 0 when the folder holds no weights.
    """
    total = 0
    for pattern in WEIGHT_PATTERNS:
        for f in glob.glob(os.path.join(path, pattern)):
            try:
                total += os.path.getsize(f)
            except OSError:
                continue
    return total


def folder_is_quantized(path):
    """Whether an MLX model folder holds a quantized model (4-bit, 8-bit, ...)."""
    try:
        with open(os.path.join(path, 'config.json')) as fh:
            cfg = json.load(fh)
    except Exception:
        return False
    return bool(cfg.get('quantization') or cfg.get('quantization_config'))


def mlx_model_folder(model, cache_roots=None):
    """The folder holding an MLX model given as a path or a Hugging Face repo id.

    Args:
        model (str): Local path or repo id such as ``mlx-community/Qwen3.5-9B-MLX-4bit``.
        cache_roots (list): Hugging Face cache folders; found automatically when omitted.

    Returns:
        str: The folder, or an empty string when it is not on this computer.
    """
    if not model:
        return ''
    path = os.path.expanduser(model)
    if os.path.isdir(path):
        return path
    if cache_roots is None:
        from results.ai.servers import hf_cache_roots
        cache_roots = hf_cache_roots()
    for root in cache_roots:
        snaps = sorted(glob.glob(os.path.join(root, 'models--' + model.replace('/', '--'), 'snapshots', '*')))
        for snap in reversed(snaps):
            if folder_weight_bytes(snap):
                return snap
    return ''


def needed_bytes(weight_bytes):
    """Memory a model needs while answering: weights plus working memory.

    Args:
        weight_bytes (int): Size of the weights.

    Returns:
        int: Bytes.
    """
    return int(weight_bytes * OVERHEAD_FACTOR + OVERHEAD_FIXED)


def fmt_gb(n):
    """Bytes as a short GB string, e.g. ``15 GB`` or ``5.6 GB``."""
    if n is None:
        return '?'
    gb = n / GB
    return f"{gb:.0f} GB" if gb >= 10 else f"{gb:.1f} GB"


def fit(weight_bytes, total, available):
    """Whether a model fits this computer now.

    Args:
        weight_bytes (int): Size of the model's weights, 0 when unknown.
        total (int): Total RAM, ``None`` when unknown.
        available (int): RAM available now, ``None`` when unknown.

    Returns:
        dict: ``level`` (``ok``, ``tight``, ``too_big`` or ``unknown``) and
        ``text``, a sentence for the settings.
    """
    if not weight_bytes or not total:
        return {'level': 'unknown', 'text': ''}
    need = needed_bytes(weight_bytes)
    if need > GPU_SHARE * total:
        return {'level': 'too_big', 'text': (
            f"⚠ This model needs about {fmt_gb(need)}, more than this computer can give it "
            f"({fmt_gb(total)} RAM). Choose a smaller model.")}
    if available is not None and need > available:
        return {'level': 'tight', 'text': (
            f"⚠ This model needs about {fmt_gb(need)}, but only {fmt_gb(available)} is free right now. "
            "Close other programs first, or choose the recommended model; otherwise the computer "
            "will slow down.")}
    return {'level': 'ok', 'text': f"✓ Needs about {fmt_gb(need)}; {fmt_gb(available)} free now."
            if available is not None else f"✓ Needs about {fmt_gb(need)}."}


def recommend(models, total):
    """The model to recommend for this computer.

    The largest model whose needs stay within :data:`RECOMMEND_SHARE` of
    the RAM, so there is room for other work; quantized models are
    preferred, since they answered as well as 16-bit ones in our tests and
    run faster.

    Args:
        models (list): Dicts with ``model``, ``bytes`` and ``quantized``.
        total (int): Total RAM.

    Returns:
        str: The recommended model id, or an empty string.
    """
    if not total:
        return ''
    fitting = [m for m in models if m.get('bytes') and needed_bytes(m['bytes']) <= RECOMMEND_SHARE * total]
    if not fitting:
        return ''
    best = max(fitting, key=lambda m: (bool(m.get('quantized')), m['bytes']))
    return best['model']


def memory_line(total, available):
    """One line describing this computer's memory for the settings."""
    if not total:
        return "Memory of this computer: unknown"
    if available is None:
        return f"This computer: {fmt_gb(total)} RAM"
    return f"This computer: {fmt_gb(total)} RAM, {fmt_gb(available)} free now"
