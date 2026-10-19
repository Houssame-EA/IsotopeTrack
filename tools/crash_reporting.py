"""
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
"""

import getpass
import logging
import os
import platform
import re
import socket
import sys
import uuid
from pathlib import Path

from PySide6.QtCore import QSettings

_itk_log = logging.getLogger("IsotopeTrack.tools.crash_reporting")

try:
    from utils.app_version import __version__ as APP_VERSION
except Exception:
    _itk_log.exception("Handled exception in <module>")
    APP_VERSION = "0.0.0"

SENTRY_DSN = (
    "https://e55a54d27c29a0001c5d9daa76a129f0"
    "@o4512255886426112.ingest.us.sentry.io/4512255949078528"
)

SETTINGS_ORG = "IsotopeTrack"
SETTINGS_APP = "IsotopeTrack"
ENABLED_KEY = "crash_reports/enabled"
ASKED_KEY = "crash_reports/asked"

DEV_ENV_VAR = "ISOTOPETRACK_SENTRY_DEV"
MAX_EVENTS_PER_SESSION = 10
MAX_MESSAGE_LENGTH = 500
MAX_BUG_REPORT_LENGTH = 5000
FLUSH_TIMEOUT_S = 2.0

_APP_ROOT = Path(__file__).resolve().parent.parent

_state = {
    "initialised": False,
    "sent": 0,
    "seen": set(),
}


def _settings():
    """Return the application's QSettings store."""
    return QSettings(SETTINGS_ORG, SETTINGS_APP)


def reports_enabled():
    """Return True when the user agreed to send automatic error reports.

    Returns:
        bool: Stored choice, defaulting to False.
    """
    return _settings().value(ENABLED_KEY, False, type=bool)


def consent_asked():
    """Return True once the user has answered the first-launch question.

    Returns:
        bool: Whether the consent question was already shown and answered.
    """
    return _settings().value(ASKED_KEY, False, type=bool)


def set_reports_enabled(enabled):
    """Store the user's choice and start or stop automatic reporting.

    Args:
        enabled (bool): True to send anonymous error reports.
    """
    s = _settings()
    s.setValue(ENABLED_KEY, bool(enabled))
    s.setValue(ASKED_KEY, True)
    if enabled:
        _ensure_client()


def sending_allowed():
    """Return True when this build may send anything at all.

    Returns:
        bool: True for the packaged app, or for a source run with the
        developer environment variable set.
    """
    if getattr(sys, "frozen", False):
        return True
    return os.environ.get(DEV_ENV_VAR) == "1"


def start_crash_reporting():
    """Start Sentry at launch when the user has opted in.

    Returns:
        bool: True if the Sentry client is running after the call.
    """
    if not reports_enabled():
        return False
    return _ensure_client()


def shutdown_crash_reporting():
    """Give queued reports a short time to leave before the process exits."""
    if not _state["initialised"]:
        return
    try:
        import sentry_sdk
        sentry_sdk.flush(timeout=FLUSH_TIMEOUT_S)
    except Exception:
        _itk_log.debug("Could not flush crash reports", exc_info=True)


def send_bug_report(description):
    """Send a bug report the user wrote.

    The text is cleaned the same way as error messages, but quoted text is kept
    because the user wrote it on purpose.

    Args:
        description (str): What the user typed in the bug report form.

    Returns:
        str | None: The Sentry event id, or None if nothing was sent.
    """
    text = (description or "").strip()
    if not text or not sending_allowed():
        return None
    if not _ensure_client():
        return None
    try:
        import sentry_sdk
        event = {
            "level": "info",
            "message": text[:MAX_BUG_REPORT_LENGTH],
            "tags": {"report_type": "bug_report"},
            "fingerprint": ["bug-report", uuid.uuid4().hex],
        }
        event_id = sentry_sdk.capture_event(event)
        sentry_sdk.flush(timeout=FLUSH_TIMEOUT_S)
        return event_id
    except Exception:
        _itk_log.exception("Could not send the bug report")
        return None


def _ensure_client():
    """Initialise the Sentry client once, with every default collector off.

    Returns:
        bool: True if the client is running.
    """
    if _state["initialised"]:
        return True
    if not sending_allowed():
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.dedupe import DedupeIntegration
        from sentry_sdk.integrations.excepthook import ExcepthookIntegration
        from sentry_sdk.integrations.threading import ThreadingIntegration
    except Exception:
        _itk_log.warning("sentry-sdk is not installed; error reporting is off")
        return False
    try:
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            release=f"isotopetrack@{APP_VERSION}",
            environment="production" if getattr(sys, "frozen", False) else "development",
            default_integrations=False,
            auto_enabling_integrations=False,
            integrations=[
                ExcepthookIntegration(always_run=True),
                ThreadingIntegration(propagate_scope=False),
                DedupeIntegration(),
            ],
            send_default_pii=False,
            include_local_variables=False,
            include_source_context=True,
            max_breadcrumbs=0,
            server_name="",
            auto_session_tracking=False,
            send_client_reports=False,
            attach_stacktrace=False,
            traces_sample_rate=None,
            before_send=_before_send,
            before_breadcrumb=lambda crumb, hint: None,
        )
    except Exception:
        _itk_log.exception("Could not start error reporting")
        return False
    _state["initialised"] = True
    return True


def _private_strings():
    """Return strings that identify this computer or user, longest first."""
    values = set()
    for getter in (getpass.getuser, socket.gethostname, platform.node):
        try:
            v = getter()
        except Exception:
            v = ""
        if v and len(v) >= 2:
            values.add(v)
    try:
        home = str(Path.home())
        if len(home) > 1:
            values.add(home)
    except Exception:
        pass
    return sorted(values, key=len, reverse=True)


_PATH_RE = re.compile(
    r"(?<![\w.])"
    r"(?:[A-Za-z]:[\\/]|\\\\|~[\\/]|/)"
    r"(?:[^\s'\"<>|:*?\\/]+[\\/])*"
    r"[^\s'\"<>|:*?\\/]*"
)
_QUOTED_RE = re.compile(r"'[^']*'|\"[^\"]*\"")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_URL_RE = re.compile(r"\b[a-zA-Z][a-zA-Z0-9+.-]*://\S+")


def scrub_text(text, keep_quoted=False):
    """Remove anything that could identify the user from a piece of text.

    Args:
        text (str): Error message or user-written text.
        keep_quoted (bool): Keep quoted text instead of replacing it.

    Returns:
        str: Text with paths, URLs, e-mail addresses, the user and computer
        names and, unless ``keep_quoted``, quoted values replaced.
    """
    if not text:
        return ""
    out = str(text)
    for private in _private_strings():
        out = re.sub(r"(?<!\w)" + re.escape(private) + r"(?!\w)", "<private>", out)
    out = _URL_RE.sub("<url>", out)
    out = _EMAIL_RE.sub("<email>", out)
    if not keep_quoted:
        out = _QUOTED_RE.sub("'<text>'", out)
    out = _PATH_RE.sub(_path_placeholder, out)
    return out


def _path_placeholder(match):
    """Replace a matched path by ``<path>`` while keeping a lone slash."""
    s = match.group(0)
    if len(s) <= 1:
        return s
    ext = os.path.splitext(s.rstrip("\\/"))[1]
    if ext and len(ext) <= 8 and re.fullmatch(r"\.[A-Za-z0-9]+", ext):
        return f"<path{ext}>"
    return "<path>"


def _clean_filename(filename):
    """Reduce a stack frame file name to a path inside the app or a library.

    Args:
        filename (str): File name or path reported by Sentry for a frame.

    Returns:
        str: ``tools/foo.py`` style relative path, or just the base name.
    """
    if not filename:
        return ""
    f = str(filename).replace("\\", "/")
    root = str(_APP_ROOT).replace("\\", "/").rstrip("/") + "/"
    if f.startswith(root):
        return f[len(root):]
    for marker in ("site-packages/", "dist-packages/", "/lib/python"):
        idx = f.rfind(marker)
        if idx >= 0:
            tail = f[idx + len(marker):]
            if marker == "/lib/python":
                tail = tail.split("/", 1)[-1]
            return tail
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        m = str(meipass).replace("\\", "/").rstrip("/") + "/"
        if f.startswith(m):
            return f[len(m):]
    if f.startswith("/") or re.match(r"^[A-Za-z]:/", f) or "<private>" in scrub_text(f):
        return os.path.basename(f)
    return f


def _clean_frame(frame):
    """Keep only the code location of a stack frame.

    Args:
        frame (dict): Sentry frame.

    Returns:
        dict: Frame with file, module, function, line and, for ``.py`` files,
        the surrounding source lines of the open-source code.
    """
    filename = _clean_filename(frame.get("filename") or frame.get("abs_path") or "")
    clean = {
        "filename": filename,
        "module": frame.get("module"),
        "function": frame.get("function"),
        "lineno": frame.get("lineno"),
        "in_app": frame.get("in_app"),
    }
    if filename.endswith(".py"):
        for key in ("context_line", "pre_context", "post_context"):
            if key in frame:
                clean[key] = frame[key]
    return {k: v for k, v in clean.items() if v is not None}


def _clean_exception(value):
    """Keep the type, cleaned message and stack of one exception."""
    clean = {
        "type": value.get("type"),
        "value": scrub_text(value.get("value") or "")[:MAX_MESSAGE_LENGTH],
        "module": value.get("module"),
    }
    mech = value.get("mechanism")
    if isinstance(mech, dict):
        clean["mechanism"] = {
            k: mech[k] for k in ("type", "handled", "exception_id",
                                 "parent_id", "source", "is_exception_group")
            if k in mech
        }
    st = value.get("stacktrace")
    if isinstance(st, dict) and isinstance(st.get("frames"), list):
        clean["stacktrace"] = {"frames": [_clean_frame(f) for f in st["frames"]]}
    return {k: v for k, v in clean.items() if v is not None}


def _environment_context():
    """Return the operating system and Python version, nothing else."""
    return {
        "os": {"name": platform.system(), "version": platform.release()},
        "runtime": {"name": "CPython", "version": platform.python_version()},
        "app": {"app_version": APP_VERSION,
                "frozen": bool(getattr(sys, "frozen", False))},
    }


def _signature(event):
    """Return a key that identifies the same error within this session."""
    try:
        exc = event["exception"]["values"][-1]
        frames = exc.get("stacktrace", {}).get("frames", [])
        top = frames[-1] if frames else {}
        return (exc.get("type"), top.get("filename"), top.get("function"), top.get("lineno"))
    except Exception:
        return None


def _before_send(event, hint):
    """Rebuild every outgoing event from an allow list.

    Error events are dropped unless the user enabled automatic reports, and
    after the first copy of the same error or ``MAX_EVENTS_PER_SESSION``
    reports in one session.

    Args:
        event (dict): Event prepared by the Sentry SDK.
        hint (dict): Sentry hint, unused.

    Returns:
        dict | None: The cleaned event, or None to send nothing.
    """
    try:
        is_bug_report = (event.get("tags") or {}).get("report_type") == "bug_report"
        if not is_bug_report:
            if not reports_enabled():
                return None
            if "exception" not in event:
                return None
            sig = _signature(event)
            if sig in _state["seen"]:
                return None
            if _state["sent"] >= MAX_EVENTS_PER_SESSION:
                return None
            _state["seen"].add(sig)
            _state["sent"] += 1

        clean = {
            k: event[k]
            for k in ("event_id", "timestamp", "platform", "level",
                      "release", "environment", "sdk", "fingerprint")
            if k in event
        }
        clean["contexts"] = _environment_context()
        clean["tags"] = {"report_type": "bug_report" if is_bug_report else "error"}

        if is_bug_report:
            msg = event.get("message")
            if not msg and isinstance(event.get("logentry"), dict):
                msg = event["logentry"].get("message")
            clean["message"] = scrub_text(msg or "", keep_quoted=True)[:MAX_BUG_REPORT_LENGTH]
        else:
            values = (event.get("exception") or {}).get("values") or []
            clean["exception"] = {"values": [_clean_exception(v) for v in values]}
        return clean
    except Exception:
        _itk_log.debug("Dropped an error report that could not be cleaned", exc_info=True)
        return None
