# Raspberry Pi MQTT Station Control

This project provides a web dashboard that sends MQTT commands to Raspberry Pi stations. Stations 5-7 have separate controls for addressable RGB LEDs and passive buzzers.

## Current Live Setup

- MQTT broker: `10.131.197.116:1883`
- Web dashboard port used in testing: `8081`
- Station client directory on each Pi: `/home/eaglevision/raspberry_mqtt_control`

## Controls

Stations 1-4 keep the original pair On/Off controls.

Stations 5-7 show separate LED and buzzer controls per pair:

- `White`: set that pair's RGB LED to full-brightness white.
- `Red`: set that pair's RGB LED to full-brightness red.
- `Yellow`: set that pair's RGB LED to full-brightness yellow.
- `Green`: set that pair's RGB LED to full-brightness green.
- `LED Off`: turn off only that pair's RGB LED.
- `Beep`: pulse that pair's buzzer on for `0.25` seconds, then off for `0.25` seconds.
- `Buzzer Off`: turn off only that pair's buzzer output.

Stations 5-7 use one addressable RGB LED per pair on GPIO 10 MOSI. Buzzers use the same GPIO wiring as Stations 1-4:

| Pair | Buzzer GPIO | RGB index |
| --- | --- | --- |
| Pair 1 | 17 | 0 |
| Pair 2 | 27 | 1 |
| Pair 3 | 22 | 2 |
| Pair 4 | 23 | 3 |

## Run The Web Server

From this folder:

```bash
cd /Users/bingkunxie/Documents/Arduino/raspberry_mqtt_control
python3 server.py --host 0.0.0.0 --port 8081 --mqtt-host 10.131.197.116
```

Open:

```text
http://127.0.0.1:8081
```

For a dry run that prints MQTT messages instead of publishing them:

```bash
python3 server.py --dry-run --host 127.0.0.1 --port 18081
```

## Run Station Clients

On Station 5:

```bash
cd /home/eaglevision/raspberry_mqtt_control
python3 -u ./station_client.py --station-id station5 --mqtt-host 10.131.197.116
```

On Stations 6 and 7, GPIO/SPI access required `sudo` during testing:

```bash
cd /home/eaglevision/raspberry_mqtt_control
sudo python3 -u ./station_client.py --station-id station6 --mqtt-host 10.131.197.116
sudo python3 -u ./station_client.py --station-id station7 --mqtt-host 10.131.197.116
```

## MQTT Topic And Payloads

All commands use:

```text
raspberry/stations/<station_id>/pairs/<pair_id>/set
```

LED command example:

```json
{"target":"led","color":"red","rgb":[255,0,0]}
```

Buzzer command example:

```json
{"target":"buzzer","action":"beep","on_seconds":0.25,"off_seconds":0.25,"repeat":1}
```

LED off command example:

```json
{"target":"led","action":"off","rgb":[0,0,0]}
```

Buzzer off command example:

```json
{"target":"buzzer","action":"off"}
```

Legacy On/Off command example:

```json
{"state":"on"}
```

## Files

- `server.py`: web dashboard and MQTT publisher.
- `station_client.py`: MQTT subscriber and GPIO/SPI controller.
- `stations.json`: station IPs, pair GPIOs, and RGB mapping.
- `mqtt_control/`: shared config, message, MQTT, and publish helpers.
- `tests/test_mqtt_control.py`: unit tests for config, message payloads, dashboard controls, and MQTT packet encoding.
