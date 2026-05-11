#pragma once

#include <stdint.h>
#include <stddef.h>

typedef enum {
    RS485_RX = 0,
    RS485_TX = 1,
} rs485_direction_t;

// Initialize the RS-485 UART (USART1 on PA9/PA10 + DE/RE on PA8).
// Default config: 9600 8-N-1. Adjust in rs485_uart.c if your slaves differ.
void rs485_uart_init(uint32_t baud);

void rs485_uart_set_direction(rs485_direction_t dir);

void rs485_uart_write(const uint8_t *data, size_t len);

void rs485_uart_wait_tx_complete(void);

// Read a Modbus RTU frame: returns when the inter-frame silence (>=3.5 char times)
// is exceeded or the buffer fills. Returns the number of bytes received or -1 on timeout.
int rs485_uart_read_frame(uint8_t *buf, size_t cap, uint32_t timeout_ms);
