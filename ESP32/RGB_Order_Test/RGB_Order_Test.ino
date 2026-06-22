#include <Adafruit_NeoPixel.h>

#define DATA_PIN   25   // GPIO wired to Data In
#define NUM_LEDS   1

// Diagnostic: commands pure RED, then GREEN, then BLUE for 2s each.
// Watch the LED and compare to what the Serial Monitor prints.
//   - If the LED matches every time  -> order is GRB (keep NEO_GRB)
//   - If RED/GREEN are swapped       -> order is RGB (use NEO_RGB)
//   - Anything else                  -> note the mapping and tell me
Adafruit_NeoPixel led(NUM_LEDS, DATA_PIN, NEO_GRB + NEO_KHZ800);

void show(const char *name, uint8_t r, uint8_t g, uint8_t b) {
  Serial.print("Commanding: ");
  Serial.println(name);
  led.setPixelColor(0, led.Color(r, g, b));
  led.show();
  delay(2000);
}

void setup() {
  Serial.begin(115200);
  led.begin();
  led.setBrightness(50);
  led.show();
}

void loop() {
  show("RED",   255, 0,   0);
  show("GREEN", 0,   255, 0);
  show("BLUE",  0,   0,   255);
}
