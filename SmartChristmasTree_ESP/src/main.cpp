#include <Arduino.h>
#include <FastLED.h>
#include <ESP8266WiFi.h>
#include <ESPAsyncWebServer.h>
#include <ESPAsyncTCP.h>

#define LED_PIN    D4      // Pin connected to the Data input of the WS2811 strip
#define NUM_LEDS   150     // Total number of LEDs in your strip
#define LED_TYPE   WS2811  // Type of LED strip
#define COLOR_ORDER RGB    // Color order
#define BRIGHTNESS 25      // LED brightness
#define NUM_FRAMES 15       // Number of frames in the calibration pattern
#define FRAME_DELAY 1000    // Delay between frames in milliseconds

struct Coord { int x; int y; };

CRGB patternTable [NUM_LEDS][NUM_FRAMES] = {};

CRGB leds[NUM_LEDS];      // Array to store LED color values

Coord ledCoords[NUM_LEDS]; // Array to store LED coordinates

const char* ssid = "NOS-676B"; // Your WiFi SSID
const char* password = "L4N9U7JC"; // Your WiFi password

IPAddress local_IP(192, 168, 1, 200);   // desired static IP
IPAddress gateway(192, 168, 1, 1);
IPAddress subnet(255, 255, 255, 0);

AsyncWebServer server(80);

bool calibration_mode = false;

CRGB getColorFromChar(char c);
void playCalibrationSequence();
void connectToWiFi();
void UpAndDownEffect();

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
                        patternTable[i][j] == CRGB::Blue ? "B" : "X");
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

  server.on("/calibrated_leds", HTTP_GET, [](AsyncWebServerRequest *request){
    if (request->hasParam("ledsPositions")) {
      String ledsPositions = request->getParam("ledsPositions")->value();
      // Parse the LED positions and update the ledCoords array
      int len = ledsPositions.length();
      int ledIndex = 0;
      int i = 0;
      while (i < len && ledIndex < NUM_LEDS) {
        int colonIndex = ledsPositions.indexOf(':', i);
        int commaIndex = ledsPositions.indexOf(',', colonIndex);
        int semicolonIndex = ledsPositions.indexOf(';', commaIndex);
        if (colonIndex == -1 || commaIndex == -1) break;

        int x = ledsPositions.substring(colonIndex + 1, commaIndex).toInt();
        int y = (semicolonIndex == -1) ? ledsPositions.substring(commaIndex + 1).toInt() : ledsPositions.substring(commaIndex + 1, semicolonIndex).toInt();

        ledCoords[ledIndex].x = x;
        ledCoords[ledIndex].y = y;

        ledIndex++;
        i = (semicolonIndex == -1) ? len : semicolonIndex + 1;
      }
      request->send(200, "text/plain", "LED positions updated");
    } else {
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
    delay(1000);
    playCalibrationSequence();
    calibration_mode = false;
    connectToWiFi();
    server.begin();
  }
  else {
    if(ledCoords[0].x == 0 && ledCoords[0].y == 0)
      return; // no coordinates set yet
    UpAndDownEffect();
  }
}

CRGB getColorFromChar(char c) {
  switch (c) {
    case 'R': return CRGB::Red;
    case 'G': return CRGB::Green;
    case 'B': return CRGB::Blue;
    default:  return CRGB::Black;
  }
}

void UpAndDownEffect() {
  // Simple vertical sweep using the Y coordinate of each LED in ledCoords.
  // A bright band moves up and down; LEDs brightness is based on distance to the band center.
  static float posY = 0.0f;
  static int dir = 1; // 1 = moving down (increasing Y), -1 = moving up
  const float speed = 2.5f; // pixels per frame
  const int bandRadius = 40; // how many pixels the band affects

  // Compute minY and maxY from known coordinates. If no coordinates set, use defaults.
  int minY = 1000;
  int maxY = -1000;
  bool anyCoords = false;
  for (int i = 0; i < NUM_LEDS; i++) {
    int y = ledCoords[i].y;
    int x = ledCoords[i].x;
    // consider a coord valid if either x or y is non-zero
    if (x != 0 || y != 0) {
      anyCoords = true;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
    }
  }
  if (!anyCoords) {
    // fallback values if coordinates haven't been set yet
    minY = 0;
    maxY = 240;
  }

  // Initialize posY to minY on first run
  if (posY == 0.0f) posY = (float)minY;

  // Move the band
  posY += dir * speed;
  if (posY > maxY) {
    posY = (float)maxY;
    dir = -1;
  } else if (posY < minY) {
    posY = (float)minY;
    dir = 1;
  }

  // Draw LEDs: white band with falloff
  for (int i = 0; i < NUM_LEDS; i++) {
    int y = ledCoords[i].y;
    // distance between LED and current band center
    int dist = abs((int)round(posY) - y);
    uint8_t brightness = 0;
    if (dist < bandRadius) {
      // linear falloff
      brightness = (uint8_t)(255 - ((uint16_t)dist * 255) / bandRadius);
    } else {
      brightness = 0;
    }

    // Set base color to white and scale by brightness so color is consistent across hardware
    leds[i] = CRGB::White;
    // nscale8_video dims the color while preserving relative channels
    leds[i].nscale8_video(brightness);
  }

  FastLED.show();
  // Small delay for visible motion; tune as needed
  delay(30);
}

void playCalibrationSequence() {
    // Sync flash
    FastLED.setBrightness(100);
    delay(500);
    fill_solid(leds, NUM_LEDS, CRGB::White);
    FastLED.show();
    delay(1000);
    FastLED.clear();
    FastLED.show();
    delay(1000);

    // Play pattern frames
    FastLED.setBrightness(1);
    for (int f = 0; f < NUM_FRAMES; f++) {
        for (int i = 0; i < NUM_LEDS; i++) {
            leds[i] = patternTable[i][f];
        }
        FastLED.show();
        delay(FRAME_DELAY);
    }

    // End flash
    FastLED.setBrightness(100);
    fill_solid(leds, NUM_LEDS, CRGB::White);
    FastLED.show();
    delay(1000);
    FastLED.clear();
}

void connectToWiFi() {
  WiFi.config(local_IP, gateway, subnet);
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