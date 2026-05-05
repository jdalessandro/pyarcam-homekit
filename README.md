# pyarcam-homekit

Bridge **Arcam SA10 / SA20** network amplifiers to **Apple HomeKit** using [HAP-python](https://github.com/ikalchev/HAP-python) and [pyarcam](https://github.com/jdalessandro/pyarcam). The amp appears as a **Television** accessory under a HomeKit bridge (power, volume, mute, and discrete inputs).

## Requirements

- **Python** 3.10+
- Amplifier reachable on your LAN (factory TCP port **50000** unless you changed it)
- **Network standby** enabled on the amp if you want remote control while it is “off”

## Install

From a clone of this repository (pyarcam is installed from GitHub, not PyPI):

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

Or with `requirements.txt`:

```bash
pip install -r requirements.txt
```

## Configuration

Create **`arcam.json`** in the working directory (or point **`ARCAM_CONFIG`** at another path). Copy and edit the example:

```bash
cp arcam.example.json arcam.json
```

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `host` | yes | — | Amplifier IP or hostname |
| `port` | no | `50000` | TCP control port |
| `timeout_sec` | no | `5.0` | Client socket timeout (seconds) |
| `poll_interval_seconds` | no | `3.0` | How often HomeKit state is refreshed from the amp |
| `display_name` | no | `"Arcam SA20"` | Name shown in the Home app |
| `hap_aid` | no | `2` | HomeKit accessory ID for the TV accessory (`null` to auto-assign) |
| `zone` | no | `1` | `1` or `2` for zone 1 / zone 2 |

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ARCAM_CONFIG` | `arcam.json` | Path to the JSON config |
| `ARCAM_HAP_PORT` | `51827` | Port for the HomeKit accessory server |
| `ARCAM_HAP_PERSIST` | `~/.pyarcam_homekit.state` | Pairing / accessory persistence file |
| `ARCAM_HAP_PINCODE` | `031-45-154` | Setup code shown when pairing (format `XXX-XX-XXX`) |
| `ARCAM_LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, …) |

If another HAP bridge on the same machine already uses **51827**, set `ARCAM_HAP_PORT` to a free port (for example **51828**).

## Run

```bash
pyarcam-homekit
```

or:

```bash
python -m pyarcam_homekit
```

Pair the **bridge** in the Home app using the pin from `ARCAM_HAP_PINCODE`. After pairing, use the Television tile for power, volume, mute, and input selection.

## systemd (Linux)

Example unit: `systemd/pyarcam-homekit.service`. Adjust **`User`**, **`Group`**, **`WorkingDirectory`**, and **`ExecStart`** to match your install, then:

```bash
sudo cp systemd/pyarcam-homekit.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pyarcam-homekit
```

Optional overrides in `/etc/default/pyarcam-homekit` (see comments in the unit file), for example:

```bash
echo 'ARCAM_HAP_PORT=51828' | sudo tee -a /etc/default/pyarcam-homekit
```

## Troubleshooting

- **Config not found** — Ensure `arcam.json` exists or set `ARCAM_CONFIG`.
- **Unreachable / timeouts** — Confirm the amp IP, firewall, and **network standby**. Connection errors are logged; the bridge keeps running and retries on the next poll.
- **Port in use** — Change `ARCAM_HAP_PORT`.

## License

MIT — see [LICENSE](LICENSE).
