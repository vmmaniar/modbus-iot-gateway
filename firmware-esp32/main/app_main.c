#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "sdkconfig.h"

#include "wifi_sta.h"
#include "mqtt_aws.h"
#include "bridge_rx.h"

#define BRIDGE_UART  UART_NUM_1
#define BRIDGE_RX_GPIO  16
#define BRIDGE_TX_GPIO  17
#define BRIDGE_BAUD     115200

static const char *TAG = "app";

static void on_telemetry(const uint8_t *cbor, size_t len)
{
    esp_err_t err = mqtt_aws_publish_binary(CONFIG_MQTT_TOPIC_TELEMETRY, cbor, len);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "publish failed %d (Wi-Fi or broker down?)", err);
    }
}

void app_main(void)
{
    ESP_LOGI(TAG, "Modbus gateway ESP32 layer starting");

    ESP_ERROR_CHECK(wifi_sta_start_blocking(CONFIG_WIFI_SSID, CONFIG_WIFI_PASSWORD));
    ESP_ERROR_CHECK(mqtt_aws_start(CONFIG_AWS_IOT_ENDPOINT));
    ESP_ERROR_CHECK(bridge_rx_start(BRIDGE_UART, BRIDGE_RX_GPIO, BRIDGE_TX_GPIO,
                                    BRIDGE_BAUD, on_telemetry));

    // Idle — bridge_rx_start spawned the worker that drives MQTT publishes
    while (1) { vTaskDelay(pdMS_TO_TICKS(1000)); }
}
