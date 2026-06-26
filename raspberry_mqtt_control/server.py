#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from mqtt_control.config import load_stations, station_by_id
from mqtt_control.messages import (
    build_buzzer_command,
    build_buzzer_off_command,
    build_led_command,
    build_led_off_command,
    build_pair_command,
)
from mqtt_control.publisher import MqttPublisher


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = PROJECT_DIR / "stations.json"
LED_COLORS = ("white", "red", "yellow", "green")


def station_uses_split_controls(station) -> bool:
    return station.rgb_gpio is not None and station.station_id in {"station5", "station6", "station7"}


def render_dashboard(stations, broker_host: str, dry_run: bool, notice: str = "") -> str:
    station_sections = []
    for station in stations:
        pair_controls = []
        for pair in station.pairs:
            pin_labels = []
            if station.has_buzzer:
                pin_labels.append(f"Buzzer GPIO {pair.gpio}")
            if station.rgb_gpio is not None:
                pin_labels.append(f"RGB GPIO {station.rgb_gpio}")
            if not pin_labels:
                pin_labels.append(f"GPIO {pair.gpio}")

            if station_uses_split_controls(station):
                color_buttons = []
                for color in LED_COLORS:
                    color_buttons.append(
                        f"""
                        <button
                          name="color"
                          value="{color}"
                          class="color {color}"
                          title="Set {html.escape(pair.name)} LED to {color}"
                        >{color.title()}</button>
                        """
                    )
                controls = f"""
                  <form method="post" action="/control" class="control-group led-group" data-control-form>
                    <input type="hidden" name="station_id" value="{html.escape(station.station_id)}">
                    <input type="hidden" name="pair_id" value="{pair.pair_id}">
                    <input type="hidden" name="target" value="led">
                    <span class="group-label">LED</span>
                    {''.join(color_buttons)}
                    <button name="action" value="off" class="off led-off">LED Off</button>
                  </form>
                  <form method="post" action="/control" class="control-group buzzer-group" data-control-form>
                    <input type="hidden" name="station_id" value="{html.escape(station.station_id)}">
                    <input type="hidden" name="pair_id" value="{pair.pair_id}">
                    <input type="hidden" name="target" value="buzzer">
                    <span class="group-label">Buzzer</span>
                    <button name="action" value="beep" class="beep">Beep</button>
                    <button name="action" value="off" class="off buzzer-off">Buzzer Off</button>
                  </form>
                """
            else:
                controls = f"""
                  <form method="post" action="/control" data-control-form>
                    <input type="hidden" name="station_id" value="{html.escape(station.station_id)}">
                    <input type="hidden" name="pair_id" value="{pair.pair_id}">
                    <button name="state" value="on" class="on">On</button>
                    <button name="state" value="off" class="off">Off</button>
                  </form>
                """

            pair_controls.append(
                f"""
                <div class="pair-row">
                  <div>
                    <strong>{html.escape(pair.name)}</strong>
                    <span>{html.escape(' | '.join(pin_labels))}</span>
                  </div>
                  <div class="controls">
                    {controls}
                  </div>
                </div>
                """
            )

        status_text = station.status.title()
        status_class = "online" if station.status.lower() == "online" else "offline"
        station_sections.append(
            f"""
            <section class="station">
              <header>
                <div>
                  <h2>{html.escape(station.name)}</h2>
                  <span>{html.escape(station.host)}</span>
                </div>
                <span class="status {status_class}">{html.escape(status_text)}</span>
              </header>
              <p class="hardware">{html.escape(station.hardware)}</p>
              {''.join(pair_controls)}
            </section>
            """
        )

    notice_html = html.escape(notice) if notice else ""
    dry_text = "dry run" if dry_run else "live MQTT"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Raspberry Pi Station Control</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: Arial, Helvetica, sans-serif;
      background: #f5f7f8;
      color: #1d252d;
    }}
    body {{
      margin: 0;
      padding: clamp(14px, 2.4vw, 28px);
    }}
    main {{
      max-width: 1480px;
      margin: 0 auto;
    }}
    h1 {{
      margin: 0 0 6px;
      font-size: clamp(23px, 3vw, 28px);
      line-height: 1.15;
      letter-spacing: 0;
    }}
    .meta {{
      margin: 0 0 22px;
      color: #5d6873;
      font-size: 14px;
    }}
    #notice {{
      background: #e9f5ee;
      border: 1px solid #b8dec8;
      display: none;
      margin: 0 0 16px;
      padding: 10px 12px;
      border-radius: 6px;
      color: #184f2f;
    }}
    #notice:not(:empty) {{
      display: block;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
      gap: 16px;
    }}
    .station {{
      background: #fff;
      border: 1px solid #dce2e6;
      border-radius: 8px;
      box-sizing: border-box;
      container-type: inline-size;
      padding: 16px;
      min-width: 0;
    }}
    .station header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 12px;
      border-bottom: 1px solid #edf1f3;
      padding-bottom: 10px;
      margin-bottom: 10px;
    }}
    h2 {{
      margin: 0;
      font-size: 18px;
      letter-spacing: 0;
    }}
    .hardware {{
      margin: 0 0 8px;
      color: #41505d;
      font-size: 13px;
      line-height: 1.35;
    }}
    .status {{
      border-radius: 999px;
      font-size: 12px;
      line-height: 1;
      padding: 5px 8px;
      white-space: nowrap;
    }}
    .status.online {{
      background: #dff3e7;
      color: #14633b;
    }}
    .status.offline {{
      background: #eef1f3;
      color: #5b6770;
    }}
    .station header span,
    .pair-row span {{
      color: #697681;
      font-size: 13px;
    }}
    .pair-row {{
      display: grid;
      grid-template-columns: minmax(118px, 150px) minmax(0, 1fr);
      align-items: start;
      gap: 14px;
      padding: 10px 0;
      min-height: 44px;
    }}
    .pair-row + .pair-row {{
      border-top: 1px solid #edf1f3;
    }}
    .controls {{
      display: grid;
      gap: 8px;
      justify-items: stretch;
      min-width: 0;
    }}
    form {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 0;
    }}
    .control-group {{
      display: grid;
      align-items: center;
      width: 100%;
    }}
    .led-group {{
      grid-template-columns: 56px repeat(5, minmax(64px, 1fr));
    }}
    .buzzer-group {{
      grid-template-columns: 56px repeat(2, minmax(94px, 1fr));
    }}
    .group-label {{
      color: #41505d;
      font-size: 12px;
      font-weight: 700;
      text-align: right;
      text-transform: uppercase;
    }}
    button {{
      border: 0;
      border-radius: 6px;
      color: #fff;
      cursor: pointer;
      font-size: 14px;
      line-height: 1.1;
      min-height: 38px;
      min-width: 54px;
      padding: 8px 12px;
      white-space: nowrap;
    }}
    button.on {{
      background: #197047;
    }}
    button.off {{
      background: #8f2f2f;
    }}
    button.beep {{
      background: #5f4b8b;
    }}
    button.led-off,
    button.buzzer-off {{
      min-width: 76px;
    }}
    button.color.white {{
      background: #f7f7f2;
      border: 1px solid #b8bfc5;
      color: #1d252d;
    }}
    button.color.red {{
      background: #bd3333;
    }}
    button.color.yellow {{
      background: #d2a319;
      color: #1d252d;
    }}
    button.color.green {{
      background: #197047;
    }}
    @container (max-width: 620px) {{
      body {{
        padding: 14px;
      }}
      .pair-row {{
        grid-template-columns: 1fr;
      }}
      .controls {{
        justify-items: stretch;
      }}
      .control-group {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
      .group-label {{
        grid-column: 1 / -1;
        text-align: left;
      }}
      button {{
        width: 100%;
      }}
    }}
    @media (max-width: 520px) {{
      .grid {{
        grid-template-columns: minmax(0, 1fr);
      }}
    }}
  </style>
</head>
<body>
  <main>
    <h1>Raspberry Pi Station Control</h1>
    <p class="meta">Broker: {html.escape(broker_host)} | Mode: {dry_text}</p>
    <p id="notice">{notice_html}</p>
    <div class="grid">
      {''.join(station_sections)}
    </div>
  </main>
  <script>
    const notice = document.getElementById('notice');
    document.querySelectorAll('[data-control-form]').forEach((form) => {{
      form.addEventListener('submit', async (event) => {{
        event.preventDefault();
        const clicked = event.submitter;
        const body = new URLSearchParams(new FormData(form));
        if (clicked && clicked.name) {{
          body.set(clicked.name, clicked.value);
        }}
        const actionUrl = form.getAttribute('action') || window.location.href;
        const response = await fetch(actionUrl, {{
          method: 'POST',
          headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
          body
        }});
        const result = await response.json();
        notice.textContent = result.message || result.error || '';
      }});
    }});
  </script>
</body>
</html>"""


class ControlHandler(BaseHTTPRequestHandler):
    stations = []
    publisher: MqttPublisher
    broker_host = ""
    dry_run = False

    def do_GET(self) -> None:
        if self.path not in {"/", "/index.html", "/control"}:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self._send_html(render_dashboard(self.stations, self.broker_host, self.dry_run))

    def do_POST(self) -> None:
        if self.path != "/control":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        form = parse_qs(body)

        station_id = form.get("station_id", [""])[0]
        pair_text = form.get("pair_id", [""])[0]
        state = form.get("state", [""])[0]
        target = form.get("target", [""])[0]
        color = form.get("color", [""])[0]
        action = form.get("action", [""])[0]

        station = station_by_id(self.stations, station_id)
        if station is None:
            self.send_error(HTTPStatus.BAD_REQUEST, "Unknown station")
            return

        pair_id = int(pair_text)
        if pair_id not in {pair.pair_id for pair in station.pairs}:
            self.send_error(HTTPStatus.BAD_REQUEST, "Unknown pair")
            return

        try:
            if target == "led":
                if action == "off":
                    message = build_led_off_command(station_id, pair_id)
                else:
                    message = build_led_command(station_id, pair_id, color)
            elif target == "buzzer":
                if action == "off":
                    message = build_buzzer_off_command(station_id, pair_id)
                elif action == "beep":
                    message = build_buzzer_command(station_id, pair_id)
                else:
                    raise ValueError("buzzer action must be beep or off")
            else:
                message = build_pair_command(station_id, pair_id, state)
            result = self.publisher.publish(message)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_GATEWAY)
            return

        notice = f"Published {result.topic} {result.payload}"
        if self.headers.get("Accept", "").startswith("text/html"):
            self._send_html(render_dashboard(self.stations, self.broker_host, self.dry_run, notice))
        else:
            self._send_json({"message": notice, "topic": result.topic, "payload": result.payload})

    def log_message(self, format: str, *args) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _send_html(self, text: str) -> None:
        data = text.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, data: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(data, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def make_handler(stations, publisher: MqttPublisher, broker_host: str, dry_run: bool):
    class BoundControlHandler(ControlHandler):
        pass

    BoundControlHandler.stations = stations
    BoundControlHandler.publisher = publisher
    BoundControlHandler.broker_host = broker_host
    BoundControlHandler.dry_run = dry_run
    return BoundControlHandler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Web UI for Raspberry Pi MQTT control.")
    parser.add_argument("--host", default="0.0.0.0", help="Web server bind host.")
    parser.add_argument("--port", default=8080, type=int, help="Web server port.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to stations JSON.")
    parser.add_argument("--mqtt-host", default="localhost", help="MQTT broker host.")
    parser.add_argument("--mqtt-port", default=1883, type=int, help="MQTT broker port.")
    parser.add_argument("--dry-run", action="store_true", help="Print MQTT messages instead of publishing.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    stations = load_stations(args.config)
    publisher = MqttPublisher(args.mqtt_host, args.mqtt_port, dry_run=args.dry_run)
    handler = make_handler(stations, publisher, args.mqtt_host, args.dry_run)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Serving dashboard on http://{args.host}:{args.port}")
    print(f"MQTT broker: {args.mqtt_host}:{args.mqtt_port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
