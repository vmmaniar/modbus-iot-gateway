#pragma once
#include "esp_err.h"
esp_err_t wifi_sta_start_blocking(const char *ssid, const char *password);
