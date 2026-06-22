# Study Station Controller — setup

One ESP32 station = one addressable RGB LED (GPIO 25) + one passive buzzer (GPIO 26),
remote-controlled over MQTT. LED and buzzer are independent and can run at the same time.
Default at boot: both off. Blink/beep cadence: 500 ms on / 500 ms off.

## Pieces
- `../RemoteControl_LED_Buzzer.ino` — the ESP32 firmware.
- `dashboard.html` — click-button control panel (open in a browser on the Mac).
- `mosquitto-websockets.conf` — broker config enabling TCP (1883) + WebSockets (9001).

## 1. Broker on the MacBook
```sh
brew install mosquitto          # if not already installed
ipconfig getifaddr en0          # note this IP -> put it in the .ino as MQTT_HOST
mosquitto -c mosquitto-websockets.conf -v
```
Allow `mosquitto` through the macOS firewall if prompted (port 1883). Keep the Mac
awake and on the same Wi-Fi for the whole session.

## 2. Flash each station
In `RemoteControl_LED_Buzzer.ino` edit the three marked values:
- `WIFI_SSID` / `WIFI_PASS` — the network the Mac is on (avoid campus/guest Wi-Fi;
  client isolation blocks the ESP32 from reaching the Mac).
- `MQTT_HOST` — the Mac's IP from step 1.
- `STATION_ID` — a UNIQUE id per physical unit: `"1"`, `"2"`, `"3"`, …

Flash one board per id.

## 3. Control
Open `dashboard.html`. Set the station IDs (e.g. `1,2,3`), click **Connect**, then use the
per-station buttons. **ALL OFF** resets every station at once (between trials).

## Command reference
Topics: `study/station/<id>/cmd` (one station) or `study/station/all/cmd` (broadcast).

| Payload | Effect |
|---|---|
| `RED` / `GREEN` / `BLUE` | LED blinks that color |
| `LED_OFF` | LED off |
| `BUZZER_ON` / `BUZZER_OFF` | buzzer beep on / off |
| `ALL_OFF` | LED + buzzer off |

Each station publishes `online` / `offline` (last will) to `study/station/<id>/status`,
so you can detect a dropped station mid-session.

## Manual test from Terminal (optional)
```sh
mosquitto_pub -h localhost -t study/station/1/cmd -m RED
mosquitto_pub -h localhost -t study/station/all/cmd -m ALL_OFF
mosquitto_sub -h localhost -t 'study/station/+/status' -v   # watch station health
```
