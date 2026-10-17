# `settings.py`

Settings dialogs: which model to use, and how the chat looks.

---

## Constants

| Name | Value |
|------|-------|
| `IDLE_CHOICES` | `[('Never', 0), ('5 minutes', 5), ('10 minutes', 10), ('15…` |
| `RECOMMENDED_MARK` | `'★ Recommended for this computer'` |

## Classes

### `BackendDialog` *(extends `QDialog`)*

Choose the model backend, model, context window and answer checks.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, current_cfg, parent=None)` | Build the dialog. |
| `_on_backend` | `(self, idx)` | Show the settings of the selected backend. |
| `_fetch_ollama_models` | `(self)` | Refresh the model combo from the running Ollama server. |
| `_test_mlx` | `(self)` | Check the MLX server and report the models it exposes. |
| `_scan_mlx_models` | `(self)` | Fill the MLX model list from the running server and the local cache. |
| `_fill_list` | `(self, widget, rows, infos)` | Fill a model list, adding each model's memory need and the recommended mark. |
| `_current_model_for_fit` | `(self)` | The model the fit note describes: the one selected for the active backend. |
| `_model_fit` | `(self)` | Whether the selected model fits this computer now. |
| `_update_fit` | `(self)` | Show whether the selected model fits, in colour when it does not. |
| `_confirm_fit` | `(self)` | Ask before using a model that does not fit now. |
| `_accept_if_fits` | `(self)` | Close with OK, after a warning when the model will not fit. |
| `_add_model_folder` | `(self)` | Let the user add a folder of MLX models and list them. |
| `_selected_mlx_model` | `(self)` | Return the model id chosen in the MLX list. |
| `_start_mlx_server` | `(self)` | Launch mlx_lm.server for the selected model and wait for it to answer. |
| `_stop_mlx_server` | `(self)` | Stop the MLX server and free the memory its weights occupy. |
| `_poll_mlx_server` | `(self, model, host)` | Check whether the launched MLX server has finished loading. |
| `_ctx_value` | `(self)` | Return the context window as an integer, falling back to 8192. |
| `_apply_model_context` | `(self)` | Set the context window to what the selected Ollama model supports. |
| `_selected_ollama_model` | `(self)` | Return the Ollama model name highlighted in the list. |
| `_resolve_mlx_model` | `(self)` | Ask the MLX server which model it has loaded. |
| `_test_custom` | `(self)` | Check the custom OpenAI-compatible endpoint and prefill a model. |
| `get_config` | `(self)` | Collect the chosen settings. |

### `CustomizeDialog` *(extends `QDialog`)*

Font size, chart quality, and display options.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` | Build the dialog. |
| `_dpi_value` | `(self)` | Return the chosen chart resolution in dpi. |
| `_reset` | `(self)` | Put every control back to its default. |
| `_apply` | `(self)` | Store the choices and close. |
