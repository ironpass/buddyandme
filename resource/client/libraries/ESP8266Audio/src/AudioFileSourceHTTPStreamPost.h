#ifndef _AUDIOFILESOURCEHTTPSTREAMPOST_H_
#define _AUDIOFILESOURCEHTTPSTREAMPOST_H_

#include <WiFiClient.h>
#include <vector>
#include <Arduino.h>
#include <HTTPClient.h>
#include "AudioFileSource.h"

class AudioFileSourceHTTPStreamPost : public AudioFileSource {
public:
  AudioFileSourceHTTPStreamPost();
  AudioFileSourceHTTPStreamPost(const char* url, const char* postData, int timeout, const std::vector<String>& headers, WiFiClient* client = nullptr);
  virtual ~AudioFileSourceHTTPStreamPost();
  virtual bool open(const char* url, const char* postData, int timeout, const std::vector<String>& headers);
  virtual uint32_t read(void* data, uint32_t len);
  virtual uint32_t readNonBlock(void* data, uint32_t len);
  virtual bool seek(int32_t pos, int dir);
  virtual bool close();
  virtual bool isOpen();
  virtual uint32_t getSize();
  virtual uint32_t getPos();
  enum { STATUS_HTTPFAIL=2, STATUS_DISCONNECTED, STATUS_RECONNECTING, STATUS_RECONNECTED, STATUS_NODATA };

protected:
  const char* postData;
  int timeout;
  HTTPClient http;
  char saveURL[256];
  uint32_t size;
  uint32_t pos;
  std::vector<String> headers;
  WiFiClient* client; // client for HTTPS

  uint32_t readInternal(void* data, uint32_t len, bool nonBlock);
  void applyHeaders();
};

#endif
