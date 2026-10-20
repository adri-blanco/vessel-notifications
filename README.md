# AIS Vessel Notifications

Runs on a Raspberry Pi with an RTL-SDR dongle. It:
- Receives AIS signals from boats near a port and decodes them with **AIS-catcher**
- Sends a **Telegram** notification when a vessel enters the geofence
- Stores every visit in **Supabase** (PostgreSQL) for statistics
- Posts **daily and weekly stats** to Telegram, and answers `/today`, `/week` and `/all`

Domain terms (Visit, Sighting, Small vessel…) are defined in [GLOSSARY.md](GLOSSARY.md).

---

## How it behaves

- Only signals with a position **inside the geofence** count. Signals without a position are ignored.
- A vessel seen again within the dedup window (`DEDUP_WINDOW_SECONDS`) is skipped.
- **First time ever seen:** always notified.
- **Small vessels** (Fishing, Sailing, Pleasure craft) already seen before: stored in the database but **not** sent to Telegram.
- Direction (Arriving = heading south, Departing = heading north) is derived from the course. It is hardcoded for this port.
- Each report has a `Visits: X · Notified: Y` line.

---

## Hardware

| Component | Notes |
|-----------|-------|
| Raspberry Pi 3/4/5 | 64-bit OS with Docker installed |
| RTL-SDR dongle | Tested with **RTL-SDR Blog V4** |
| VHF antenna (~162 MHz) | AIS frequencies 161.975 / 162.025 MHz |

> The Blog V4 needs the `rtl-sdr-blog` driver. Debian's stock `librtlsdr` and `rtl-ais`
> do not work with it (`PLL not locked!`, no messages decoded). The Docker image builds the right driver.

---

## One-time setup

### 1. Supabase

1. Create a project at [supabase.com](https://supabase.com).
2. Run `supabase/schema.sql` in the **SQL editor**.
3. Copy the project URL and key.

**Upgrading an existing database:** run the commented `ALTER TABLE sightings ADD COLUMN IF NOT EXISTS notified …` line from `schema.sql`, then re-run the `stats_summary` function from the same file.

### 2. Telegram bot

1. Chat with [@BotFather](https://t.me/BotFather) → `/newbot`, and copy the token.
2. Add the bot to your chat or group.
3. Get the chat ID: send the bot a message, open `https://api.telegram.org/bot<TOKEN>/getUpdates` and read `"chat": {"id": ...}`.
   Groups are negative numbers; channels start with `-100`.

### 3. Configuration

```bash
cp .env.example .env
# fill in SUPABASE_URL, SUPABASE_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GEOFENCE_POLYGON
```

---

## Deploy with Docker (recommended)

`compose.yaml` runs two containers with host networking:
- `ais-catcher`: reads the RTL-SDR over USB and forwards NMEA to `127.0.0.1:10110`
- `ais-notify`: the app, listening on that UDP port

On the Pi:

```bash
git clone https://github.com/adri-blanco/vessel-notifications.git ~/dev/vessel-notifications
cd ~/dev/vessel-notifications
cp .env.example .env   # and edit it
docker compose up -d --build
```

The first build takes several minutes because it compiles the SDR driver and AIS-catcher.
Both containers restart automatically after a reboot.

### Day to day

```bash
docker compose ps                                  # status
docker compose logs -f ais-notify | grep Vessel    # one line per vessel: notified or why not
docker compose logs -f ais-catcher                 # decoder / dongle
docker compose restart ais-notify                  # after editing .env
docker compose up -d --build                       # after updating the code
docker compose down                                # stop everything
```

Run these from the project folder.

### Updating from your laptop

```bash
rsync -a --exclude .venv --exclude .git --exclude .env --exclude __pycache__ \
  ./ garden-pi:dev/vessel-notifications/
ssh garden-pi 'cd ~/dev/vessel-notifications && docker compose up -d --build'
```

### Troubleshooting

| Symptom | Check |
|---------|-------|
| No `Vessel …` lines for hours | `docker compose logs ais-catcher`. Test the dongle with `docker compose stop ais-catcher`, then run `AIS-catcher -o 5` in a one-off container and look for `"class":"AIS"` lines. |
| `PLL not locked!` and nothing decoded | The decoder is using a driver without Blog V4 support. Rebuild with `docker compose build --no-cache ais-catcher`. |
| `usb_claim_interface` or `no such device` | Something else holds the dongle. Make sure no other `rtl_ais` or `AIS-catcher` process or systemd service is running (`pgrep -af 'rtl_ais|AIS-catcher'`). |
| Sightings not saved, `column … does not exist` | Apply the Supabase migration above. |
| Supabase host does not resolve | The free project may be paused; resume it in the dashboard. |

---

## Run without Docker (development)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env
```

No hardware? Replay a capture file:

```bash
AIS_SOURCE=file AIS_FILE_PATH=tests/sample.nmea python -m ais_notify.main
```

Tests (fully offline):

```bash
pip install pytest
pytest tests/ -v
```

---

## Configuration

All settings live in `.env` (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `SUPABASE_URL` | — | Supabase project URL |
| `SUPABASE_KEY` | — | Supabase anon or service key |
| `TELEGRAM_BOT_TOKEN` | — | Telegram bot token |
| `TELEGRAM_CHAT_ID` | — | Chat or channel ID |
| `AIS_SOURCE` | `udp` | `udp` / `tcp` / `serial` / `file` |
| `AIS_UDP_HOST` / `AIS_UDP_PORT` | `127.0.0.1` / `10110` | UDP listener |
| `AIS_TCP_HOST` / `AIS_TCP_PORT` | `127.0.0.1` / `10110` | TCP server to connect to |
| `AIS_SERIAL_PORT` / `AIS_SERIAL_BAUD` | `/dev/ttyAMA0` / `38400` | Serial receiver (e.g. dAISy HAT) |
| `AIS_FILE_PATH` / `AIS_FILE_LOOP` | `tests/sample.nmea` / `false` | File replay |
| `DEDUP_WINDOW_SECONDS` | `300` | Minimum seconds between two Sightings of the same vessel |
| `TIMEZONE` | `UTC` | IANA timezone for daily/weekly reports |
| `LOG_LEVEL` | `INFO` | `DEBUG` is very noisy |
| `AIS_PHOTO_ENRICHMENT` | `false` | Look up vessel photos for notifications |
| `AIS_PHOTO_RECHECK_DAYS` | `30` | Days before retrying a failed photo lookup |
| `GEOFENCE_POLYGON` | *(unset)* | `lat,lon;lat,lon;…` — only vessels inside count. Unset means everything counts. |

Docker note: `docker compose` reads `.env` without a shell, so the semicolons in `GEOFENCE_POLYGON` need no quoting.

---

## Architecture

```
RTL-SDR → AIS-catcher ──(NMEA over UDP)──► AISSource (udp/tcp/serial/file)
                                                │
                                           AISDecoder (pyais)
                                                │
                                          SignalHandler
                                  geofence → dedup → enrich → notify → persist
                                                │
                                   Telegram  +  Supabase

APScheduler: daily 23:59 and weekly Sunday 23:59 reports → Telegram
```

To add an input source, implement `AISSource` in `src/ais_notify/sources/` and register it in `main._build_source()`.
