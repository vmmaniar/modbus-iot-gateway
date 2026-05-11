idf_component_register(
    SRCS "app_main.c" "wifi_sta.c" "mqtt_aws.c" "bridge_rx.c"
    INCLUDE_DIRS "."
    REQUIRES driver esp_wifi nvs_flash mqtt esp_event esp_netif esp-tls
)
