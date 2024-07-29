#include <Arduino.h>
#include <WiFiManager.h>
#include <WiFiClient.h>
#include <HTTPClient.h>
#include <driver/i2s.h>
#include "Base64.h"
#include <math.h>

// Define pins
#define BUTTON_PIN 6
#define I2S_BCK_IO 14
#define I2S_WS_IO 12
#define I2S_DO_IO 13
#define MIC_ADC_PIN 4
#define SAMPLE_RATE 32000
#define MAX_RECORD_DURATION 5  // Maximum recording duration in seconds
#define BEEP_DURATION 200      // Duration of the beep in milliseconds

// Function prototypes
void initI2S();
void playBeep();
void recordAudio();
void playRecordedAudio();
void IRAM_ATTR buttonPressedISR();
void IRAM_ATTR buttonReleasedISR();
void setupWiFi();
void sendAudioData(const char* audioData, size_t audioDataLen);
void playAudioFromStream(WiFiClient* stream);
void clearAudioBuffer();

// const char* serverName = "https://or1nhpgnhk.execute-api.ap-southeast-1.amazonaws.com/dev";
const char* serverName = "http://192.168.1.39:8002";
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

// Variables
volatile bool buttonPressed = false;
unsigned long pressTime = 0;
unsigned long releaseTime = 0;

const int bufferSize = SAMPLE_RATE * MAX_RECORD_DURATION; // Buffer for max record duration
int16_t* audioBuffer;
size_t audioBufferIndex = 0;
bool recording = false;

void setup() {
  Serial.begin(115200);

  if (!psramFound()) {
    Serial.println("No PSRAM found. Please enable PSRAM.");
    while (true);  // Stop execution here if no PSRAM is found
  }

  // Initialize button pin
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(BUTTON_PIN), buttonPressedISR, FALLING);

  // Configure ADC
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);

  // Setup WiFi and I2S
  setupWiFi();
  initI2S();

  // Allocate memory for audio buffer in PSRAM
  audioBuffer = (int16_t*)ps_malloc(bufferSize * sizeof(int16_t));
  if (audioBuffer == NULL) {
    Serial.println("Failed to allocate memory for audio buffer");
    while (1);
  }
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

void loop() {
  if (buttonPressed) {
    if (digitalRead(BUTTON_PIN) == HIGH) {
      releaseTime = millis();
      unsigned long duration = releaseTime - pressTime;

      // Log the press duration
      Serial.print("Button held for ");
      Serial.print(duration);
      Serial.println(" milliseconds");
      recording = false;

      // Encode Base64 for request preparation
      size_t base64_len = Base64.encodedLength(bufferSize * sizeof(int16_t));
      char* base64_data = (char*)ps_malloc(base64_len + 1);  // +1 for null-terminator

      if (base64_data == NULL) {
        Serial.println("Failed to allocate memory for base64 encoding");
        return;
      }

      Base64.encode(base64_data, (char*)audioBuffer, bufferSize * sizeof(int16_t));
      base64_data[base64_len] = '\0';  // Null-terminate the string

      sendAudioData(base64_data, base64_len);

      // Free the allocated memory
      free(base64_data);

      // Reset the flag
      buttonPressed = false;
      attachInterrupt(digitalPinToInterrupt(BUTTON_PIN), buttonPressedISR, FALLING);
      playBeep();
    } else if (recording) {
      // Continue recording audio
      recordAudio();
    }
  }
}

void initI2S() {
  i2s_config_t i2s_config = {
    .mode = i2s_mode_t(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_RIGHT,
    .communication_format = I2S_COMM_FORMAT_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 64,
    .use_apll = false,
    .tx_desc_auto_clear = true,
    .fixed_mclk = 0
  };

  i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_BCK_IO,
    .ws_io_num = I2S_WS_IO,
    .data_out_num = I2S_DO_IO,
    .data_in_num = I2S_PIN_NO_CHANGE
  };

  i2s_driver_install(I2S_NUM_0, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pin_config);
  i2s_set_sample_rates(I2S_NUM_0, SAMPLE_RATE);  // Ensure sample rate is set
}

void playBeep() {
  const int frequency = 1000;  // Hz
  const int amplitude = 3000;  // 16-bit max value is 32767

  int samples = SAMPLE_RATE * BEEP_DURATION / 1000;
  size_t bytes_written = 0;

  for (int i = 0; i < samples; ++i) {
    int16_t sample = amplitude * sin((2 * PI * frequency * i) / SAMPLE_RATE);
    i2s_write_expand(I2S_NUM_0, &sample, sizeof(sample), 16, 16, &bytes_written, portMAX_DELAY);
  }
}

void recordAudio() {
  if (audioBufferIndex < bufferSize) {
    int adc_reading = analogRead(MIC_ADC_PIN);
    audioBuffer[audioBufferIndex++] = (adc_reading - 2048) << 4;  // Adjust ADC resolution to I2S resolution, center around 0
  } else {
    Serial.println("Audio buffer overflow");
    playBeep();
    recording = false;
  }
}

void clearAudioBuffer() {
  memset(audioBuffer, 0, bufferSize * sizeof(int16_t));
}

void playAudioFromStream(WiFiClient* stream) {
  Serial.println("Playing received audio...");
  size_t written;
  uint8_t buffer[4096];
  unsigned long playbackStartTime = millis();

  while (stream->connected() && stream->available()) {
    int bytesRead = stream->readBytes(buffer, sizeof(buffer));
    if (bytesRead > 0) {
      i2s_write(I2S_NUM_0, buffer, bytesRead, &written, portMAX_DELAY);
      if (written != bytesRead) {
        Serial.println("I2S write error: Not all bytes written");
      }
    } else {
      Serial.println("Error reading stream");
    }
  }

  unsigned long playbackEndTime = millis();
  Serial.print("Audio Playback Time: ");
  Serial.print(playbackEndTime - playbackStartTime);
  Serial.println(" ms");
  Serial.println("Finished playing audio");
}

void sendAudioData(const char* audioData, size_t audioDataLen) {
  unsigned long startTime = millis();
  
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    WiFiClient client;
    // client.setCACert(root_ca);

    http.setTimeout(10000); // Initial timeout to handle short responses

    if (http.begin(client, serverName)) {
      http.addHeader("Content-Type", "application/json");

      // Construct the JSON data incrementally
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

      // Send the JSON data as a string
      int httpResponseCode = http.POST(String(jsonData));

      unsigned long sendTime = millis();
      Serial.print("HTTP Request Time: ");
      Serial.print(sendTime - startTime);
      Serial.println(" ms");

      if (httpResponseCode > 0) {
        Serial.print("HTTP Response code: ");
        Serial.println(httpResponseCode);

        // Adjust the timeout based on the size of the response
        int contentLength = http.getSize();
        if (contentLength > 0) {
          unsigned long adjustedTimeout = contentLength / 1000; // Adjust based on response size
          http.setTimeout(adjustedTimeout);
          Serial.print("Adjusted Timeout: ");
          Serial.print(adjustedTimeout);
          Serial.println(" ms");
        }

        // Play the received audio from stream
        playAudioFromStream(&client);

      } else {
        Serial.print("Error on sending POST: ");
        Serial.println(httpResponseCode);
      }
      http.end();
      free(jsonData);

    } else {
      Serial.println("Failed to connect to server");
    }
  } else {
    Serial.println("WiFi Disconnected");
  }
}

void IRAM_ATTR buttonPressedISR() {
  if (digitalRead(BUTTON_PIN) == LOW) {
    pressTime = millis();
    buttonPressed = true;
    recording = true;
    audioBufferIndex = 0;  // Reset buffer index for new recording
    clearAudioBuffer();    // Clear the audio buffer
    detachInterrupt(digitalPinToInterrupt(BUTTON_PIN));
    attachInterrupt(digitalPinToInterrupt(BUTTON_PIN), buttonReleasedISR, RISING);
  }
}

void IRAM_ATTR buttonReleasedISR() {
  if (digitalRead(BUTTON_PIN) == HIGH) {
    releaseTime = millis();
    buttonPressed = true;
    detachInterrupt(digitalPinToInterrupt(BUTTON_PIN));
    attachInterrupt(digitalPinToInterrupt(BUTTON_PIN), buttonPressedISR, FALLING);
  }
}
