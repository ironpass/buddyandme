#include "AudioFileSourceHTTPStreamPost.h"

// Constructor for initializing the class without parameters
AudioFileSourceHTTPStreamPost::AudioFileSourceHTTPStreamPost()
    : postData(nullptr), timeout(5000), size(0), pos(0), client(nullptr), lastHttpCode(-1) {
  saveURL[0] = 0;
}

// Constructor for initializing the class with parameters
AudioFileSourceHTTPStreamPost::AudioFileSourceHTTPStreamPost(const char* url, const char* postData, int timeout, const std::vector<String>& headers, WiFiClient* client)
    : postData(postData), timeout(timeout), size(0), pos(0), headers(headers), client(client), lastHttpCode(-1) {
  saveURL[0] = 0;
  open(url, postData, timeout, headers);
}

// Open a connection with the specified URL, post data, timeout, and headers
bool AudioFileSourceHTTPStreamPost::open(const char* url, const char* postData, int timeout, const std::vector<String>& headers) {
  pos = 0;
  this->timeout = timeout;
  this->headers = headers;
  this->postData = postData; // Use the provided postData directly

  if (client) {
    http.begin(*client, url); // Use the secure client for HTTPS
  } else {
    http.begin(url); // Use the default client for HTTP
  }
  
  http.setTimeout(timeout);
  http.setReuse(true);

  // Apply custom headers
  applyHeaders();

#ifndef ESP32
  http.setFollowRedirects(HTTPC_FORCE_FOLLOW_REDIRECTS);
#endif

  lastHttpCode = http.POST((uint8_t*)this->postData, strlen(this->postData));
  if (lastHttpCode != HTTP_CODE_OK) {
    http.end();
    Serial.printf("ERROR: Can't open HTTP request, code: %d\n", lastHttpCode);
    return false;
  }

  // Adjust the timeout based on the size of the response
  int contentLength = http.getSize();
  if (contentLength > 0) {
    unsigned long adjustedTimeout = contentLength / 1000; // Adjust based on response size
    http.setTimeout(adjustedTimeout);
    Serial.print("Adjusted Timeout: ");
    Serial.print(adjustedTimeout);
    Serial.println(" ms");
  }

  size = http.getSize();
  strncpy(saveURL, url, sizeof(saveURL));
  saveURL[sizeof(saveURL) - 1] = 0;
  return true;
}

// Apply custom headers to the HTTP request
void AudioFileSourceHTTPStreamPost::applyHeaders() {
  for (const auto& header : headers) {
    int separatorIndex = header.indexOf(':');
    if (separatorIndex != -1) {
      String key = header.substring(0, separatorIndex);
      String value = header.substring(separatorIndex + 1);
      http.addHeader(key, value);
    }
  }
}

// Destructor to clean up resources
AudioFileSourceHTTPStreamPost::~AudioFileSourceHTTPStreamPost() {
  http.end();
}

// Read data from the HTTP stream
uint32_t AudioFileSourceHTTPStreamPost::read(void* data, uint32_t len) {
  if (data == NULL) {
    Serial.println("ERROR: AudioFileSourceHTTPStreamPost::read passed NULL data");
    return 0;
  }
  return readInternal(data, len, false);
}

// Read data from the HTTP stream in non-blocking mode
uint32_t AudioFileSourceHTTPStreamPost::readNonBlock(void* data, uint32_t len) {
  if (data == NULL) {
    Serial.println("ERROR: AudioFileSourceHTTPStreamPost::readNonBlock passed NULL data");
    return 0;
  }
  return readInternal(data, len, true);
}

// Internal function to read data from the HTTP stream
uint32_t AudioFileSourceHTTPStreamPost::readInternal(void* data, uint32_t len, bool nonBlock) {
retry:
  if (!http.connected()) {
    Serial.println("Stream disconnected, end retrying...");
    http.end();
    return 0;
  }

  if ((size > 0) && (pos >= size)) return 0;

  WiFiClient* stream = http.getStreamPtr();

  // Can't read past EOF...
  if ((size > 0) && (len > (uint32_t)(pos - size))) len = pos - size;

  if (!nonBlock) {
    int start = millis();
    while ((stream->available() < (int)len) && (millis() - start < 500)) yield();
  } else {
    // Implement a more patient wait for non-blocking mode
    int retries = 500; // Number of retries
    while ((retries > 0) && (stream->available() == 0)) {
      delay(1); // Small delay to wait for data
      retries--;
      yield(); // Allow network operations to proceed
    }
  }

  size_t avail = stream->available();
  if (!nonBlock && !avail) {
    Serial.println("No stream data available, retrying...");
    http.end();
    goto retry;
  }
  if (avail == 0) {
    Serial.println("Stream not available; end of streaming");
    http.end();
    return 0;
  }
  if (avail < len) len = avail;

  int read = stream->read(reinterpret_cast<uint8_t*>(data), len);
  pos += read;
  return read;
}

// Seek to a specific position in the stream (not implemented)
bool AudioFileSourceHTTPStreamPost::seek(int32_t pos, int dir) {
  Serial.println("ERROR: AudioFileSourceHTTPStreamPost::seek not implemented!");
  (void)pos;
  (void)dir;
  return false;
}

// Close the HTTP stream
bool AudioFileSourceHTTPStreamPost::close() {
  http.end();
  pos = 0; // Reset position
  size = 0; // Reset size
  return true;
}

// Check if the HTTP stream is open
bool AudioFileSourceHTTPStreamPost::isOpen() {
  return http.connected();
}

// Get the size of the HTTP stream
uint32_t AudioFileSourceHTTPStreamPost::getSize() {
  return size;
}

// Get the current position in the HTTP stream
uint32_t AudioFileSourceHTTPStreamPost::getPos() {
  return pos;
}

// Get the last HTTP status code
int AudioFileSourceHTTPStreamPost::getLastHttpCode() {
  return lastHttpCode;
}
