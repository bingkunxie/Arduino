import json
import tempfile
import unittest
from pathlib import Path

from mqtt_control.config import load_stations
from mqtt_control.messages import (
    build_buzzer_command,
    build_buzzer_off_command,
    build_led_command,
    build_led_off_command,
    build_pair_command,
)
from mqtt_control.simple_mqtt import encode_publish_packet
from server import render_dashboard
from station_client import SpiRgbStrip


class ConfigTests(unittest.TestCase):
    def test_loads_stations_from_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "stations.json"
            config_path.write_text(
                json.dumps(
                    {
                        "stations": [
                            {
                                "id": "station1",
                                "name": "Station 1",
                                "host": "10.131.230.114",
                                "hardware": "PWM buzzer + GPIO output",
                                "status": "offline",
                                "rgb_gpio": None,
                                "pairs": [
                                    {"id": 1, "name": "Pair 1", "gpio": 17},
                                    {"id": 2, "name": "Pair 2", "gpio": 27},
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            stations = load_stations(config_path)

        self.assertEqual(len(stations), 1)
        self.assertEqual(stations[0].station_id, "station1")
        self.assertEqual(stations[0].pairs[1].gpio, 27)
        self.assertEqual(stations[0].hardware, "PWM buzzer + GPIO output")
        self.assertEqual(stations[0].status, "offline")
        self.assertIsNone(stations[0].rgb_gpio)

    def test_loads_rgb_station_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "stations.json"
            config_path.write_text(
                json.dumps(
                    {
                        "stations": [
                            {
                                "id": "station5",
                                "name": "Station 5",
                                "host": "10.131.34.51",
                                "hardware": "Addressable RGB LEDs",
                                "status": "online",
                                "has_buzzer": True,
                                "rgb_gpio": 10,
                                "pairs": [
                                    {"id": 1, "name": "Pair 1 RGB LEDs", "gpio": 10},
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            station = load_stations(config_path)[0]

        self.assertEqual(station.station_id, "station5")
        self.assertEqual(station.hardware, "Addressable RGB LEDs")
        self.assertEqual(station.status, "online")
        self.assertEqual(station.rgb_gpio, 10)
        self.assertTrue(station.has_buzzer)

    def test_dashboard_renders_all_station_metadata(self):
        stations = load_stations("stations.json")

        html = render_dashboard(stations, broker_host="localhost", dry_run=True)

        self.assertIn("Station 7", html)
        self.assertIn("10.131.246.201", html)
        self.assertIn("Online", html)
        self.assertIn("RGB GPIO 10", html)

    def test_online_rgb_stations_have_buzzer_pins(self):
        stations = {station.station_id: station for station in load_stations("stations.json")}

        for station_id in ("station5", "station6", "station7"):
            station = stations[station_id]
            self.assertTrue(station.has_buzzer)
            self.assertEqual(station.rgb_gpio, 10)
            self.assertEqual(station.rgb_leds_per_pair, 1)
            self.assertEqual([pair.gpio for pair in station.pairs], [17, 27, 22, 23])

    def test_dashboard_renders_separate_rgb_and_buzzer_controls(self):
        stations = load_stations("stations.json")

        html = render_dashboard(stations, broker_host="localhost", dry_run=True)

        self.assertIn('data-control-form', html)
        self.assertIn('class="control-group led-group"', html)
        self.assertIn('name="target" value="led"', html)
        self.assertIn('value="white"', html)
        self.assertIn('value="red"', html)
        self.assertIn('value="yellow"', html)
        self.assertIn('value="green"', html)
        self.assertIn('name="action" value="off"', html)
        self.assertIn("LED Off", html)
        self.assertIn('class="control-group buzzer-group"', html)
        self.assertIn('name="target" value="buzzer"', html)
        self.assertIn('name="action" value="beep"', html)
        self.assertIn("Buzzer Off", html)
        self.assertIn("form.getAttribute('action')", html)
        self.assertIn("fetch(actionUrl", html)
        self.assertIn("grid-template-columns: repeat(auto-fit, minmax(420px, 1fr))", html)
        self.assertIn("container-type: inline-size", html)
        self.assertIn("@container (max-width: 620px)", html)


class MessageTests(unittest.TestCase):
    def test_builds_pair_command_topic_and_payload(self):
        message = build_pair_command("station2", 3, "on")

        self.assertEqual(
            message.topic,
            "raspberry/stations/station2/pairs/3/set",
        )
        self.assertEqual(json.loads(message.payload), {"state": "on"})

    def test_rejects_invalid_pair_state(self):
        with self.assertRaises(ValueError):
            build_pair_command("station2", 3, "blink")

    def test_builds_led_command_payload(self):
        message = build_led_command("station5", 2, "yellow")

        self.assertEqual(message.topic, "raspberry/stations/station5/pairs/2/set")
        self.assertEqual(
            json.loads(message.payload),
            {
                "target": "led",
                "action": "blink",
                "color": "yellow",
                "rgb": [255, 255, 0],
                "on_seconds": 0.25,
                "off_seconds": 0.25,
            },
        )

    def test_builds_led_off_command_payload(self):
        message = build_led_off_command("station5", 2)

        self.assertEqual(message.topic, "raspberry/stations/station5/pairs/2/set")
        self.assertEqual(
            json.loads(message.payload),
            {"target": "led", "action": "off", "rgb": [0, 0, 0]},
        )

    def test_builds_buzzer_command_payload(self):
        message = build_buzzer_command("station5", 2)

        self.assertEqual(message.topic, "raspberry/stations/station5/pairs/2/set")
        self.assertEqual(
            json.loads(message.payload),
            {
                "target": "buzzer",
                "action": "beep",
                "on_seconds": 0.25,
                "off_seconds": 0.25,
                "repeat": 14,
            },
        )

    def test_builds_buzzer_off_command_payload(self):
        message = build_buzzer_off_command("station5", 2)

        self.assertEqual(message.topic, "raspberry/stations/station5/pairs/2/set")
        self.assertEqual(
            json.loads(message.payload),
            {"target": "buzzer", "action": "off"},
        )


class SimpleMqttTests(unittest.TestCase):
    def test_encode_publish_packet_contains_topic_and_payload(self):
        packet = encode_publish_packet("raspberry/stations/station5/pairs/2/set", '{"state":"on"}')

        self.assertEqual(packet[0], 0x30)
        self.assertIn(b"raspberry/stations/station5/pairs/2/set", packet)
        self.assertTrue(packet.endswith(b'{"state":"on"}'))


class SpiRgbStripTests(unittest.TestCase):
    def test_wire_values_do_not_swap_red_and_green(self):
        self.assertEqual(SpiRgbStrip.wire_values((255, 0, 0)), (255, 0, 0))
        self.assertEqual(SpiRgbStrip.wire_values((0, 255, 0)), (0, 255, 0))


if __name__ == "__main__":
    unittest.main()
