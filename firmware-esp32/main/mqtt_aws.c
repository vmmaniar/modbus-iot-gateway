#include "mqtt_aws.h"

#include <stdlib.h>
#include "esp_log.h"
#include "nvs.h"
#include "mqtt_client.h"

static const char *TAG = "aws-mqtt";
static esp_mqtt_client_handle_t s_client;
static volatile bool s_connected;

static char *load_nvs_blob(const char *key)
{
    nvs_handle_t h;
    if (nvs_open("aws_certs", NVS_READONLY, &h) != ESP_OK) return NULL;
    size_t sz = 0;
    if (nvs_get_str(h, key, NULL, &sz) != ESP_OK || sz == 0) {
        nvs_close(h);
        return NULL;
    }
    char *buf = malloc(sz);
    if (!buf) { nvs_close(h); return NULL; }
    if (nvs_get_str(h, key, buf, &sz) != ESP_OK) {
        free(buf);
        nvs_close(h);
        return NULL;
    }
    nvs_close(h);
    return buf;
}

static void mqtt_event(void *args, esp_event_base_t base, int32_t id, void *data)
{
    esp_mqtt_event_handle_t evt = data;
    switch ((esp_mqtt_event_id_t)id) {
        case MQTT_EVENT_CONNECTED:    s_connected = true;  ESP_LOGI(TAG, "AWS IoT connected"); break;
        case MQTT_EVENT_DISCONNECTED: s_connected = false; ESP_LOGW(TAG, "disconnected"); break;
        case MQTT_EVENT_ERROR:        ESP_LOGE(TAG, "TLS error %d", evt->error_handle->error_type); break;
        default: break;
    }
}

esp_err_t mqtt_aws_start(const char *endpoint_uri)
{
    char *cert_pem    = load_nvs_blob("cert_pem");
    char *private_key = load_nvs_blob("private_key");
    char *ca_root     = load_nvs_blob("ca_root");
    if (!cert_pem || !private_key || !ca_root) {
        ESP_LOGE(TAG, "Device certs missing — provision via aws_iot_provisioning.md");
        free(cert_pem); free(private_key); free(ca_root);
        return ESP_ERR_NOT_FOUND;
    }

    esp_mqtt_client_config_t cfg = {
        .broker.address.uri = endpoint_uri,
        .credentials.authentication.certificate = cert_pem,
        .credentials.authentication.key         = private_key,
        .broker.verification.certificate        = ca_root,
    };
    s_client = esp_mqtt_client_init(&cfg);
    if (!s_client) return ESP_FAIL;
    esp_mqtt_client_register_event(s_client, ESP_EVENT_ANY_ID, mqtt_event, NULL);
    return esp_mqtt_client_start(s_client);
}

esp_err_t mqtt_aws_publish_binary(const char *topic, const uint8_t *data, size_t len)
{
    if (!s_connected) return ESP_ERR_INVALID_STATE;
    int msg_id = esp_mqtt_client_publish(s_client, topic, (const char *)data, len, 1, 0);
    return msg_id < 0 ? ESP_FAIL : ESP_OK;
}
