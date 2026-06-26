from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Pair:
    pair_id: int
    name: str
    gpio: int


@dataclass(frozen=True)
class Station:
    station_id: str
    name: str
    host: str
    hardware: str
    status: str
    rgb_gpio: int | None
    rgb_leds_per_pair: int
    has_buzzer: bool
    pairs: tuple[Pair, ...]


def load_stations(config_path: str | Path) -> list[Station]:
    path = Path(config_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    stations: list[Station] = []

    for station_data in data.get("stations", []):
        pairs = tuple(
            Pair(
                pair_id=int(pair_data["id"]),
                name=str(pair_data["name"]),
                gpio=int(pair_data["gpio"]),
            )
            for pair_data in station_data.get("pairs", [])
        )
        stations.append(
            Station(
                station_id=str(station_data["id"]),
                name=str(station_data["name"]),
                host=str(station_data.get("host", "")),
                hardware=str(station_data.get("hardware", "GPIO outputs")),
                status=str(station_data.get("status", "offline")),
                rgb_gpio=(
                    int(station_data["rgb_gpio"])
                    if station_data.get("rgb_gpio") is not None
                    else None
                ),
                rgb_leds_per_pair=int(station_data.get("rgb_leds_per_pair", 1)),
                has_buzzer=bool(station_data.get("has_buzzer", True)),
                pairs=pairs,
            )
        )

    return stations


def station_by_id(stations: list[Station], station_id: str) -> Station | None:
    for station in stations:
        if station.station_id == station_id:
            return station
    return None
