#pragma once
#include "esp_err.h"

// Start MQTT-TLS connection to AWS IoT Core. Device certs are read from NVS
// namespace "aws_certs", keys: "cert_pem", "private_key", "ca_root".
esp_err_t mqtt_aws_start(const char *endpoint_uri);

// Publish a binary payload to the configured topic.
esp_err_t mqtt_aws_publish_binary(const char *topic, const uint8_t *data, size_t len);
