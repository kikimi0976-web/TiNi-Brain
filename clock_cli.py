import argparse
import time
from datetime import datetime
from clock_tools import get_local_time, Stopwatch, Timer, Alarm, convert_timezone


def cmd_now(args):
    print(get_local_time(args.tz, args.format))


def cmd_stopwatch(args):
    sw = Stopwatch()
    print("Stopwatch: press Enter to stop, Ctrl+C to abort.")
    sw.start()
    try:
        input()
    except KeyboardInterrupt:
        print("\nAborted")
        return
    elapsed = sw.stop()
    print(f"Elapsed: {elapsed:.3f} seconds")


def cmd_timer(args):
    def tick(remaining):
        print(f"Remaining: {remaining}s", end='\r')

    def finish():
        print("\nTimer finished!")

    t = Timer()
    t.start(int(args.seconds), on_tick=tick, on_finish=finish)
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        t.cancel()
        print("\nTimer cancelled")


def cmd_alarm(args):
    def ring():
        print("\n=== ALARM ===\n")

    a = Alarm()
    a.set_alarm(args.when, tz=args.tz, callback=ring)
    print(f"Alarm set for {args.when}. Ctrl+C to cancel.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        a.cancel()
        print("\nAlarm cancelled")


def cmd_convert(args):
    out = convert_timezone(args.dt, args.from_tz, args.to_tz, fmt=args.format)
    print(out)


def main():
    parser = argparse.ArgumentParser(prog="clock_cli", description="Simple clock tools CLI")
    sub = parser.add_subparsers(dest="cmd")

    p_now = sub.add_parser("now", help="Show current time")
    p_now.add_argument("-t", "--tz", help="Timezone name (e.g. Europe/Berlin)")
    p_now.add_argument("-f", "--format", default="%Y-%m-%d %H:%M:%S")
    p_now.set_defaults(func=cmd_now)

    p_sw = sub.add_parser("stopwatch", help="Start a simple stopwatch (press Enter to stop)")
    p_sw.set_defaults(func=cmd_stopwatch)

    p_timer = sub.add_parser("timer", help="Start a countdown timer in seconds")
    p_timer.add_argument("seconds", type=int)
    p_timer.set_defaults(func=cmd_timer)

    p_alarm = sub.add_parser("alarm", help="Set an alarm (HH:MM or ISO datetime)")
    p_alarm.add_argument("when", help="Time like 'HH:MM' or ISO datetime")
    p_alarm.add_argument("-t", "--tz", help="Timezone (optional)")
    p_alarm.set_defaults(func=cmd_alarm)

    p_conv = sub.add_parser("convert", help="Convert datetime between timezones")
    p_conv.add_argument("dt", help="Datetime (ISO or formatted)")
    p_conv.add_argument("from_tz", help="Source timezone")
    p_conv.add_argument("to_tz", help="Destination timezone")
    p_conv.add_argument("-f", "--format", default="%Y-%m-%d %H:%M:%S")
    p_conv.set_defaults(func=cmd_convert)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
