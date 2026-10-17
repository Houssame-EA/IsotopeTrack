# `crash_reporting.py`

tools/crash_reporting.py

Anonymous error reporting for IsotopeTrack through Sentry.

Only the error itself ever leaves the computer: the exception type, a cleaned
message, and the stack of IsotopeTrack and library functions that led to it,
tagged with the app version and the operating system name and version.

Nothing about the user is sent. Every outgoing event is rebuilt from an allow
list, so anything Sentry or a future SDK version adds by default is dropped:
no user name, computer name, IP address, file paths, file or sample names,
command-line arguments, variable values, log lines or installed packages.
Quoted text and paths inside error messages are replaced by placeholders.

Automatic reports are opt-in and stored in ``QSettings`` under
``crash_reports/enabled``. A bug report the user writes and sends from the
Help menu is sent even when automatic reports are off, because sending it is
itself the user's choice.

Reports are only sent from the packaged application. Running from source sends
nothing unless the environment variable ``ISOTOPETRACK_SENTRY_DEV`` is ``1``.

---

## Constants

| Name | Value |
|------|-------|
| `SENTRY_DSN` | `'https://e55a54d27c29a0001c5d9daa76a129f0@o45122558864261…` |
| `SETTINGS_ORG` | `'IsotopeTrack'` |
| `SETTINGS_APP` | `'IsotopeTrack'` |
| `ENABLED_KEY` | `'crash_reports/enabled'` |
| `ASKED_KEY` | `'crash_reports/asked'` |
| `DEV_ENV_VAR` | `'ISOTOPETRACK_SENTRY_DEV'` |
| `MAX_EVENTS_PER_SESSION` | `10` |
| `MAX_MESSAGE_LENGTH` | `500` |
| `MAX_BUG_REPORT_LENGTH` | `5000` |
| `FLUSH_TIMEOUT_S` | `2.0` |
| `_APP_ROOT` | `Path(__file__).resolve().parent.parent` |
| `_PATH_RE` | `re.compile('(?<![\\w.])(?:[A-Za-z]:[\\\\/]\|\\\\\\\\\|~[\\\…` |
| `_QUOTED_RE` | `re.compile('\'[^\']*\'\|\\"[^\\"]*\\"')` |
| `_EMAIL_RE` | `re.compile('[\\w.+-]+@[\\w-]+\\.[\\w.-]+')` |
| `_URL_RE` | `re.compile('\\b[a-zA-Z][a-zA-Z0-9+.-]*://\\S+')` |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_settings` | `()` | Return the application's QSettings store. |
| `reports_enabled` | `()` | Return True when the user agreed to send automatic error reports. |
| `consent_asked` | `()` | Return True once the user has answered the first-launch question. |
| `set_reports_enabled` | `(enabled)` | Store the user's choice and start or stop automatic reporting. |
| `sending_allowed` | `()` | Return True when this build may send anything at all. |
| `start_crash_reporting` | `()` | Start Sentry at launch when the user has opted in. |
| `shutdown_crash_reporting` | `()` | Give queued reports a short time to leave before the process exits. |
| `send_bug_report` | `(description)` | Send a bug report the user wrote. |
| `_ensure_client` | `()` | Initialise the Sentry client once, with every default collector off. |
| `_private_strings` | `()` | Return strings that identify this computer or user, longest first. |
| `scrub_text` | `(text, keep_quoted=False)` | Remove anything that could identify the user from a piece of text. |
| `_path_placeholder` | `(match)` | Replace a matched path by ``<path>`` while keeping a lone slash. |
| `_clean_filename` | `(filename)` | Reduce a stack frame file name to a path inside the app or a library. |
| `_clean_frame` | `(frame)` | Keep only the code location of a stack frame. |
| `_clean_exception` | `(value)` | Keep the type, cleaned message and stack of one exception. |
| `_environment_context` | `()` | Return the operating system and Python version, nothing else. |
| `_signature` | `(event)` | Return a key that identifies the same error within this session. |
| `_before_send` | `(event, hint)` | Rebuild every outgoing event from an allow list. |
