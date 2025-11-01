#include <Arduino.h>
#include <FastLED.h>
#include <ESP8266WiFi.h>
#include <ESPAsyncWebServer.h>
#include <ESPAsyncTCP.h>

#define LED_PIN    D4      // Pin connected to the Data input of the WS2811 strip
#define NUM_LEDS   150     // Total number of LEDs in your strip
#define LED_TYPE   WS2811  // Type of LED strip
#define COLOR_ORDER GRB    // Color order (GRB is typical for WS2811)
#define BRIGHTNESS 25      // LED brightness
#define NUM_FRAMES 6       // Number of frames in the calibration pattern
#define FRAME_DELAY 1000    // Delay between frames in milliseconds

struct Coord { int x; int y; };

CRGB patternTable [NUM_LEDS][NUM_FRAMES] = {};

CRGB leds[NUM_LEDS];      // Array to store LED color values

Coord ledCoords[NUM_LEDS]; // Array to store LED coordinates

const char* ssid = "NOS-676B";
const char* password = "L4N9U7JC";

AsyncWebServer server(80);

bool calibration_mode = false;

CRGB getColorFromChar(char c);
void playCalibrationSequence();
void connectToWiFi();

void setup() {
  Serial.begin(115200);

  FastLED.addLeds<LED_TYPE, LED_PIN, COLOR_ORDER>(leds, NUM_LEDS);
  FastLED.setBrightness(BRIGHTNESS);

  connectToWiFi();

  server.on("/calibrate", HTTP_GET, [](AsyncWebServerRequest *request){
    if (request->hasParam("ledAssignment")) {
      String ledAssignment = request->getParam("ledAssignment")->value();
      // Parse the LED assignment and update the calibration data
      int len = ledAssignment.length();
      for (int i = 0; i < NUM_LEDS; i++) {
        for (int j = 0; j < NUM_FRAMES; j++) {
          int idx = i * NUM_FRAMES + j; // expecting 6 chars per LED
          if (idx < len) {
            patternTable[i][j] = getColorFromChar(ledAssignment.charAt(idx));
          } else {
            patternTable[i][j] = CRGB::Black;
          }
        }
      }
      for(int i = 0; i < NUM_LEDS; i++) {
        Serial.print("LED ");
        Serial.print(i);
        Serial.print(": ");
        for(int j = 0; j < NUM_FRAMES; j++) {
          Serial.print( patternTable[i][j] == CRGB::Red ? "R" :
                        patternTable[i][j] == CRGB::Green ? "G" :
                        patternTable[i][j] == CRGB::Blue ? "B" :
                        patternTable[i][j] == CRGB::Yellow ? "Y" :
                        patternTable[i][j] == CRGB::Purple ? "P" :
                        patternTable[i][j] == CRGB::Cyan ? "C" :
                        patternTable[i][j] == CRGB::Violet ? "V" :
                        patternTable[i][j] == CRGB::Orange ? "N" :
                        patternTable[i][j] == CRGB::Magenta ? "M" : "X");
          if (j < NUM_FRAMES - 1) Serial.print(", ");
        }
        Serial.println();
      }
      request->send(200, "text/plain", "OK");
      calibration_mode = true;
    }else{
      request->send(400, "text/plain", "Missing parameters");
    }
  });

  server.begin();

  delay(1000); // Wait a moment before starting

  for(int i = 0; i < NUM_LEDS; i++) {
    leds[i] = CRGB::Red; // Initialize all LEDs to off
  }
  FastLED.show();

  Serial.println("Setup complete (:");
  delay(1000); // Wait a moment before starting
}

void loop() {
  if (calibration_mode) {
    server.end();
    WiFi.disconnect();
    playCalibrationSequence();
    calibration_mode = false;
    connectToWiFi();
    server.begin();
  }
  else {
    // Ensure LEDs remain solid red in normal operation
    for (int i = 0; i < NUM_LEDS; i++) {
      leds[i] = CRGB::Red;
    }
    FastLED.show();
    delay(100);

    for(int i = 0; i < NUM_LEDS; i++) {
      leds[i] = CRGB::Green;
    }
    FastLED.show();
    delay(100);
  }
}

CRGB getColorFromChar(char c) {
  switch (c) {
    case 'R': return CRGB::Red;
    case 'G': return CRGB::Green;
    case 'B': return CRGB::Blue;
    case 'Y': return CRGB::Yellow;
    case 'P': return CRGB::Purple;
    case 'C': return CRGB::Cyan;
    case 'V': return CRGB::Violet;
    case 'N': return CRGB::Orange;
    case 'M': return CRGB::Magenta;
    default:  return CRGB::Black;
  }
}

void playCalibrationSequence() {
    // Sync flash
    fill_solid(leds, NUM_LEDS, CRGB::White);
    FastLED.show();
    delay(1000);
    FastLED.clear();
    delay(500);

    // Play pattern frames
    for (int f = 0; f < NUM_FRAMES; f++) {
        for (int i = 0; i < NUM_LEDS; i++) {
            leds[i] = patternTable[i][f];
        }
        FastLED.show();
        delay(FRAME_DELAY);
    }

    // End flash
    fill_solid(leds, NUM_LEDS, CRGB::White);
    FastLED.show();
    delay(1000);
    FastLED.clear();
}

void connectToWiFi() {
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("Connected! IP address: ");
  Serial.println(WiFi.localIP());
}