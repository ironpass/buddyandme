#include <WiFiManager.h>
#include "Base64.h"
#include <math.h>
#include <AudioGeneratorMP3.h>
#include <AudioOutputI2S.h>
#include <AudioFileSourceHTTPStreamPost.h>
#include <WiFiClientSecure.h>
// #include <WiFiClient.h>

WiFiClientSecure client;

// Server URL
const char* serverName = "https://or1nhpgnhk.execute-api.ap-southeast-1.amazonaws.com/dev";
// const char* serverName = "http://192.168.1.34:8002";
const char* root_ca = \
"-----BEGIN CERTIFICATE-----\n" \
"MIIDQTCCAimgAwIBAgITBmyfz5m/jAo54vB4ikPmljZbyjANBgkqhkiG9w0BAQsF\n" \
"ADA5MQswCQYDVQQGEwJVUzEPMA0GA1UEChMGQW1hem9uMRkwFwYDVQQDExBBbWF6\n" \
"b24gUm9vdCBDQSAxMB4XDTE1MDUyNjAwMDAwMFoXDTM4MDExNzAwMDAwMFowOTEL\n" \
"MAkGA1UEBhMCVVMxDzANBgNVBAoTBkFtYXpvbjEZMBcGA1UEAxMQQW1hem9uIFJv\n" \
"b3QgQ0EgMTCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBALJ4gHHKeNXj\n" \
"ca9HgFB0fW7Y14h29Jlo91ghYPl0hAEvrAIthtOgQ3pOsqTQNroBvo3bSMgHFzZM\n" \
"9O6II8c+6zf1tRn4SWiw3te5djgdYZ6k/oI2peVKVuRF4fn9tBb6dNqcmzU5L/qw\n" \
"IFAGbHrQgLKm+a/sRxmPUDgH3KKHOVj4utWp+UhnMJbulHheb4mjUcAwhmahRWa6\n" \
"VOujw5H5SNz/0egwLX0tdHA114gk957EWW67c4cX8jJGKLhD+rcdqsq08p8kDi1L\n" \
"93FcXmn/6pUCyziKrlA4b9v7LWIbxcceVOF34GfID5yHI9Y/QCB/IIDEgEw+OyQm\n" \
"jgSubJrIqg0CAwEAAaNCMEAwDwYDVR0TAQH/BAUwAwEB/zAOBgNVHQ8BAf8EBAMC\n" \
"AYYwHQYDVR0OBBYEFIQYzIU07LwMlJQuCFmcx7IQTgoIMA0GCSqGSIb3DQEBCwUA\n" \
"A4IBAQCY8jdaQZChGsV2USggNiMOruYou6r4lK5IpDB/G/wkjUu0yKGX9rbxenDI\n" \
"U5PMCCjjmCXPI6T53iHTfIUJrU6adTrCC2qJeHZERxhlbI1Bjjt/msv0tadQ1wUs\n" \
"N+gDS63pYaACbvXy8MWy7Vu33PqUXHeeE6V/Uq2V8viTO96LXFvKWlJbYK8U90vv\n" \
"o/ufQJVtMVT8QtPHRh8jrdkPSHCa2XV4cdFyQzR1bldZwgJcJmApzyMZFo6IQ6XU\n" \
"5MsI+yMRQ+hDKXJioaldXgjUkK642M4UwtBV8ob2xJNDd2ZhwLnoQdeXeGADbkpy\n" \
"rqXRfboQnoZsG4q5WTP468SQvvG5\n" \
"-----END CERTIFICATE-----\n";

// Define pins
#define BUTTON_PIN 6
#define I2S_BCK_IO 14
#define I2S_WS_IO 12
#define I2S_DO_IO 13
#define MIC_ADC_PIN 4
// #define SAMPLE_RATE 32000
#define SAMPLE_RATE 44100
#define MAX_RECORD_DURATION 5  // Maximum recording duration in seconds

// Function prototypes
void IRAM_ATTR buttonPressedISR();
void IRAM_ATTR buttonReleasedISR();
void recordAudio();
void sendAudioAndPlay();

// State definitions
enum State {
  STATE_IDLE,
  STATE_RECORDING,
  STATE_PROCESSING
};

volatile State currentState = STATE_IDLE; // Initialize the state to idle

AudioGeneratorMP3 *mp3 = nullptr;
AudioFileSourceHTTPStreamPost *file = nullptr;
AudioOutputI2S *out = nullptr;

const int recordBufferSize = SAMPLE_RATE * MAX_RECORD_DURATION; // Buffer for max record duration
int16_t* recordAudioBuffer = nullptr;
size_t recordAudioBufferIndex = 0;


void setup() {
  Serial.begin(115200);

  if (!psramFound()) {
    Serial.println("No PSRAM found. Please enable PSRAM.");
    while (true);  // Stop execution if no PSRAM is found
  }

  initButtonModule();
  setupWiFi();
  initAudioModule();

  // Set the root CA for SSL
  client.setCACert(root_ca);
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
    out->SetChannels(1); 
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

void IRAM_ATTR buttonPressedISR() {
  if (currentState == STATE_IDLE && digitalRead(BUTTON_PIN) == LOW) {
    // Start recording immediately on button press
    currentState = STATE_RECORDING;
    recordAudioBufferIndex = 0;  // Reset buffer index for new recording
    memset(recordAudioBuffer, 0, recordBufferSize * sizeof(int16_t));
    detachInterrupt(digitalPinToInterrupt(BUTTON_PIN));
    attachInterrupt(digitalPinToInterrupt(BUTTON_PIN), buttonReleasedISR, RISING);
  }
}

void IRAM_ATTR buttonReleasedISR() {
  if (currentState == STATE_RECORDING && digitalRead(BUTTON_PIN) == HIGH) {
    // Stop recording on button release
    currentState = STATE_PROCESSING; // Move to processing state
    detachInterrupt(digitalPinToInterrupt(BUTTON_PIN));
    attachInterrupt(digitalPinToInterrupt(BUTTON_PIN), buttonPressedISR, FALLING);
  }
}

void loop() {
  switch (currentState) {
    case STATE_IDLE:
      // Do nothing, wait for button press
      break;

    case STATE_RECORDING:
      recordAudio();
      break;

    case STATE_PROCESSING:
      // Processing state - Sending and playing audio
      Serial.println("Processing audio...");
      sendAudioAndPlay();

      // Reset the state
      currentState = STATE_IDLE;
      break;
  }
}

void recordAudio() {
  if (recordAudioBufferIndex < recordBufferSize) {
    int adc_reading = analogRead(MIC_ADC_PIN);
    recordAudioBuffer[recordAudioBufferIndex++] = (adc_reading - 2048) << 4;  // Adjust ADC resolution to I2S resolution, center around 0
  } else {
    Serial.println("Recording complete, buffer full.");
    currentState = STATE_PROCESSING;
    detachInterrupt(digitalPinToInterrupt(BUTTON_PIN));
    attachInterrupt(digitalPinToInterrupt(BUTTON_PIN), buttonPressedISR, FALLING);
  }
}

void sendAudioAndPlay() {
  // Get the board's unique ID
  String userId = String(ESP.getEfuseMac()); // Using the MAC address as a unique ID

  // Calculate the length of actual recorded audio
  size_t actualBufferSize = recordAudioBufferIndex * sizeof(int16_t);

  // Calculate the Base64-encoded size
  size_t base64_len = Base64.encodedLength(actualBufferSize);
  char* base64_data = (char*)ps_malloc(base64_len + 1);  // +1 for null-terminator

  if (base64_data == NULL) {
    Serial.println("Failed to allocate memory for base64 encoding");
    currentState = STATE_IDLE;
    return;
  }

  // Encode the audio data to Base64
  Base64.encode(base64_data, (char*)recordAudioBuffer, actualBufferSize);
  base64_data[base64_len] = '\0';  // Null-terminate the string

  // Construct the JSON payload
  const char* jsonPrefix = "{\"audio_data\": \"";
  const char* userIdField = "\", \"user_id\": \"";
  const char* jsonSuffix = "\"}";
  size_t jsonDataLen = strlen(jsonPrefix) + base64_len + strlen(userIdField) + userId.length() + strlen(jsonSuffix) + 1;
  
  // Allocate a buffer for JSON data
  char* jsonData = (char*)ps_malloc(jsonDataLen);

  if (jsonData == NULL) {
    Serial.println("Failed to allocate memory for JSON payload");
    free(base64_data); // Free previously allocated memory
    currentState = STATE_IDLE;
    return;
  }

  // Create the JSON string
  snprintf(jsonData, jsonDataLen, "%s%s%s%s%s", jsonPrefix, base64_data, userIdField, userId.c_str(), jsonSuffix);

  // Prepare custom headers
  std::vector<String> headers = {
    "Content-Type: application/json",
    "Accept: audio/mpeg", // Add Accept header for audio/mpeg
    "Authorization: Bearer YOUR_ACCESS_TOKEN"
  };

  // Open the audio stream with custom headers
  file = new AudioFileSourceHTTPStreamPost(serverName, jsonData, 100000, headers, &client);
  mp3->begin(file, out);

  while (mp3->isRunning()) {
    bool looping = mp3->loop();
    if (!looping) {
      out->flush();
      mp3->stop();
      Serial.println("MP3 playback stopped");
    }
  }
  Serial.println("MP3 playback finished");

  // Clean up
  delete file;
  file = nullptr;

  free(base64_data);
  base64_data = nullptr;
  free(jsonData);
  jsonData = nullptr;
}