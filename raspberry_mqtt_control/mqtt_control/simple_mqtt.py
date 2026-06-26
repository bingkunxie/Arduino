from __future__ import annotations

import socket
import struct
import time
from dataclasses import dataclass


def encode_remaining_length(length: int) -> bytes:
    if length < 0:
        raise ValueError("remaining length cannot be negative")

    encoded = bytearray()
    while True:
        byte = length % 128
        length //= 128
        if length > 0:
            byte |= 128
        encoded.append(byte)
        if length == 0:
            return bytes(encoded)


def encode_utf8(text: str) -> bytes:
    data = text.encode("utf-8")
    return struct.pack("!H", len(data)) + data


def encode_connect_packet(client_id: str, keepalive: int = 60) -> bytes:
    variable_header = (
        encode_utf8("MQTT")
        + bytes([4, 2])
        + struct.pack("!H", keepalive)
    )
    payload = encode_utf8(client_id)
    remaining = variable_header + payload
    return bytes([0x10]) + encode_remaining_length(len(remaining)) + remaining


def encode_publish_packet(topic: str, payload: str | bytes) -> bytes:
    payload_bytes = payload if isinstance(payload, bytes) else payload.encode("utf-8")
    remaining = encode_utf8(topic) + payload_bytes
    return bytes([0x30]) + encode_remaining_length(len(remaining)) + remaining


def encode_subscribe_packet(packet_id: int, topic: str) -> bytes:
    remaining = struct.pack("!H", packet_id) + encode_utf8(topic) + bytes([0])
    return bytes([0x82]) + encode_remaining_length(len(remaining)) + remaining


def encode_disconnect_packet() -> bytes:
    return bytes([0xE0, 0])


def read_remaining_length(sock: socket.socket) -> int:
    multiplier = 1
    value = 0
    while True:
        byte = sock.recv(1)
        if not byte:
            raise ConnectionError("MQTT connection closed while reading remaining length")
        digit = byte[0]
        value += (digit & 127) * multiplier
        if (digit & 128) == 0:
            return value
        multiplier *= 128
        if multiplier > 128 * 128 * 128:
            raise ValueError("Malformed MQTT remaining length")


def read_packet(sock: socket.socket) -> tuple[int, bytes]:
    header = sock.recv(1)
    if not header:
        raise ConnectionError("MQTT connection closed")
    remaining_length = read_remaining_length(sock)
    payload = bytearray()
    while len(payload) < remaining_length:
        chunk = sock.recv(remaining_length - len(payload))
        if not chunk:
            raise ConnectionError("MQTT connection closed while reading packet")
        payload.extend(chunk)
    return header[0], bytes(payload)


def connect(sock: socket.socket, client_id: str, keepalive: int = 60) -> None:
    sock.sendall(encode_connect_packet(client_id, keepalive))
    packet_type, payload = read_packet(sock)
    if packet_type != 0x20 or len(payload) < 2 or payload[1] != 0:
        raise ConnectionError(f"MQTT CONNACK failed: packet_type={packet_type:#x} payload={payload!r}")


def publish(host: str, port: int, topic: str, payload: str, client_id: str) -> None:
    with socket.create_connection((host, port), timeout=5) as sock:
        connect(sock, client_id)
        sock.sendall(encode_publish_packet(topic, payload))
        sock.sendall(encode_disconnect_packet())


@dataclass(frozen=True)
class IncomingMessage:
    topic: str
    payload: bytes


def decode_publish_packet(payload: bytes) -> IncomingMessage:
    if len(payload) < 2:
        raise ValueError("MQTT publish packet too short")
    topic_length = struct.unpack("!H", payload[:2])[0]
    topic_start = 2
    topic_end = topic_start + topic_length
    topic = payload[topic_start:topic_end].decode("utf-8")
    message_payload = payload[topic_end:]
    return IncomingMessage(topic=topic, payload=message_payload)


def subscribe_forever(
    host: str,
    port: int,
    topic: str,
    client_id: str,
    on_message,
    keepalive: int = 60,
) -> None:
    with socket.create_connection((host, port), timeout=10) as sock:
        sock.settimeout(1)
        connect(sock, client_id, keepalive)
        sock.sendall(encode_subscribe_packet(1, topic))

        last_ping = time.monotonic()
        while True:
            try:
                packet_type, payload = read_packet(sock)
            except socket.timeout:
                if time.monotonic() - last_ping >= keepalive / 2:
                    sock.sendall(bytes([0xC0, 0]))
                    last_ping = time.monotonic()
                continue

            packet_kind = packet_type & 0xF0
            if packet_kind == 0x30:
                on_message(decode_publish_packet(payload))
            elif packet_kind in {0x90, 0xD0}:
                continue

