# Clock Tools

This workspace now includes a small `clock_tools` package and a CLI script `clock_cli.py` providing:

- Current time display (`now`)
- Stopwatch (press Enter to stop)
- Countdown timer (`timer`)
- Alarm (`alarm`)
- Timezone conversion (`convert`)

Quick examples:

```bash
python clock_cli.py now
python clock_cli.py now --tz Europe/Berlin
python clock_cli.py stopwatch
python clock_cli.py timer 10
python clock_cli.py alarm 07:30
python clock_cli.py convert "2025-12-31 12:00:00" UTC Europe/Berlin
```

Timezone support:
- The code uses `zoneinfo` when available (Python 3.9+). If your system lacks tzdata, install `tzdata` or `pytz`.
