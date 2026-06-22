#include <Adafruit_NeoPixel.h>

#define DATA_PIN   25    // GPIO wired to Data In
#define NUM_LEDS   1

Adafruit_NeoPixel led(NUM_LEDS, DATA_PIN, NEO_GRB + NEO_KHZ800);


struct NamedColor {
  const char *name;
  uint8_t g, r, b;
};


NamedColor colors[] = {
  { "White", 255, 255, 255},
  { "red",  0, 255, 0 },
  { "orange", 85,  255,   0 },
  { "yellow", 200, 255,   0 },
  { "green", 255, 0, 0},
  { "blue", 0, 0, 255},
  { "purple", 25, 162, 255 },
};

const uint8_t NUM_COLORS = sizeof(colors) / sizeof(colors[0]);

void setup() {
  led.begin();
  led.setBrightness(200);   // 0–255, keep low while testing
  led.show();              // start off
}

void loop() {
  for (uint8_t i = 0; i < NUM_COLORS; i++) {
    led.setPixelColor(0, led.Color(colors[i].g, colors[i].r, colors[i].b));
    led.show();
    delay(120);
  }
}
