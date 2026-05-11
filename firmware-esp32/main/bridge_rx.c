#include "bridge_rx.h"

#include "driver/uart.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"

static const char *TAG = "bridge-rx";

typedef struct {
    int uart;
    bridge_payload_cb_t cb;
} bridge_state_t;

#define MAX_PAYLOAD 512

static void bridge_task(void *arg)
{
    bridge_state_t *st = arg;
    enum { S_IDLE, S_LEN_LO, S_LEN_HI, S_PAYLOAD, S_XOR, S_END } state = S_IDLE;
    uint8_t payload[MAX_PAYLOAD];
    uint16_t expected_len = 0, recv = 0;
    uint8_t xor_sum = 0;

    while (1) {
        uint8_t b;
        int n = uart_read_bytes(st->uart, &b, 1, pdMS_TO_TICKS(100));
        if (n <= 0) continue;

        switch (state) {
            case S_IDLE:
                if (b == 0x7E) { state = S_LEN_LO; xor_sum = 0; recv = 0; }
                break;
            case S_LEN_LO: expected_len = b;            state = S_LEN_HI; break;
            case S_LEN_HI: expected_len |= ((uint16_t)b << 8);
                           if (expected_len > MAX_PAYLOAD) { state = S_IDLE; break; }
                           state = expected_len ? S_PAYLOAD : S_XOR; break;
            case S_PAYLOAD:
                payload[recv++] = b;
                xor_sum ^= b;
                if (recv >= expected_len) state = S_XOR;
                break;
            case S_XOR:
                if (b != xor_sum) {
                    ESP_LOGW(TAG, "XOR mismatch");
                    state = S_IDLE;
                } else {
                    state = S_END;
                }
                break;
            case S_END:
                if (b == 0x7F) {
                    st->cb(payload, expected_len);
                }
                state = S_IDLE;
                break;
        }
    }
}

esp_err_t bridge_rx_start(int uart_num, int rx_gpio, int tx_gpio, int baud,
                          bridge_payload_cb_t on_payload)
{
    uart_config_t cfg = {
        .baud_rate = baud,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
    };
    ESP_ERROR_CHECK(uart_driver_install(uart_num, 1024, 0, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_param_config(uart_num, &cfg));
    ESP_ERROR_CHECK(uart_set_pin(uart_num, tx_gpio, rx_gpio, -1, -1));

    bridge_state_t *st = malloc(sizeof(*st));
    st->uart = uart_num;
    st->cb = on_payload;
    xTaskCreate(bridge_task, "bridge-rx", 4096, st, 5, NULL);
    return ESP_OK;
}
