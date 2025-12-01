#include <Arduino.h>
#include <FastLED.h>
#include <ESP8266WiFi.h>
#include <ESPAsyncWebServer.h>
#include <ESPAsyncTCP.h>
#include <LittleFS.h>

#define LED_PIN    D4      // Pin connected to the Data input of the WS2811 strip
#define NUM_LEDS   250     // Total number of LEDs in your strip
#define LED_TYPE   WS2811  // Type of LED strip
#define COLOR_ORDER RGB    // Color order
#define MAX_BRIGHTNESS 60      // LED brightness
#define NUM_CAL_STEPS 5      // Number of calibration steps
#define NUM_FRAMES 6       // Number of frames in the calibration pattern
#define FRAME_DELAY 300    // Delay between frames in milliseconds
#define MAX_GIF_FRAMES 100  // Maximum number of frames for GIF animations

struct Coord { int x; int y; };

CRGB patternTable [NUM_LEDS][NUM_FRAMES] = {};

CRGB leds[NUM_LEDS];      // Array to store LED color values

Coord ledCoords[NUM_LEDS]; // Array to store LED coordinates

// GIF animation storage (using SPIFFS instead of RAM)
CRGB gifFrameBuffer[NUM_LEDS];  // Single frame buffer (only 600 bytes in RAM!)
int gifNumFrames = 0;       // Actual number of frames in current GIF
int gifCurrentFrame = 0;    // Current frame index
unsigned long gifLastUpdate = 0;
int gifFrameDelay = 50;     // Delay between GIF frames in ms
bool gifMode = false;
bool gifPlaying = false;    // Whether a GIF is currently playing
File gifFile;               // File handle for reading frames from flash

const char* ssid = "NOS-676B"; // Your WiFi SSID
const char* password = "L4N9U7JC"; // Your WiFi password

IPAddress local_IP(192, 168, 1, 200);   // desired static IP
IPAddress gateway(192, 168, 1, 1);
IPAddress subnet(255, 255, 255, 0);

AsyncWebServer server(80);

bool calibration_mode = false;

CRGB getColorFromChar(char c);
void playCalibrationSequence();
bool connectToWiFi(unsigned long timeoutMs = 15000);
void UpAndDownEffect();
void RainbowEffect();
void playGIFAnimation();

void setup() {
  Serial.begin(115200);
  delay(500);
  
  // Initialize LittleFS for GIF storage
  if (!LittleFS.begin()) {
    Serial.println("LittleFS mount failed!");
  } else {
    Serial.println("LittleFS mounted successfully");
    FSInfo fs_info;
    LittleFS.info(fs_info);
    Serial.printf("Total: %d bytes, Used: %d bytes\n", fs_info.totalBytes, fs_info.usedBytes);
  }

  FastLED.addLeds<LED_TYPE, LED_PIN, COLOR_ORDER>(leds, NUM_LEDS);
  FastLED.setBrightness(MAX_BRIGHTNESS);

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

  // GIF upload endpoint - saves frame data to SPIFFS
  server.on("/gif", HTTP_POST, 
    [](AsyncWebServerRequest *request){
      request->send(200);
    },
    NULL,
    [](AsyncWebServerRequest *request, uint8_t *data, size_t len, size_t index, size_t total){
      static File uploadFile;
      
      // First chunk - parse header and create file
      if (index == 0) {
        // First 2 bytes = number of frames (little endian)
        if (len < 2) {
          request->send(400, "text/plain", "Invalid data");
          return;
        }
        
        gifNumFrames = data[0] | (data[1] << 8);
        
        if (gifNumFrames < 1) {
          Serial.printf("Invalid frame count: %d\n", gifNumFrames);
          request->send(400, "text/plain", "Invalid frame count");
          return;
        }
        
        // Remove MAX_GIF_FRAMES limit - SPIFFS can handle any size!
        size_t totalSize = gifNumFrames * NUM_LEDS * sizeof(CRGB);
        Serial.printf("Receiving GIF: %d frames (%d bytes total)\n", gifNumFrames, totalSize);
        
        // Create/overwrite file in SPIFFS
        uploadFile = LittleFS.open("/gif.dat", "w");
        if (!uploadFile) {
          Serial.println("Failed to create GIF file!");
          request->send(500, "text/plain", "Storage error");
          return;
        }
        
        // Write frame data (skip first 2 bytes header)
        size_t dataToCopy = len - 2;
        uploadFile.write(data + 2, dataToCopy);
      } else {
        // Subsequent chunks - append data to file
        if (uploadFile) {
          uploadFile.write(data, len);
        }
      }
      
      // Last chunk - finalize
      if (index + len >= total) {
        if (uploadFile) {
          uploadFile.close();
          Serial.printf("GIF saved to SPIFFS: %d frames, %d LEDs per frame\n", gifNumFrames, NUM_LEDS);
        }
        gifCurrentFrame = 0;
        gifPlaying = true;
        gifMode = true;
        request->send(200, "text/plain", "GIF uploaded to flash storage");
      }
    }
  );

  // GIF control endpoint
  server.on("/gif/control", HTTP_GET, [](AsyncWebServerRequest *request){
    if (request->hasParam("action")) {
      String action = request->getParam("action")->value();
      
      if (action == "play") {
        gifPlaying = true;
        gifMode = true;
        request->send(200, "text/plain", "Playing");
      } else if (action == "pause") {
        gifPlaying = false;
        gifMode = true;
        request->send(200, "text/plain", "Paused");
      } else if (action == "stop") {
        gifPlaying = false;
        gifCurrentFrame = 0;
        gifMode = false;
        request->send(200, "text/plain", "Stopped");
      } else if (action == "speed" && request->hasParam("value")) {
        gifFrameDelay = request->getParam("value")->value().toInt();
        request->send(200, "text/plain", "Speed updated");
      } else {
        request->send(400, "text/plain", "Invalid action");
      }
    } else {
      request->send(400, "text/plain", "Missing action");
    }
  });

  server.begin();

  delay(1000); // Wait a moment before starting

  for(int i = 0; i < NUM_LEDS; i++) {
    leds[i] = CRGB::Red; // Initialize all LEDs to off
  }
  FastLED.show();

  // Check if a GIF file exists in SPIFFS And Play it
  File f = LittleFS.open("/gif.dat", "r");
  if(f && f.size() > 0){
    // GIF in File exists
    size_t fileSize = f.size();
    gifNumFrames = fileSize / (NUM_LEDS * sizeof(CRGB));
    gifCurrentFrame = 0;
    gifMode = true;
    gifPlaying = true;
    Serial.printf("Found existing GIF in flash: %d bytes, %d frames\n", fileSize, gifNumFrames);
    f.close();
  } else {
    if(f) f.close();
  }

  Serial.println("Setup complete (:");
  delay(1000); // Wait a moment before starting
}

void loop() {
  if (calibration_mode) {
    // Keep the webserver and WiFi 
    delay(1000);
    playCalibrationSequence();
    calibration_mode = false;
    // If WiFi was lost for any reason, try to reconnect with a timeout.
    if (WiFi.status() != WL_CONNECTED) {
      bool ok = connectToWiFi(10000);
      if (!ok) {
        Serial.println("Warning: WiFi reconnect failed after calibration");
      }
    }
  }
  else if (gifMode && gifNumFrames > 0) {
    playGIFAnimation();
  }
  else {
    // Default effects
    if(ledCoords[0].x == 0 && ledCoords[0].y == 0)
      RainbowEffect();
    else
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

void playGIFAnimation() {
  if (!gifPlaying) {
    delay(1);  // Small delay to prevent WiFi issues
    return;
  }
  // Play GIF animation from SPIFFS (stream one frame at a time)
  unsigned long now = millis();
  if (now - gifLastUpdate >= gifFrameDelay) {
    // Open file and seek to current frame
    File f = LittleFS.open("/gif.dat", "r");
    if (f) {
      // Seek to frame position
      size_t frameOffset = gifCurrentFrame * NUM_LEDS * sizeof(CRGB);
      f.seek(frameOffset, SeekSet);
      
      // Read one frame into buffer
      f.read((uint8_t*)gifFrameBuffer, NUM_LEDS * sizeof(CRGB));
      f.close();
      
      // Display frame from buffer
      for (int i = 0; i < NUM_LEDS; i++) {
        leds[i] = gifFrameBuffer[i];
      }
      FastLED.show();
    }
    
    // Move to next frame
    gifCurrentFrame++;
    if (gifCurrentFrame >= gifNumFrames) {
      gifCurrentFrame = 0;  // Loop back to start
    }
    
    gifLastUpdate = now;
  }
  delay(1);  // Small delay to prevent WiFi issues
}

void RainbowEffect() {
  static uint8_t hue = 0;

  for (int i = 0; i < NUM_LEDS; i++) {
    leds[i] = CHSV(hue + (i * 256 / NUM_LEDS), 255, 255);
  }

  FastLED.show();

  hue++;

  delay(20);
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
      // linear falloff from MAX_BRIGHTNESS to 0
      brightness = (uint8_t)(MAX_BRIGHTNESS - ((uint16_t)dist * MAX_BRIGHTNESS) / bandRadius);
    } else {
      brightness = 0;
    }

    // Set base color to white and scale by brightness so color is consistent across hardware
    leds[i] = CRGB::White;
    // nscale8_video dims the color while preserving relative channels
    leds[i].nscale8_video(brightness);
  }

  FastLED.show();
  // Small delay for visible motion; use FastLED.delay to yield for WiFi
  FastLED.delay(30);
}

void playCalibrationSequence() {
    // Start sync sequence: Red -> Green -> Blue (unique pattern)
    FastLED.setBrightness(MAX_BRIGHTNESS);
  FastLED.delay(500);
    
    // Red flash
    fill_solid(leds, NUM_LEDS, CRGB::Red);
    FastLED.show();
    FastLED.delay(400);
    FastLED.clear();
    FastLED.show();
    FastLED.delay(200);
    
    // Green flash
    fill_solid(leds, NUM_LEDS, CRGB::Green);
    FastLED.show();
    FastLED.delay(400);
    FastLED.clear();
    FastLED.show();
    FastLED.delay(200);
    
    // Blue flash
    fill_solid(leds, NUM_LEDS, CRGB::Blue);
    FastLED.show();
    FastLED.delay(400);
    FastLED.clear();
    FastLED.show();
    
    // Longer delay to let camera auto-focus and exposure stabilize
    FastLED.delay(2000);  // 2 seconds for camera to adjust

    // Play pattern frames
  FastLED.setBrightness(1);
  for(int step = 0; step < NUM_CAL_STEPS; step++) {
    for (int f = 0; f < NUM_FRAMES; f++) {
        for (int i = 0; i < NUM_LEDS; i++) {
            leds[i] = patternTable[i][f];
        }
        FastLED.show();
    FastLED.delay(FRAME_DELAY);
    }
  }

    // End sync sequence: Blue -> Green -> Red (reverse pattern)
    FastLED.setBrightness(MAX_BRIGHTNESS);
    
    // Blue flash
    fill_solid(leds, NUM_LEDS, CRGB::Blue);
    FastLED.show();
    FastLED.delay(400);
    FastLED.clear();
    FastLED.show();
    FastLED.delay(200);
    
    // Green flash
    fill_solid(leds, NUM_LEDS, CRGB::Green);
    FastLED.show();
    FastLED.delay(400);
    FastLED.clear();
    FastLED.show();
    FastLED.delay(200);
    
    // Red flash
    fill_solid(leds, NUM_LEDS, CRGB::Red);
    FastLED.show();
    FastLED.delay(400);
    FastLED.clear();
}

bool connectToWiFi(unsigned long timeoutMs) {
  WiFi.config(local_IP, gateway, subnet);
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && (millis() - start) < timeoutMs) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("Connected! IP address: ");
    Serial.println(WiFi.localIP());
    return true;
  } else {
    Serial.println("WiFi connect timed out");
    return false;
  }
}