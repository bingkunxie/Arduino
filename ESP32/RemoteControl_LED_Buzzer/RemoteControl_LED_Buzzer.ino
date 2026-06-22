/*
 * RemoteControl_LED_Buzzer
 * ------------------------
 * MQTT remote control for a user-study station: one addressable RGB LED
 * (WS2812 on GPIO 25) and a passive piezo buzzer (GPIO 26).
 *
 * LED and buzzer are controlled INDEPENDENTLY and can run SIMULTANEOUSLY.
 * Default at boot: both OFF. Blink/beep cadence: 500 ms on / 500 ms off,
 * driven by non-blocking millis() timing so MQTT stays responsive.
 *
 * Commands (MQTT payload, case-insensitive) sent to either:
 *     study/station/<STATION_ID>/cmd   (this station only)
 *     study/station/all/cmd            (every station at once)
 *
 *     RED         -> LED blinks red
 *     GREEN       -> LED blinks green
 *     BLUE        -> LED blinks blue
 *     LED_OFF     -> LED off
 *     BUZZER_ON   -> buzzer beeps
 *     BUZZER_OFF  -> buzzer off
 *     ALL_OFF     -> LED + buzzer off (reset between trials)
 *
 * Status: publishes "online" to study/station/<STATION_ID>/status on connect,
 * and an MQTT last-will "offline" if the station drops (lets you spot a dead
 * station during a session).
 *
 * Requires libraries: Adafruit NeoPixel, PubSubClient (both already installed).
 * Buzzer uses tone()/noTone() (ESP32 Arduino core 3.x).
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <Adafruit_NeoPixel.h>

// ---------- STATION CONFIG ----------
#define WIFI_SSID    "YOUR_WIFI_SSID"
#define WIFI_PASS    "YOUR_WIFI_PASSWORD"
// Mac's mDNS name (works on any local network without knowing its IP).
// Found via: scutil --get LocalHostName  ->  bingkun-mac
#define MQTT_HOST    "bingkun-mac.local"
// Give each physical station a UNIQUE id: "1", "2", "3", ...
#define STATION_ID   "1"
// ------------------------------------

#define MQTT_PORT    1883
#define DATA_PIN     25     // WS2812 Data In
#define BUZZER_PIN   26     // passive piezo
#define BUZZER_FREQ  2000   // Hz; adjust to your buzzer's loudest pitch
#define BLINK_MS     500    // on/off period for both LED and buzzer
#define LED_BRIGHT   120    // 0-255

Adafruit_NeoPixel led(1, DATA_PIN, NEO_GRB + NEO_KHZ800);
WiFiClient   wifiClient;
PubSubClient mqtt(wifiClient);

// Topics (built once in setup)
char topicCmd[48];
char topicAll[48];
char topicStatus[48];

// ---- State (default: everything off) ----
enum LedMode { LED_OFF_MODE, LED_RED, LED_GREEN, LED_BLUE };
LedMode ledMode  = LED_OFF_MODE;
bool    buzzerOn = false;

bool          phase = false;          // shared 500 ms on/off phase
unsigned long lastToggle = 0;

// Apply current state to the hardware for the given phase.
void applyOutputs() {
  // LED
  uint32_t color = 0;
  if (ledMode != LED_OFF_MODE && phase) {
    switch (ledMode) {
      // This LED's R/G channels are swapped vs the NEO_GRB assumption,
      // so RED and GREEN use exchanged values to display correctly.
      case LED_RED:   color = led.Color(0,   255, 0);   break;
      case LED_GREEN: color = led.Color(255, 0,   0);   break;
      case LED_BLUE:  color = led.Color(0,   0,   255); break;
      default: break;
    }
  }
  led.setPixelColor(0, color);
  led.show();

  // Buzzer
  if (buzzerOn && phase) tone(BUZZER_PIN, BUZZER_FREQ);
  else                   noTone(BUZZER_PIN);
}

void handleCommand(String cmd) {
  cmd.trim();
  cmd.toUpperCase();

  if      (cmd == "RED")        ledMode = LED_RED;
  else if (cmd == "GREEN")      ledMode = LED_GREEN;
  else if (cmd == "BLUE")       ledMode = LED_BLUE;
  else if (cmd == "LED_OFF")    ledMode = LED_OFF_MODE;
  else if (cmd == "BUZZER_ON")  buzzerOn = true;
  else if (cmd == "BUZZER_OFF") buzzerOn = false;
  else if (cmd == "ALL_OFF")  { ledMode = LED_OFF_MODE; buzzerOn = false; }
  else { Serial.printf("Unknown command: %s\n", cmd.c_str()); return; }

  Serial.printf("Command: %s\n", cmd.c_str());
  applyOutputs();   // respond immediately, don't wait for next toggle
}

void onMessage(char* topic, byte* payload, unsigned int len) {
  String msg;
  for (unsigned int i = 0; i < len; i++) msg += (char)payload[i];
  handleCommand(msg);
}

void connectWifi() {
  Serial.printf("WiFi: connecting to %s", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    delay(400);
    Serial.print(".");
  }
  Serial.printf("\nWiFi: connected, IP %s\n", WiFi.localIP().toString().c_str());
}

void connectMqtt() {
  while (!mqtt.connected()) {
    String clientId = String("station-") + STATION_ID + "-" + String((uint32_t)ESP.getEfuseMac(), HEX);
    Serial.printf("MQTT: connecting to %s:%d ...", MQTT_HOST, MQTT_PORT);
    // Last will: broker publishes "offline" (retained) if we drop unexpectedly.
    if (mqtt.connect(clientId.c_str(), nullptr, nullptr,
                     topicStatus, 0, true, "offline")) {
      Serial.println(" connected");
      mqtt.publish(topicStatus, "online", true);
      mqtt.subscribe(topicCmd);
      mqtt.subscribe(topicAll);
      Serial.printf("Subscribed: %s  and  %s\n", topicCmd, topicAll);
    } else {
      Serial.printf(" failed (rc=%d), retry in 2s\n", mqtt.state());
      delay(2000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(BUZZER_PIN, OUTPUT);
  led.begin();
  led.setBrightness(LED_BRIGHT);
  led.show();   // start dark

  snprintf(topicCmd,    sizeof(topicCmd),    "study/station/%s/cmd",    STATION_ID);
  snprintf(topicAll,    sizeof(topicAll),    "study/station/all/cmd");
  snprintf(topicStatus, sizeof(topicStatus), "study/station/%s/status", STATION_ID);

  connectWifi();
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onMessage);
  connectMqtt();

  applyOutputs();   // enforce default-off state
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWifi();
  if (!mqtt.connected()) connectMqtt();
  mqtt.loop();

  unsigned long now = millis();
  if (now - lastToggle >= BLINK_MS) {
    lastToggle = now;
    phase = !phase;
    applyOutputs();
  }
}
