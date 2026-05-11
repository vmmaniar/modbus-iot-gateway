#pragma once
#include "esp_err.h"

typedef void (*bridge_payload_cb_t)(const uint8_t *cbor, size_t len);

// Configure UART pins and start the parser task that decodes frames from the STM32.
esp_err_t bridge_rx_start(int uart_num, int rx_gpio, int tx_gpio, int baud,
                          bridge_payload_cb_t on_payload);
