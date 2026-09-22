#!/usr/bin/env python3
"""Log and graph the 4-20 mA signal on analog input 1 of a Sequent
Microsystems MEGA-IND card (https://github.com/SequentMicrosystems/megaind-rpi).

Samples are appended to a CSV file and a PNG graph is redrawn as data arrives.
Use --live for an on-screen window instead (needs a desktop session).
"""

import argparse
import csv
import os
import signal
import sys
import time
from collections import deque
from datetime import datetime

# Milliamp span of a standard 4-20 mA loop.
MA_MIN = 4.0
MA_MAX = 20.0


def parse_args():
    p = argparse.ArgumentParser(description="Log the 4-20 mA signal on MEGA-IND analog input 1.")
    p.add_argument("--stack", type=int, default=0, help="card stack level, 0-7 (default: 0)")
    p.add_argument("--channel", type=int, default=1, help="4-20 mA input channel, 1-4 (default: 1)")
    p.add_argument("--interval", type=float, default=1.0, help="seconds between samples (default: 1.0)")
    p.add_argument("--duration", type=float, default=0.0,
                   help="stop after N seconds; 0 runs until Ctrl+C (default: 0)")
    p.add_argument("--csv", default="data/ai1_log.csv", help="CSV output path")
    p.add_argument("--png", default="data/ai1_graph.png", help="PNG graph output path")
    p.add_argument("--window", type=int, default=600,
                   help="how many recent samples the graph shows (default: 600)")
    p.add_argument("--live", action="store_true", help="show a live plot window instead of writing a PNG")
    p.add_argument("--demo", action="store_true",
                   help="generate a fake signal instead of reading hardware (for testing off-Pi)")
    return p.parse_args()


def make_reader(args):
    """Return a zero-arg function that yields one reading in milliamps."""
    if args.demo:
        import math
        start = time.time()

        def read_demo():
            # Slow sine sweeping the full 4-20 mA span.
            phase = (time.time() - start) / 30.0 * 2 * math.pi
            return 12.0 + 8.0 * math.sin(phase)

        return read_demo

    try:
        import megaind
    except ImportError:
        sys.exit("SMmegaind is not installed. Run this app through ./run.sh, "
                 "or use --demo to test without hardware.")

    def read_hw():
        return megaind.get4_20In(args.stack, args.channel)

    return read_hw


def ma_to_percent(ma):
    """Position within the 4-20 mA span, as a percentage."""
    return (ma - MA_MIN) / (MA_MAX - MA_MIN) * 100.0


def open_csv(path):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    is_new = not os.path.exists(path) or os.path.getsize(path) == 0
    handle = open(path, "a", newline="")
    writer = csv.writer(handle)
    if is_new:
        writer.writerow(["timestamp", "epoch", "milliamps", "percent_of_span"])
        handle.flush()
    return handle, writer


def setup_plot(args):
    import matplotlib
    if not args.live:
        matplotlib.use("Agg")  # headless: render straight to a file
    import matplotlib.pyplot as plt
    from matplotlib.dates import AutoDateLocator, DateFormatter

    fig, ax = plt.subplots(figsize=(10, 5))
    line, = ax.plot([], [], color="#0f6fd1", linewidth=1.6)
    ax.set_title("MEGA-IND analog input %d - 4-20 mA" % args.channel)
    ax.set_xlabel("time")
    ax.set_ylabel("milliamps")
    ax.set_ylim(0, 22)
    ax.grid(True, alpha=0.3)
    # Reference lines for the ends of the loop range.
    ax.axhline(MA_MIN, color="#999999", linestyle="--", linewidth=1)
    ax.axhline(MA_MAX, color="#999999", linestyle="--", linewidth=1)
    # Treat the x axis as clock time rather than raw float dates.
    ax.xaxis_date()
    ax.xaxis.set_major_locator(AutoDateLocator())
    ax.xaxis.set_major_formatter(DateFormatter("%H:%M:%S"))
    fig.autofmt_xdate()

    if args.live:
        plt.ion()
        plt.show(block=False)

    return plt, fig, ax, line


def redraw(plt, fig, ax, line, times, values, args):
    line.set_data(times, values)
    ax.relim()
    ax.autoscale_view(scalex=True, scaley=False)
    if args.live:
        fig.canvas.draw_idle()
        fig.canvas.flush_events()
    else:
        parent = os.path.dirname(args.png)
        if parent:
            os.makedirs(parent, exist_ok=True)
        fig.savefig(args.png, dpi=110, bbox_inches="tight")


def main():
    args = parse_args()

    if not 0 <= args.stack <= 7:
        sys.exit("--stack must be 0-7")
    if not 1 <= args.channel <= 4:
        sys.exit("--channel must be 1-4")
    if args.interval <= 0:
        sys.exit("--interval must be greater than 0")

    read = make_reader(args)
    handle, writer = open_csv(args.csv)
    plt, fig, ax, line = setup_plot(args)

    times = deque(maxlen=args.window)
    values = deque(maxlen=args.window)

    running = {"go": True}

    def stop(_sig, _frame):
        running["go"] = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    print("Logging analog input %d (stack %d) every %.2fs -> %s"
          % (args.channel, args.stack, args.interval, args.csv))
    print("Graph: %s   (Ctrl+C to stop)" % (args.png if not args.live else "live window"))

    started = time.time()
    try:
        while running["go"]:
            loop_start = time.time()
            now = datetime.now()

            try:
                ma = float(read())
            except Exception as exc:  # keep logging through a transient I2C hiccup
                print("read failed: %s" % exc, file=sys.stderr)
                time.sleep(args.interval)
                continue

            pct = ma_to_percent(ma)
            writer.writerow([now.isoformat(timespec="seconds"), "%.3f" % loop_start,
                             "%.3f" % ma, "%.2f" % pct])
            handle.flush()

            times.append(now)
            values.append(ma)
            redraw(plt, fig, ax, line, list(times), list(values), args)

            print("%s  %6.3f mA  (%6.2f%% of span)" % (now.strftime("%H:%M:%S"), ma, pct))

            if args.duration and (time.time() - started) >= args.duration:
                break

            sleep_for = args.interval - (time.time() - loop_start)
            if sleep_for > 0:
                time.sleep(sleep_for)
    finally:
        handle.close()
        if values:
            args_live_was = args.live
            args.live = False  # always leave a PNG behind on exit
            redraw(plt, fig, ax, line, list(times), list(values), args)
            args.live = args_live_was
            print("\nWrote %d samples to %s" % (len(values), args.csv))
            print("Graph saved to %s" % args.png)


if __name__ == "__main__":
    main()
