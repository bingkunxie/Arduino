from __future__ import annotations

import json
from dataclasses import dataclass


BASE_TOPIC = "raspberry/stations"
VALID_STATES = {"on", "off"}
LED_COLORS = {
    "white": [255, 255, 255],
    "red": [255, 0, 0],
    "yellow": [255, 255, 0],
    "green": [0, 255, 0],
}


@dataclass(frozen=True)
class MqttMessage:
    topic: str
    payload: str


def build_pair_command(station_id: str, pair_id: int, state: str) -> MqttMessage:
    normalized_state = state.lower()
    if normalized_state not in VALID_STATES:
        raise ValueError(f"state must be one of {sorted(VALID_STATES)}")

    topic = f"{BASE_TOPIC}/{station_id}/pairs/{int(pair_id)}/set"
    payload = json.dumps({"state": normalized_state}, separators=(",", ":"))
    return MqttMessage(topic=topic, payload=payload)


def build_led_command(station_id: str, pair_id: int, color: str) -> MqttMessage:
    normalized_color = color.lower()
    if normalized_color not in LED_COLORS:
        raise ValueError(f"color must be one of {sorted(LED_COLORS)}")

    topic = f"{BASE_TOPIC}/{station_id}/pairs/{int(pair_id)}/set"
    payload = json.dumps(
        {
            "target": "led",
            "color": normalized_color,
            "rgb": LED_COLORS[normalized_color],
        },
        separators=(",", ":"),
    )
    return MqttMessage(topic=topic, payload=payload)


def build_led_off_command(station_id: str, pair_id: int) -> MqttMessage:
    topic = f"{BASE_TOPIC}/{station_id}/pairs/{int(pair_id)}/set"
    payload = json.dumps(
        {
            "target": "led",
            "action": "off",
            "rgb": [0, 0, 0],
        },
        separators=(",", ":"),
    )
    return MqttMessage(topic=topic, payload=payload)


def build_buzzer_command(station_id: str, pair_id: int) -> MqttMessage:
    topic = f"{BASE_TOPIC}/{station_id}/pairs/{int(pair_id)}/set"
    payload = json.dumps(
        {
            "target": "buzzer",
            "action": "beep",
            "on_seconds": 0.25,
            "off_seconds": 0.25,
            "repeat": 1,
        },
        separators=(",", ":"),
    )
    return MqttMessage(topic=topic, payload=payload)


def build_buzzer_off_command(station_id: str, pair_id: int) -> MqttMessage:
    topic = f"{BASE_TOPIC}/{station_id}/pairs/{int(pair_id)}/set"
    payload = json.dumps(
        {
            "target": "buzzer",
            "action": "off",
        },
        separators=(",", ":"),
    )
    return MqttMessage(topic=topic, payload=payload)


def station_subscription_topic(station_id: str) -> str:
    return f"{BASE_TOPIC}/{station_id}/pairs/+/set"
