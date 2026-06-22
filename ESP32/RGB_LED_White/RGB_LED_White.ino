#include <Adafruit_NeoPixel.h>

#define DATA_PIN   25   // GPIO wired to Data In
#define NUM_LEDS   1

Adafruit_NeoPixel led(NUM_LEDS, DATA_PIN, NEO_GRB + NEO_KHZ800);

void setup() {
  led.begin();
  led.setBrightness(200); // 0–255
  led.setPixelColor(0, led.Color(200, 255, 0)); //
  led.show();
}

void loop() {
  // Nothing to do — the LED stays white.
}
