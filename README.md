# MEGA-IND 4-20 mA Logger

Logs the 4-20 mA signal on **analog input 1** of a
[Sequent Microsystems MEGA-IND](https://github.com/SequentMicrosystems/megaind-rpi)
card on a Raspberry Pi, writing every sample to CSV and redrawing a graph as it goes.

## One-time Pi setup

Enable I2C and make sure `python3-venv` is present:

```bash
sudo raspi-config     # Interface Options -> I2C -> Yes, then reboot
sudo apt install -y python3-venv python3-pip
```

## Run it

```bash
./run.sh
```

`run.sh` creates `.venv/`, installs `SMmegaind` + `matplotlib` into it (only on the
first run, or when `requirements.txt` changes), and starts the logger. Ctrl+C to stop.

Output lands in `data/`:

| file | contents |
| --- | --- |
| `data/ai1_log.csv` | `timestamp, epoch, milliamps, percent_of_span` — appended to across runs |
| `data/ai1_graph.png` | the graph, rewritten after every sample |

## Options

Anything after `./run.sh` is passed to `logger.py`:

```bash
./run.sh --interval 0.5            # sample twice a second
./run.sh --duration 3600           # stop after an hour
./run.sh --channel 2 --stack 1     # a different input / stacked card
./run.sh --live                    # on-screen plot window (needs a desktop session)
./run.sh --demo                    # fake signal, no hardware needed
```

| flag | default | meaning |
| --- | --- | --- |
| `--stack` | `0` | card stack level, 0-7 |
| `--channel` | `1` | 4-20 mA input channel, 1-4 |
| `--interval` | `1.0` | seconds between samples |
| `--duration` | `0` | stop after N seconds; 0 = until Ctrl+C |
| `--csv` | `data/ai1_log.csv` | CSV path |
| `--png` | `data/ai1_graph.png` | graph path |
| `--window` | `600` | how many recent samples the graph shows |
| `--live` | off | live window instead of a PNG |
| `--demo` | off | simulated signal for testing off-Pi |

## Notes

- Readings come from `megaind.get4_20In(stack, channel)`, which returns milliamps.
- `percent_of_span` is `(mA - 4) / 16 * 100`, i.e. where the reading sits in the loop range.
- A failed read (transient I2C error) is printed to stderr and the loop keeps going.
- Watching the graph remotely: `scp pi@raspberrypi:~/megaind-logger/data/ai1_graph.png .`
