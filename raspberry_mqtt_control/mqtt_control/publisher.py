from __future__ import annotations

from dataclasses import dataclass

from mqtt_control.messages import MqttMessage
from mqtt_control.simple_mqtt import publish as simple_publish


@dataclass(frozen=True)
class PublishResult:
    topic: str
    payload: str
    dry_run: bool


class MqttPublisher:
    def __init__(self, host: str, port: int, dry_run: bool = False):
        self.host = host
        self.port = port
        self.dry_run = dry_run

    def publish(self, message: MqttMessage) -> PublishResult:
        if self.dry_run:
            print(f"DRY RUN publish {message.topic} {message.payload}")
            return PublishResult(message.topic, message.payload, True)

        try:
            import paho.mqtt.publish as publish
        except ImportError as exc:
            simple_publish(
                self.host,
                self.port,
                message.topic,
                message.payload,
                client_id="raspberry-web-control",
            )
            return PublishResult(message.topic, message.payload, False)

        publish.single(message.topic, message.payload, hostname=self.host, port=self.port)
        return PublishResult(message.topic, message.payload, False)
