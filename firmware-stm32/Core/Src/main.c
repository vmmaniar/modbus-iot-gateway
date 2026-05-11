/*
 * Industrial Modbus-RTU → MQTT IoT Gateway — STM32F103 firmware
 *
 * Two FreeRTOS tasks:
 *   1. modbus_master_task: round-robin polls slaves listed in s_poll_table
 *   2. bridge_task:        drains a queue of completed readings and frames
 *                          them to the ESP32 over USART2
 */

#include "stm32f1xx.h"

#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"

#include "modbus_rtu.h"
#include "rs485_uart.h"
#include "bridge_uart.h"

typedef struct {
    const modbus_poll_entry_t *entry;
    modbus_response_t resp;
} polled_reading_t;

static QueueHandle_t s_bridge_q;

static const modbus_poll_entry_t s_poll_table[] = {
    { .slave_id = 0x01, .start_register = 0x0000, .register_count = 2,
      .poll_interval_ms = 500, .label = "tank_pressure" },
    { .slave_id = 0x01, .start_register = 0x0010, .register_count = 1,
      .poll_interval_ms = 1000, .label = "ambient_temp" },
    { .slave_id = 0x02, .start_register = 0x0020, .register_count = 4,
      .poll_interval_ms = 2000, .label = "flow_meter" },
};
#define POLL_TABLE_LEN (sizeof(s_poll_table) / sizeof(s_poll_table[0]))

static void modbus_master_task(void *arg)
{
    (void)arg;
    rs485_uart_init(9600);
    modbus_rtu_init();

    uint32_t next_poll_ms[POLL_TABLE_LEN] = {0};
    polled_reading_t pr;

    for (;;) {
        uint32_t now_ms = (uint32_t)(xTaskGetTickCount() * portTICK_PERIOD_MS);
        for (size_t i = 0; i < POLL_TABLE_LEN; i++) {
            if ((int32_t)(now_ms - next_poll_ms[i]) < 0) continue;
            pr.entry = &s_poll_table[i];
            modbus_status_t st = modbus_poll(pr.entry, &pr.resp);
            if (st == MB_OK) {
                xQueueSend(s_bridge_q, &pr, 0);
            }
            next_poll_ms[i] = now_ms + s_poll_table[i].poll_interval_ms;
        }
        vTaskDelay(pdMS_TO_TICKS(20));
    }
}

static void bridge_task(void *arg)
{
    (void)arg;
    bridge_uart_init(115200);
    polled_reading_t pr;
    for (;;) {
        if (xQueueReceive(s_bridge_q, &pr, portMAX_DELAY) == pdTRUE) {
            bridge_uart_publish(pr.entry, &pr.resp);
        }
    }
}

int main(void)
{
    SystemInit();
    // SystemCoreClockUpdate(); -- supplied by CMSIS startup

    s_bridge_q = xQueueCreate(16, sizeof(polled_reading_t));
    configASSERT(s_bridge_q);

    xTaskCreate(modbus_master_task, "modbus", 512, NULL, 4, NULL);
    xTaskCreate(bridge_task,        "bridge", 512, NULL, 3, NULL);

    vTaskStartScheduler();
    for (;;) { }
}
