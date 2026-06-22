# Raspberry Pi 5 study station

A Pi-based station that behaves identically to the ESP32 ones: WS2812 RGB LED +
passive piezo buzzer, controlled over MQTT from the same dashboard/broker.

## Wiring (Pi 5 — uses SPI, NOT the old GPIO18 PWM method)
| Component | Pi 5 pin |
|---|---|
| LED DIN | GPIO10 / SPI0 MOSI — **physical pin 19** (via ~330–470 Ω) |
| LED +5V | 5V (pin 2/4); or 3.3V (pin 1) for one LED without a level shifter |
| LED GND | GND (pin 6) — common ground |
| Buzzer pin A | GPIO18 — **physical pin 12** (optional ~100 Ω) |
| Buzzer pin B | GND (pin 14) — common ground |

## 1. One-time setup (Pi must be on an INTERNET network for this)
SSH into the Pi from your Mac, then:
```sh
# Enable the SPI bus (needed for the LED)
sudo raspi-config nonint do_spi 0

# Create an isolated environment that can still see system GPIO libs
python3 -m venv ~/station-venv --system-site-packages
source ~/station-venv/bin/activate
pip install adafruit-circuitpython-neopixel-spi paho-mqtt gpiozero lgpio

sudo reboot      # for SPI enable to take effect
```

## 2. Copy the script to the Pi
From your Mac:
```sh
scp ~/Documents/RaspberryPi/study_station/study_station.py <user>@station2.local:~/
```
Edit `STATION_ID` in the script to a unique value per Pi (the ESP32 is `"1"`).

## 3. Run it
On the Pi (during the study it must be on the same local Wi-Fi as the Mac broker):
```sh
source ~/station-venv/bin/activate
python ~/study_station.py
```
You should see `MQTT connected`. Drive it from the dashboard's Station 2 buttons,
or test from the Mac:
```sh
mosquitto_pub -h localhost -t study/station/2/cmd -m RED
mosquitto_pub -h localhost -t study/station/all/cmd -m ALL_OFF
```

## Run automatically on boot (optional)
Create `/etc/systemd/system/study-station.service`:
```ini
[Unit]
Description=Study station
After=network-online.target
Wants=network-online.target

[Service]
User=<user>
ExecStart=/home/<user>/station-venv/bin/python /home/<user>/study_station.py
Restart=always

[Install]
WantedBy=multi-user.target
```
Then: `sudo systemctl enable --now study-station`

## Notes
- Don't forget to add `2` (and any other Pi ids) to the dashboard's Station IDs field.
- If red/green look swapped, flip `SWAP_RG` in the script (set to match your LED).
- If the buzzer errors on gpiozero, prefix the run with `GPIOZERO_PIN_FACTORY=lgpio`.
- `pip` complains about an "externally managed environment"? You're outside the venv —
  re-run `source ~/station-venv/bin/activate` first.
