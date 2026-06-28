# AIS Vessel Notifications

A Python application for Raspberry Pi that:
- Receives AIS signals from an RTL-SDR dongle via **rtl-ais** or **AIS-catcher**
- Stores vessel sightings in **Supabase** (PostgreSQL)
- Enriches vessel data from the AIS signal itself (name, type, size, flag)
- Sends instant **Telegram** notifications on new sightings
- Posts **daily and weekly stats** to Telegram

The AIS input source is fully swappable (UDP → TCP → serial → file replay).

---

## Hardware requirements

| Component | Notes |
|-----------|-------|
| Raspberry Pi (any model) | Pi 3/4/5 recommended |
| RTL-SDR dongle | e.g. RTL-SDR Blog V3 |
| VHF antenna (156–162 MHz) | AIS frequencies |

Alternatively, a dedicated receiver like the **dAISy HAT** outputs NMEA over serial (set `AIS_SOURCE=serial`).

---

## Quick start

### 1. Install AIS-catcher (RTL-SDR decoder)

**On macOS (testing without hardware)** — skip this step entirely. Use the file replay source in step 5 instead.

**On Raspberry Pi (production):**

```bash
# Install curl if not already present
sudo apt install curl

# Install AIS-catcher (downloads binary + all SDR dependencies)
sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/jvde-github/AIS-catcher/main/scripts/aiscatcher-install) -p"
```

Configure it to forward NMEA to our app over UDP:

```bash
sudo nano /etc/AIS-catcher/config.cmd
```

Add this line and save:

```
-u 127.0.0.1 10110
```

Enable and start the service:

```bash
sudo systemctl enable --now ais-catcher.service
```

**On macOS (with a real RTL-SDR dongle attached):** AIS-catcher has no Homebrew formula and must be built from source — see the [macOS install guide](https://jvde-github.github.io/AIS-catcher-docs/installation/macos/). Once built, run it manually (no systemd on macOS):

```bash
AIS-catcher -u 127.0.0.1 10110
```

### 2. Set up Supabase

1. Create a free project at [supabase.com](https://supabase.com).
2. In the Supabase **SQL editor**, run the contents of `supabase/schema.sql`.
3. Copy your project URL and anon/service key.

### 3. Create a Telegram bot

1. Chat with [@BotFather](https://t.me/BotFather) → `/newbot` and follow the prompts.
2. Copy the bot token into `TELEGRAM_BOT_TOKEN`.
3. Add the bot to your channel or group.
4. Get the chat ID:
   - Send any message to the chat (or `/start` in a private chat with the bot).
   - Open this URL in your browser (replace the token):
     ```
     https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
     ```
   - Find `"chat": { "id": ... }` in the JSON response — that number is your `TELEGRAM_CHAT_ID`.

> **ID format by chat type:**
> - Private chat with the bot: positive number (`123456789`)
> - Group: negative number (`-123456789`)
> - Channel: negative number starting with `-100` (`-1001234567890`)
>
> If `getUpdates` returns an empty result, send the bot a message first (in a group, type `@yourbotname hello`).

### 4. Install the app

```bash
git clone https://github.com/yourusername/vessel-notifications.git
cd vessel-notifications

python3 -m venv .venv
source .venv/bin/activate
pip install -e .

cp .env.example .env
# Edit .env with your Supabase URL/key, Telegram token/chat ID, etc.
```

### 5. Test without hardware (file replay)

```bash
AIS_SOURCE=file AIS_FILE_PATH=tests/sample.nmea python -m ais_notify.main
```

You should see decoded vessels in the logs. With valid Supabase/Telegram credentials set, sightings will be stored and a Telegram notification sent.

### 6. Run in production

```bash
# Start manually
source .venv/bin/activate
ais-notify
```

---

## Systemd auto-start on the Pi

Copy both service files and enable them:

```bash
sudo cp deploy/rtl-ais.service /etc/systemd/system/
sudo cp deploy/ais-notify.service /etc/systemd/system/

# Edit the paths in ais-notify.service if needed
sudo nano /etc/systemd/system/ais-notify.service

sudo systemctl daemon-reload
sudo systemctl enable rtl-ais ais-notify
sudo systemctl start rtl-ais ais-notify

# Monitor logs
journalctl -u ais-notify -f
```

---

## Configuration

All settings live in `.env` (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `SUPABASE_URL` | — | Your Supabase project URL |
| `SUPABASE_KEY` | — | Your Supabase anon or service key |
| `TELEGRAM_BOT_TOKEN` | — | Telegram bot token |
| `TELEGRAM_CHAT_ID` | — | Chat or channel ID |
| `AIS_SOURCE` | `udp` | Input source: `udp` / `tcp` / `serial` / `file` |
| `AIS_UDP_HOST` | `127.0.0.1` | rtl-ais UDP host |
| `AIS_UDP_PORT` | `10110` | rtl-ais UDP port |
| `AIS_TCP_HOST` | `127.0.0.1` | TCP server host |
| `AIS_TCP_PORT` | `10110` | TCP server port |
| `AIS_SERIAL_PORT` | `/dev/ttyAMA0` | Serial port (dAISy HAT) |
| `AIS_SERIAL_BAUD` | `38400` | Serial baud rate |
| `AIS_FILE_PATH` | `tests/sample.nmea` | NMEA file for replay |
| `AIS_FILE_LOOP` | `false` | Loop file replay |
| `DEDUP_WINDOW_SECONDS` | `300` | Minimum seconds between duplicate alerts |
| `TIMEZONE` | `UTC` | IANA timezone for daily/weekly reports |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `AIS_PHOTO_ENRICHMENT` | `false` | Enable Wikidata photo lookup |

---

## Swapping the input source

The `AISSource` abstraction makes it trivial to change the data input:

```
AIS_SOURCE=udp     # RTL-SDR via rtl-ais or AIS-catcher (default)
AIS_SOURCE=tcp     # Any TCP NMEA server (SignalK, AIS-catcher --server mode)
AIS_SOURCE=serial  # dAISy HAT or other serial AIS receiver
AIS_SOURCE=file    # Replay a .nmea capture file (testing)
```

To add a completely new source (e.g. MQTT, WebSocket):
1. Create `src/ais_notify/sources/my_source.py` implementing `AISSource`.
2. Add a case for it in `main._build_source()`.
3. No other files need to change.

---

## Architecture

```
RTL-SDR + rtl-ais
      │ (NMEA UDP)
      ▼
 AISSource adapter  ◄─── swappable (UDP/TCP/serial/file)
      │
      ▼
 AISDecoder (pyais)  ─── multi-part assembly, type 1/2/3/5/18/24
      │
      ▼
 SignalHandler
   ├─ DedupCache (5-min TTL + DB fallback)
   ├─ Enrichment chain (AIS static → ship type → MMSI country → photo)
   ├─ Telegram notification  ◄── sent FIRST for low latency
   └─ Supabase persist (sightings + vessels)

 APScheduler
   ├─ Daily 23:59 → stats query → Telegram
   └─ Weekly Sun 23:59 → stats query → Telegram
```

---

## Running tests

```bash
pip install pytest
pytest tests/ -v
```

The test suite runs fully offline using `FileSource` with `tests/sample.nmea`.
Tests for the DB layer and Telegram require mocking (see individual test files).

---

## Adding vessel photo enrichment

Photos are disabled by default. To enable Wikidata lookups (free, covers notable ships):

```
AIS_PHOTO_ENRICHMENT=true
```

For a richer paid source (all vessels), add your key and implement `_lookup_photo_*` in `src/ais_notify/enrich/photo.py`:

```
AIS_VESSEL_API_KEY=your_key_here   # VesselAPI, Datalastic, etc.
```

---

## Extending the system

| Feature | Where to add |
|---------|-------------|
| New notification channel (email, Slack…) | Implement `Notifier` protocol in `src/ais_notify/notify/` |
| Geofencing / watchlist alerts | Add a pre-notification filter in `handler.py` |
| Paid vessel enrichment API | Add a provider in `src/ais_notify/enrich/` |
| Local SQLite offline buffer | Wrap `repository.py` with a write-ahead buffer |
| Live web dashboard | Query Supabase via a Next.js / Grafana frontend |
