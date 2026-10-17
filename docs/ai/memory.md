# `memory.py`

How much memory this computer has, how much a model needs, and which model fits.

The assistant's settings use this to mark the model recommended for the
computer and to warn before loading one that will not fit. Sizes are
estimates: a model needs its weights plus working memory for the
conversation and the runtime.

---

## Constants

| Name | Value |
|------|-------|
| `GB` | `1024 ** 3` |
| `OVERHEAD_FACTOR` | `1.15` |
| `OVERHEAD_FIXED` | `1.5 * GB` |
| `GPU_SHARE` | `0.75` |
| `RECOMMEND_SHARE` | `0.5` |
| `WEIGHT_PATTERNS` | `('*.safetensors', '*.npz', '*.gguf')` |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `system_memory` | `()` | Total and currently available memory of this computer. |
| `_macos_memory` | `()` | Total and available memory on macOS from sysctl and vm_stat. |
| `parse_vm_stat` | `(text)` | Available bytes from ``vm_stat`` output: free, inactive, speculative and purgeable pages. |
| `_linux_memory` | `()` | Total and available memory from /proc/meminfo. |
| `_windows_memory` | `()` | Total and available memory on Windows. |
| `folder_weight_bytes` | `(path)` | Size of the weight files in a model folder. |
| `folder_is_quantized` | `(path)` | Whether an MLX model folder holds a quantized model (4-bit, 8-bit, ...). |
| `mlx_model_folder` | `(model, cache_roots=None)` | The folder holding an MLX model given as a path or a Hugging Face repo id. |
| `needed_bytes` | `(weight_bytes)` | Memory a model needs while answering: weights plus working memory. |
| `fmt_gb` | `(n)` | Bytes as a short GB string, e.g. ``15 GB`` or ``5.6 GB``. |
| `fit` | `(weight_bytes, total, available)` | Whether a model fits this computer now. |
| `recommend` | `(models, total)` | The model to recommend for this computer. |
| `memory_line` | `(total, available)` | One line describing this computer's memory for the settings. |
