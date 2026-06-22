#include <Adafruit_NeoPixel.h>

#define DATA_PIN   25    // GPIO wired to Data In
#define NUM_LEDS   1

Adafruit_NeoPixel led(NUM_LEDS, DATA_PIN, NEO_GRB + NEO_KHZ800);

void setup() {
  led.begin();
  led.setBrightness(50);   // 0–255, keep low while testing
  led.show();              // start off
}

void loop() {
  led.setPixelColor(0, led.Color(255, 0, 0)); led.show(); delay(500); // red
  led.setPixelColor(0, led.Color(0, 255, 0)); led.show(); delay(500); // green
  led.setPixelColor(0, led.Color(0, 0, 255)); led.show(); delay(500); // blue
}