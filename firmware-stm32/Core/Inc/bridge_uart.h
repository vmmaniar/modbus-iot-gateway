#pragma once

#include <stdint.h>
#include <stddef.h>
#include "modbus_rtu.h"

void bridge_uart_init(uint32_t baud);

// Frame a Modbus response into CBOR and ship it to the ESP32 over USART2.
void bridge_uart_publish(const modbus_poll_entry_t *entry,
                         const modbus_response_t *resp);
