#include <Arduino.h>
#include <FastLED.h>
#include <ESP8266WiFi.h>
#include <ESPAsyncWebServer.h>
#include <ESPAsyncTCP.h>

#define LED_PIN    D4      // Pin connected to the Data input of the WS2811 strip
#define NUM_LEDS   150     // Total number of LEDs in your strip
#define LED_TYPE   WS2811  // Type of LED strip
#define COLOR_ORDER RGB    // Color order for your strip
#define BRIGHTNESS 25      // LED brightness

struct Coord { int x; int y; };

CRGB leds[NUM_LEDS];      // Array to store LED color values

Coord ledCoords[NUM_LEDS]; // Array to store LED coordinates

const char* ssid = "NOS-676B";
const char* password = "L4N9U7JC";

AsyncWebServer server(80);

bool calibration_mode = false;

void setup() {
  Serial.begin(115200);

  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("Connected! IP address: ");
  Serial.println(WiFi.localIP());

  server.on("/calibrate", HTTP_GET, [](AsyncWebServerRequest *request){
    if (request->hasParam("ledAssignment")) {
      String ledAssignment = request->getParam("ledAssignment")->value();
      // Parse the LED assignment and update the calibration data
      for(int i = 0; i < ledAssignment.length(); i++) {
        char c = ledAssignment.charAt(i);
        int ledIndex = i; // Assuming the index corresponds to the position in the string
        if (c == 'R') {
          leds[ledIndex] = CRGB::Red;
        } else if (c == 'G') {
          leds[ledIndex] = CRGB::Green;
        } else if (c == 'B') {
          leds[ledIndex] = CRGB::Blue;
        } else {
          leds[ledIndex] = CRGB::Black; // Off or unassigned
        }
      }
      Serial.println("Received LED assignment: " + ledAssignment);
      request->send(200, "text/plain", "OK");
      calibration_mode = true;
    }else{
      request->send(400, "text/plain", "Missing parameters");
    }
  });

  server.begin();

  for(int i = 0; i < NUM_LEDS; i++) {
    leds[i] = CRGB::Black; // Initialize all LEDs to off
  }

  Serial.println("Setup complete (:");
}

void loop() {
  if (calibration_mode) {
    FastLED.show();
    delay(100);
  }
}
