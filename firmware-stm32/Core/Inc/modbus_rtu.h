#pragma once

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#define MODBUS_RTU_MAX_PDU      253
#define MODBUS_RTU_MAX_ADU      256   // 1 (addr) + 253 (PDU) + 2 (CRC)
#define MODBUS_BROADCAST        0x00

typedef enum {
    MB_FN_READ_COILS              = 0x01,
    MB_FN_READ_DISCRETE_INPUTS    = 0x02,
    MB_FN_READ_HOLDING_REGISTERS  = 0x03,
    MB_FN_READ_INPUT_REGISTERS    = 0x04,
    MB_FN_WRITE_SINGLE_COIL       = 0x05,
    MB_FN_WRITE_SINGLE_REGISTER   = 0x06,
    MB_FN_WRITE_MULTIPLE_COILS    = 0x0F,
    MB_FN_WRITE_MULTIPLE_REGS     = 0x10,
} modbus_function_t;

typedef enum {
    MB_OK                 = 0,
    MB_ERR_TIMEOUT        = -1,
    MB_ERR_CRC            = -2,
    MB_ERR_FRAME          = -3,
    MB_ERR_EXCEPTION      = -4,
    MB_ERR_ADDR_MISMATCH  = -5,
    MB_ERR_SHORT_BUFFER   = -6,
} modbus_status_t;

typedef struct {
    uint8_t  slave_id;
    uint16_t start_register;
    uint16_t register_count;
    uint16_t poll_interval_ms;
    const char *label;          // e.g. "tank_pressure"
} modbus_poll_entry_t;

typedef struct {
    uint8_t  slave_id;
    uint8_t  function;
    uint8_t  exception;         // 0 if OK
    uint16_t register_count;
    uint16_t registers[125];    // max per RTU spec
    uint32_t timestamp_ms;
} modbus_response_t;

// Compute the standard Modbus CRC-16 (polynomial 0xA001, init 0xFFFF, LSB first).
uint16_t modbus_crc16(const uint8_t *data, size_t len);

// Build a "read holding registers" PDU. Returns the ADU length including CRC.
size_t modbus_build_read_holding(uint8_t *out, uint8_t slave_id,
                                 uint16_t start, uint16_t count);

// Parse a slave response. Returns MB_OK on success and fills `resp`.
modbus_status_t modbus_parse_response(const uint8_t *buf, size_t len,
                                      modbus_response_t *resp);

// One blocking poll cycle (write request, wait for response).
// Returns MB_OK if a valid response arrived; otherwise sets resp->exception or returns an error code.
modbus_status_t modbus_poll(const modbus_poll_entry_t *entry, modbus_response_t *resp);

// Initialize the RTU layer (must be called after rs485_uart_init).
void modbus_rtu_init(void);
