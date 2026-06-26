#!/usr/bin/env python3
"""
study_station.py  —  Raspberry Pi 5 study station (2 LEDs + buzzer)

Two WS2812 RGB LEDs daisy-chained on SPI0 MOSI, plus one passive piezo buzzer,
remote-controlled over MQTT. Each LED and the buzzer are independent and can run
at the same time. Default at start: all off. Blink/beep cadence: 500 ms on/off.

WIRING (Pi 5):
  LED1 DIN  -> GPIO10 / SPI0 MOSI (physical pin 19), via ~330-470 ohm
  LED1 DOUT -> LED2 DIN              (daisy chain; data flows through)
  LED +5V   -> 5V (pin 2/4)   [or 3.3V (pin 1) for a short chain]
  LED GND   -> GND (pin 6), common ground
  Buzzer A  -> GPIO18 (physical pin 12), optional ~100 ohm
  Buzzer B  -> GND (pin 14), common ground

Commands (MQTT payload, case-insensitive) on either:
    study/station/<STATION_ID>/cmd      study/station/all/cmd

  Per-LED:   L1:RED  L1:GREEN  L1:BLUE  L1:OFF   (LED 1)
             L2:RED  L2:GREEN  L2:BLUE  L2:OFF   (LED 2)
  Bare cmds (RED/GREEN/BLUE/LED_OFF) apply to LED 1 (back-compat).
  Buzzer:    BUZZER_ON  BUZZER_OFF
  Reset:     ALL_OFF    (both LEDs + buzzer off)
"""

import threading
import time

import paho.mqtt.client as mqtt
import board
import neopixel_spi as neopixel
from gpiozero import PWMOutputDevice

# ---------------- CONFIG ----------------
STATION_ID  = "2"                 # UNIQUE per station (ESP32 is "1")
MQTT_HOST   = "bingkun-mac.local" # same broker as the ESP32 stations
MQTT_PORT   = 1883
NUM_LEDS    = 2                   # daisy-chained WS2812 count
BUZZER_PIN  = 18                  # BCM GPIO (physical pin 12)
BUZZER_FREQ = 2000                # Hz; raise for a louder piezo
BLINK_S     = 0.5                 # on/off period for LEDs and buzzer
BRIGHTNESS  = 0.5                 # 0.0 - 1.0
# This LED model shows red/green swapped vs GRB. If yours shows correct
# colors, set SWAP_RG = False.
SWAP_RG     = True
# ----------------------------------------

_RED, _GREEN = (255, 0, 0), (0, 255, 0)
if SWAP_RG:
    _RED, _GREEN = _GREEN, _RED
COLORS = {"RED": _RED, "GREEN": _GREEN, "BLUE": (0, 0, 255)}

# ---- Hardware ----
pixels = neopixel.NeoPixel_SPI(
    board.SPI(), NUM_LEDS, pixel_order=neopixel.GRB,
    brightness=BRIGHTNESS, auto_write=False,
)
buzzer = PWMOutputDevice(BUZZER_PIN, frequency=BUZZER_FREQ)

# ---- State (default: everything off) ----
lock = threading.Lock()
led_colors = [None] * NUM_LEDS    # per-LED color; None = off
buzzer_on = False

# ---- Topics ----
TOPIC_CMD    = f"study/station/{STATION_ID}/cmd"
TOPIC_ALL    = "study/station/all/cmd"
TOPIC_STATUS = f"study/station/{STATION_ID}/status"


def set_led(idx: int, action: str):
    """action is RED/GREEN/BLUE/OFF; idx is 0-based LED index."""
    if not (0 <= idx < NUM_LEDS):
        print("No such LED index:", idx + 1); return False
    if action == "OFF":
        led_colors[idx] = None
    elif action in COLORS:
        led_colors[idx] = COLORS[action]
    else:
        return False
    return True


def handle(cmd: str):
    global buzzer_on
    cmd = cmd.strip().upper()
    with lock:
        if ":" in cmd:                       # e.g. L2:RED
            sel, _, action = cmd.partition(":")
            if sel.startswith("L") and sel[1:].isdigit():
                if not set_led(int(sel[1:]) - 1, action):
                    print("Bad LED command:", cmd); return
            else:
                print("Unknown command:", cmd); return
        elif cmd in COLORS:                  # bare -> LED 1
            led_colors[0] = COLORS[cmd]
        elif cmd == "LED_OFF":               # bare -> LED 1
            led_colors[0] = None
        elif cmd == "BUZZER_ON":   buzzer_on = True
        elif cmd == "BUZZER_OFF":  buzzer_on = False
        elif cmd == "ALL_OFF":
            for i in range(NUM_LEDS): led_colors[i] = None
            buzzer_on = False
        else:
            print("Unknown command:", cmd); return
    print("Command:", cmd)


def on_connect(client, userdata, flags, reason_code, properties):
    print("MQTT connected:", reason_code)
    client.publish(TOPIC_STATUS, "online", retain=True)
    client.subscribe(TOPIC_CMD)
    client.subscribe(TOPIC_ALL)
    print("Subscribed:", TOPIC_CMD, "and", TOPIC_ALL)


def on_message(client, userdata, msg):
    handle(msg.payload.decode(errors="ignore"))


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=f"pi-station-{STATION_ID}")
    client.will_set(TOPIC_STATUS, "offline", retain=True)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
    client.loop_start()

    phase = False
    try:
        while True:
            phase = not phase
            with lock:
                colors = list(led_colors)
                beep = buzzer_on
            for i in range(NUM_LEDS):
                pixels[i] = colors[i] if (colors[i] and phase) else (0, 0, 0)
            pixels.show()
            buzzer.value = 0.5 if (beep and phase) else 0.0
            time.sleep(BLINK_S)
    except KeyboardInterrupt:
        pass
    finally:
        pixels.fill((0, 0, 0)); pixels.show()
        buzzer.off()
        client.publish(TOPIC_STATUS, "offline", retain=True)
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
