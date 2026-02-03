import time
import threading
from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

try:
    import pytz
except Exception:
    pytz = None


def _tz_from_name(name):
    if not name:
        return None
    if ZoneInfo is not None:
        try:
            return ZoneInfo(name)
        except Exception:
            pass
    if pytz is not None:
        try:
            return pytz.timezone(name)
        except Exception:
            pass
    raise ValueError(f"Unknown timezone: {name}")


def get_local_time(tz: str = None, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Return current time as a formatted string for optional timezone name."""
    now = datetime.utcnow()
    if tz:
        tzone = _tz_from_name(tz)
        if ZoneInfo is not None and isinstance(tzone, ZoneInfo):
            aware = datetime.now(tzone)
        elif pytz is not None:
            aware = pytz.utc.localize(now).astimezone(tzone)
        else:
            aware = now
        return aware.strftime(fmt)
    return datetime.now().strftime(fmt)


class Stopwatch:
    def __init__(self):
        self._start = None
        self._elapsed = 0.0
        self._running = False
        self._laps = []

    def start(self):
        if not self._running:
            self._start = time.perf_counter()
            self._running = True

    def stop(self):
        if self._running:
            delta = time.perf_counter() - self._start
            self._elapsed += delta
            self._running = False
            return self._elapsed
        return self._elapsed

    def reset(self):
        self._start = None
        self._elapsed = 0.0
        self._running = False
        self._laps = []

    def lap(self):
        now = time.perf_counter()
        if self._running and self._start is not None:
            lap_time = now - self._start + self._elapsed
            self._laps.append(lap_time)
            return lap_time
        return None

    def elapsed(self):
        if self._running and self._start is not None:
            return self._elapsed + (time.perf_counter() - self._start)
        return self._elapsed


class Timer:
    def __init__(self):
        self._thread = None
        self._stop_event = threading.Event()

    def start(self, seconds: int, on_tick=None, on_finish=None):
        def _run():
            remaining = int(seconds)
            while remaining > 0 and not self._stop_event.is_set():
                if on_tick:
                    on_tick(remaining)
                time.sleep(1)
                remaining -= 1
            if not self._stop_event.is_set():
                if on_finish:
                    on_finish()

        self._stop_event.clear()
        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def cancel(self):
        if self._thread and self._thread.is_alive():
            self._stop_event.set()
            self._thread.join(timeout=1)


class Alarm:
    def __init__(self):
        self._timer = None

    def set_alarm(self, when: str, tz: str = None, callback=None):
        """Set an alarm. `when` can be 'HH:MM' today or an ISO datetime.
        This uses a background timer thread to call `callback()` when time arrives.
        """
        now = datetime.now()
        try:
            target = datetime.fromisoformat(when)
        except Exception:
            hh, mm = when.split(":")
            target = now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
            if target <= now:
                target = target + timedelta(days=1)

        delay = (target - now).total_seconds()
        if delay < 0:
            raise ValueError("Alarm time is in the past")

        def _trigger():
            if callback:
                callback()

        self._timer = threading.Timer(delay, _trigger)
        self._timer.daemon = True
        self._timer.start()

    def cancel(self):
        if self._timer:
            self._timer.cancel()


def convert_timezone(dt: str, from_tz: str, to_tz: str, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Convert a datetime string `dt` from `from_tz` to `to_tz`.
    `dt` can be ISO or a formatted time compatible with `fmt`.
    """
    try:
        parsed = datetime.fromisoformat(dt)
    except Exception:
        parsed = datetime.strptime(dt, fmt)

    if pytz is not None:
        src = pytz.timezone(from_tz)
        dst = pytz.timezone(to_tz)
        aware = src.localize(parsed) if parsed.tzinfo is None else parsed.astimezone(src)
        converted = aware.astimezone(dst)
        return converted.strftime(fmt)

    if ZoneInfo is not None:
        src = ZoneInfo(from_tz)
        dst = ZoneInfo(to_tz)
        if parsed.tzinfo is None:
            aware = parsed.replace(tzinfo=src)
        else:
            aware = parsed.astimezone(src)
        converted = aware.astimezone(dst)
        return converted.strftime(fmt)

    raise RuntimeError("No timezone support available. Install pytz or use Python 3.9+ with zoneinfo.")
