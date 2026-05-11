#include "modbus_rtu.h"
#include "rs485_uart.h"
#include "crc16.h"

#include <string.h>

#include "FreeRTOS.h"
#include "task.h"

#define RX_TIMEOUT_MS  500

uint16_t modbus_crc16(const uint8_t *data, size_t len)
{
    return crc16_modbus(data, len);
}

size_t modbus_build_read_holding(uint8_t *out, uint8_t slave_id,
                                 uint16_t start, uint16_t count)
{
    out[0] = slave_id;
    out[1] = MB_FN_READ_HOLDING_REGISTERS;
    out[2] = start >> 8;
    out[3] = start & 0xFF;
    out[4] = count >> 8;
    out[5] = count & 0xFF;
    uint16_t crc = modbus_crc16(out, 6);
    out[6] = crc & 0xFF;
    out[7] = crc >> 8;
    return 8;
}

modbus_status_t modbus_parse_response(const uint8_t *buf, size_t len,
                                      modbus_response_t *resp)
{
    if (len < 5) return MB_ERR_FRAME;

    uint16_t crc_recv = (uint16_t)buf[len - 1] << 8 | buf[len - 2];
    uint16_t crc_calc = modbus_crc16(buf, len - 2);
    if (crc_recv != crc_calc) return MB_ERR_CRC;

    resp->slave_id = buf[0];
    resp->function = buf[1];
    resp->exception = 0;
    resp->timestamp_ms = (uint32_t)xTaskGetTickCount() * portTICK_PERIOD_MS;

    if (resp->function & 0x80) {
        resp->exception = buf[2];
        resp->register_count = 0;
        return MB_ERR_EXCEPTION;
    }

    if (resp->function == MB_FN_READ_HOLDING_REGISTERS ||
        resp->function == MB_FN_READ_INPUT_REGISTERS) {
        uint8_t byte_count = buf[2];
        if (byte_count & 1) return MB_ERR_FRAME;
        resp->register_count = byte_count / 2;
        if (resp->register_count > 125) return MB_ERR_SHORT_BUFFER;
        for (uint16_t i = 0; i < resp->register_count; i++) {
            resp->registers[i] = ((uint16_t)buf[3 + i * 2] << 8) | buf[4 + i * 2];
        }
    } else {
        resp->register_count = 0;
    }
    return MB_OK;
}

modbus_status_t modbus_poll(const modbus_poll_entry_t *entry, modbus_response_t *resp)
{
    uint8_t  request[8];
    uint8_t  reply[MODBUS_RTU_MAX_ADU];
    size_t   req_len = modbus_build_read_holding(request, entry->slave_id,
                                                 entry->start_register,
                                                 entry->register_count);

    rs485_uart_set_direction(RS485_TX);
    rs485_uart_write(request, req_len);
    rs485_uart_wait_tx_complete();
    rs485_uart_set_direction(RS485_RX);

    int n = rs485_uart_read_frame(reply, sizeof(reply), RX_TIMEOUT_MS);
    if (n < 0) return MB_ERR_TIMEOUT;

    modbus_status_t st = modbus_parse_response(reply, (size_t)n, resp);
    if (st == MB_OK && resp->slave_id != entry->slave_id) {
        return MB_ERR_ADDR_MISMATCH;
    }
    return st;
}

void modbus_rtu_init(void)
{
    // RS-485 layer is initialized externally; this is reserved for future
    // statistics counters (CRC errors, timeouts, retries).
}
