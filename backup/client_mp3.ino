#include <WiFi.h>
#include <WiFiManager.h>
#include <HTTPClient.h>
#include "Base64.h"
#include <math.h>
#include <AudioGeneratorMP3.h>
#include <AudioOutputI2S.h>
#include <AudioFileSourceHTTPStreamPost.h>

// Server URL
const char* serverName = "http://192.168.1.39:8002";

// Define pins
#define BUTTON_PIN 6
#define I2S_BCK_IO 14
#define I2S_WS_IO 12
#define I2S_DO_IO 13
#define MIC_ADC_PIN 4
#define SAMPLE_RATE 32000
#define MAX_RECORD_DURATION 5  // Maximum recording duration in seconds

void IRAM_ATTR buttonPressedISR();
void IRAM_ATTR buttonReleasedISR();

AudioGeneratorMP3 *mp3 = nullptr;
AudioFileSourceHTTPStreamPost *file = nullptr;
AudioOutputI2S *out = nullptr;

// Variables
volatile bool buttonPressed = false;
unsigned long pressTime = 0;
unsigned long releaseTime = 0;

const int recordBufferSize = SAMPLE_RATE * MAX_RECORD_DURATION; // Buffer for max record duration
int16_t* recordAudioBuffer = nullptr;
size_t recordAudioBufferIndex = 0;
bool recording = false;

void setup() {
  Serial.begin(115200);

  if (!psramFound()) {
    Serial.println("No PSRAM found. Please enable PSRAM.");
    while (true);  // Stop execution if no PSRAM is found
  }

  initButtonModule();
  setupWiFi();
  initAudioModule();
}

void setupWiFi() {
  WiFiManager wifiManager;
  wifiManager.setConfigPortalTimeout(180); // Set timeout for the configuration portal

  Serial.println("Starting WiFiManager...");
  if (!wifiManager.autoConnect("AutoConnectAP", "password")) {
    Serial.println("Failed to connect and hit timeout");
    delay(3000);
    ESP.restart();
    delay(5000);
  }

  Serial.println("Connected to WiFi!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
}

void initAudioModule() {
  // Configure ADC
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);
  
  // Allocate memory for audio buffer in PSRAM
  if (!recordAudioBuffer) {
    recordAudioBuffer = (int16_t*)ps_malloc(recordBufferSize * sizeof(int16_t));
    if (recordAudioBuffer == NULL) {
      Serial.println("Failed to allocate memory for audio buffer");
      while (1);
    }
  }

  // Initialize I2S and audio components
  if (!out) {
    out = new AudioOutputI2S();
    out->SetPinout(I2S_BCK_IO, I2S_WS_IO, I2S_DO_IO);
    out->SetOutputModeMono(true);
    out->SetGain(1.0);
    out->SetRate(SAMPLE_RATE); 
  }

  if (!mp3) {
    mp3 = new AudioGeneratorMP3();
  }
}

void initButtonModule() {
  // Initialize button pin
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(BUTTON_PIN), buttonPressedISR, FALLING);
}

void recordAudio() {
  if (recordAudioBufferIndex < recordBufferSize) {
    int adc_reading = analogRead(MIC_ADC_PIN);
    recordAudioBuffer[recordAudioBufferIndex++] = (adc_reading - 2048) << 4;  // Adjust ADC resolution to I2S resolution, center around 0
  } else {
    Serial.println("Audio buffer overflow");
    recording = false;
  }
}

void IRAM_ATTR buttonPressedISR() {
  if (digitalRead(BUTTON_PIN) == LOW) {
    pressTime = millis();
    buttonPressed = true;
    recording = true;
    recordAudioBufferIndex = 0;  // Reset buffer index for new recording
    memset(recordAudioBuffer, 0, recordBufferSize * sizeof(int16_t));
    detachInterrupt(digitalPinToInterrupt(BUTTON_PIN));
    attachInterrupt(digitalPinToInterrupt(BUTTON_PIN), buttonReleasedISR, RISING);
  }
}

void IRAM_ATTR buttonReleasedISR() {
  if (digitalRead(BUTTON_PIN) == HIGH) {
    releaseTime = millis();
    recording = false;
    detachInterrupt(digitalPinToInterrupt(BUTTON_PIN));
    attachInterrupt(digitalPinToInterrupt(BUTTON_PIN), buttonPressedISR, FALLING);
  }
}

void sendAudioAndPlay(const char* audioData, size_t audioDataLen) {
  // Prepare custom headers
  std::vector<String> headers = {
    "Content-Type: application/json",
    "Authorization: Bearer YOUR_ACCESS_TOKEN"
  };

  // Construct JSON payload
  const char* jsonPrefix = "{\"audio_data\": \"";
  const char* jsonSuffix = "\"}";
  size_t jsonDataLen = strlen(jsonPrefix) + audioDataLen + strlen(jsonSuffix) + 1;

  // Allocate buffer for the full JSON data
  char* jsonData = (char*)ps_malloc(jsonDataLen);
  if (jsonData == NULL) {
    Serial.println("Failed to allocate memory for JSON data");
    return;
  }
  snprintf(jsonData, jsonDataLen, "%s%s%s", jsonPrefix, audioData, jsonSuffix);

  // Open the audio stream with custom headers
  file = new AudioFileSourceHTTPStreamPost(serverName, jsonData, 10000, headers);
  mp3->begin(file, out);

  while (mp3->isRunning()) {
    if (!mp3->loop()) {
      mp3->stop();
      Serial.println("MP3 playback stopped");
    }
  }
  Serial.println("MP3 playback finished");

  // Clean up
  delete file;
  free(jsonData);
  file = nullptr;
}

void loop() {
  if (recording) {
    recordAudio();
  } else if (!recording && buttonPressed) {
    // Button has been released; process the recording
    Serial.println("Button released, sending audio...");

    // Calculate the length of actual recorded audio
    size_t actualBufferSize = recordAudioBufferIndex * sizeof(int16_t);

    // Encode Base64 for request preparation
    size_t base64_len = Base64.encodedLength(actualBufferSize);
    char* base64_data = (char*)ps_malloc(base64_len + 1);  // +1 for null-terminator

    if (base64_data == NULL) {
      Serial.println("Failed to allocate memory for base64 encoding");
      return;
    }

    Base64.encode(base64_data, (char*)recordAudioBuffer, actualBufferSize);
    base64_data[base64_len] = '\0';  // Null-terminate the string

    sendAudioAndPlay(base64_data, base64_len);

    // Free the allocated memory
    free(base64_data);

    // Reset the flag
    buttonPressed = false;
  }
}
