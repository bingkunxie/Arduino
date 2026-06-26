#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import signal
import time
from dataclasses import dataclass

from mqtt_control.config import Pair, Station, load_stations, station_by_id
from mqtt_control.messages import station_subscription_topic
from mqtt_control.simple_mqtt import IncomingMessage, subscribe_forever


def parse_color(text: str) -> tuple[int, int, int]:
    parts = [int(part.strip()) for part in text.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("color must be R,G,B")
    if any(part < 0 or part > 255 for part in parts):
        raise argparse.ArgumentTypeError("color values must be between 0 and 255")
    return parts[0], parts[1], parts[2]


class SpiRgbStrip:
    def __init__(
        self,
        total_leds: int,
        leds_per_pair: int,
        on_color: tuple[int, int, int],
        dry_run: bool,
    ):
        self.total_leds = total_leds
        self.leds_per_pair = leds_per_pair
        self.on_color = on_color
        self.dry_run = dry_run
        self.pixels = [(0, 0, 0)] * total_leds
        self.spi = None

        if not dry_run:
            import spidev

            self.spi = spidev.SpiDev()
            self.spi.open(0, 0)
            self.spi.max_speed_hz = 2400000
            self.spi.mode = 0
            self.show()

    def set_pair(self, pair_id: int, enabled: bool) -> None:
        self.set_pair_color(pair_id, self.on_color if enabled else (0, 0, 0))

    def set_pair_color(self, pair_id: int, color: tuple[int, int, int]) -> None:
        start = (pair_id - 1) * self.leds_per_pair
        end = min(start + self.leds_per_pair, self.total_leds)
        for index in range(start, end):
            self.pixels[index] = color

        if self.dry_run:
            print(f"DRY RUN RGB pair {pair_id}: {color}")
        else:
            self.show()

    def all_off(self) -> None:
        self.pixels = [(0, 0, 0)] * self.total_leds
        if self.dry_run:
            print("DRY RUN RGB all off")
        else:
            self.show()

    def show(self) -> None:
        if self.spi is None:
            return
        self.spi.xfer3(self._encode_frame())

    def close(self) -> None:
        self.all_off()
        if self.spi is not None:
            self.spi.close()

    def _encode_frame(self) -> list[int]:
        bits = []
        for red, green, blue in self.pixels:
            for value in (green, red, blue):
                for bit in range(7, -1, -1):
                    bits.extend((1, 1, 0) if value & (1 << bit) else (1, 0, 0))

        encoded = []
        for index in range(0, len(bits), 8):
            byte = 0
            for bit in bits[index : index + 8]:
                byte = (byte << 1) | bit
            encoded.append(byte << (8 - len(bits[index : index + 8])))

        return encoded + [0] * 80


@dataclass
class PairOutput:
    pair: Pair
    buzzer: object | None
    rgb: SpiRgbStrip | None

    def on(self) -> None:
        if self.buzzer is None:
            print(f"{self.pair.name} buzzer GPIO {self.pair.gpio}: no buzzer output")
        else:
            self.buzzer.value = 0.5

        if self.rgb is not None:
            self.rgb.set_pair(self.pair.pair_id, True)

    def set_led_color(self, color: tuple[int, int, int]) -> None:
        if self.rgb is None:
            print(f"{self.pair.name}: no RGB output")
            return
        self.rgb.set_pair_color(self.pair.pair_id, color)

    def beep(self, on_seconds: float, off_seconds: float, repeat: int) -> None:
        if self.buzzer is None:
            print(f"{self.pair.name}: no buzzer output")
            return
        for _ in range(repeat):
            self.buzzer.value = 0.5
            time.sleep(on_seconds)
            self.buzzer.value = 0
            time.sleep(off_seconds)

    def buzzer_off(self) -> None:
        if self.buzzer is not None:
            self.buzzer.value = 0

    def off(self) -> None:
        self.buzzer_off()

        if self.rgb is not None:
            self.rgb.set_pair(self.pair.pair_id, False)

    def close(self) -> None:
        self.off()
        if self.buzzer is not None:
            self.buzzer.close()


class StationController:
    def __init__(
        self,
        station: Station,
        frequency_hz: int,
        dry_run: bool,
        rgb_leds_per_pair: int | None,
        rgb_color: tuple[int, int, int],
    ):
        rgb = None
        if station.rgb_gpio is not None:
            leds_per_pair = rgb_leds_per_pair or station.rgb_leds_per_pair
            rgb = SpiRgbStrip(
                total_leds=len(station.pairs) * leds_per_pair,
                leds_per_pair=leds_per_pair,
                on_color=rgb_color,
                dry_run=dry_run,
            )

        self.rgb = rgb
        self.outputs = {
            pair.pair_id: PairOutput(
                pair=pair,
                buzzer=self._make_buzzer(pair, frequency_hz, dry_run, station.has_buzzer),
                rgb=rgb,
            )
            for pair in station.pairs
        }

    def _make_buzzer(self, pair: Pair, frequency_hz: int, dry_run: bool, has_buzzer: bool):
        if not has_buzzer:
            return None
        if dry_run:
            return DryRunBuzzer(pair)

        from gpiozero import Device
        from gpiozero import PWMOutputDevice
        from gpiozero.pins.rpigpio import RPiGPIOFactory

        if Device.pin_factory is None or Device.pin_factory.__class__.__name__ != "RPiGPIOFactory":
            Device.pin_factory = RPiGPIOFactory()

        return PWMOutputDevice(
            pair.gpio,
            active_high=True,
            initial_value=0,
            frequency=frequency_hz,
        )

    def set_pair(self, pair_id: int, state: str) -> None:
        output = self.outputs.get(pair_id)
        if output is None:
            print(f"Ignoring unknown pair {pair_id}")
            return
        if state == "on":
            output.on()
        elif state == "off":
            output.off()
        else:
            print(f"Ignoring invalid state {state!r}")

    def set_led(self, pair_id: int, rgb: list[int]) -> None:
        output = self.outputs.get(pair_id)
        if output is None:
            print(f"Ignoring unknown pair {pair_id}")
            return
        output.set_led_color((int(rgb[0]), int(rgb[1]), int(rgb[2])))

    def beep_buzzer(self, pair_id: int, on_seconds: float, off_seconds: float, repeat: int) -> None:
        output = self.outputs.get(pair_id)
        if output is None:
            print(f"Ignoring unknown pair {pair_id}")
            return
        output.beep(on_seconds, off_seconds, repeat)

    def stop_buzzer(self, pair_id: int) -> None:
        output = self.outputs.get(pair_id)
        if output is None:
            print(f"Ignoring unknown pair {pair_id}")
            return
        output.buzzer_off()

    def all_off(self) -> None:
        for output in self.outputs.values():
            output.off()
        if self.rgb is not None:
            self.rgb.all_off()

    def close(self) -> None:
        for output in self.outputs.values():
            output.close()
        if self.rgb is not None:
            self.rgb.close()


class DryRunBuzzer:
    def __init__(self, pair: Pair):
        self.pair = pair
        self._value = 0

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, value: float) -> None:
        self._value = value
        state = "ON" if value else "OFF"
        print(f"DRY RUN {self.pair.name} buzzer GPIO {self.pair.gpio}: {state}")

    def close(self) -> None:
        self.value = 0


def extract_pair_id(topic: str) -> int:
    parts = topic.split("/")
    return int(parts[-2])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Raspberry Pi MQTT station client.")
    parser.add_argument("--station-id", required=True, help="Station id from stations.json, such as station5.")
    parser.add_argument("--config", default="stations.json", help="Path to stations JSON.")
    parser.add_argument("--mqtt-host", default="localhost", help="MQTT broker host.")
    parser.add_argument("--mqtt-port", default=1883, type=int, help="MQTT broker port.")
    parser.add_argument("--frequency", default=2000, type=int, help="Passive buzzer PWM frequency.")
    parser.add_argument(
        "--rgb-leds-per-pair",
        default=None,
        type=int,
        help="Override the number of addressable RGB LEDs per pair from stations.json.",
    )
    parser.add_argument("--rgb-color", default=(0, 80, 0), type=parse_color, help="RGB on color as R,G,B.")
    parser.add_argument("--reconnect-delay", default=5, type=float, help="Seconds to wait before reconnecting MQTT.")
    parser.add_argument("--dry-run", action="store_true", help="Print actions instead of controlling GPIO/RGB.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    station = station_by_id(load_stations(args.config), args.station_id)
    if station is None:
        raise SystemExit(f"Unknown station id: {args.station_id}")

    controller = StationController(
        station,
        frequency_hz=args.frequency,
        dry_run=args.dry_run,
        rgb_leds_per_pair=args.rgb_leds_per_pair,
        rgb_color=args.rgb_color,
    )
    topic = station_subscription_topic(station.station_id)
    client_id = f"{station.station_id}-client"

    def handle_signal(signum, frame):
        controller.close()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    def handle_payload(topic_text: str, payload_bytes: bytes) -> None:
        payload = json.loads(payload_bytes.decode("utf-8"))
        pair_id = extract_pair_id(topic_text)
        target = str(payload.get("target", "")).lower()
        if target == "led":
            action = str(payload.get("action", "")).lower()
            rgb = payload.get("rgb", [0, 0, 0] if action == "off" else None)
            if rgb is None:
                print(f"Command {topic_text}: invalid LED payload")
                return
            print(f"Command {topic_text}: led {payload.get('color', action or rgb)}")
            controller.set_led(pair_id, rgb)
            return
        if target == "buzzer":
            action = str(payload.get("action", "")).lower()
            if action == "beep":
                print(f"Command {topic_text}: buzzer beep")
                controller.beep_buzzer(
                    pair_id,
                    float(payload.get("on_seconds", 0.25)),
                    float(payload.get("off_seconds", 0.25)),
                    int(payload.get("repeat", 1)),
                )
                return
            if action == "off":
                print(f"Command {topic_text}: buzzer off")
                controller.stop_buzzer(pair_id)
                return
            print(f"Command {topic_text}: invalid buzzer action {action!r}")
            return
        state = str(payload.get("state", "")).lower()
        print(f"Command {topic_text}: {state}")
        controller.set_pair(pair_id, state)

    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        print(f"paho-mqtt not installed; using built-in MQTT client for {topic}")

        def on_simple_message(message: IncomingMessage) -> None:
            handle_payload(message.topic, message.payload)

        while True:
            try:
                subscribe_forever(args.mqtt_host, args.mqtt_port, topic, client_id, on_simple_message)
            except (ConnectionError, OSError) as exc:
                print(f"MQTT connection lost: {exc}; reconnecting in {args.reconnect_delay} seconds")
                time.sleep(args.reconnect_delay)
            except KeyboardInterrupt:
                controller.close()
                raise
        return

    def on_connect(client, userdata, flags, reason_code, properties=None):
        print(f"Connected to MQTT broker, subscribing to {topic}")
        client.subscribe(topic)

    def on_message(client, userdata, msg):
        handle_payload(msg.topic, msg.payload)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(args.mqtt_host, args.mqtt_port)
        client.loop_forever()
    finally:
        controller.close()


if __name__ == "__main__":
    main()
