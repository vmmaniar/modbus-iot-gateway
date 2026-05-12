"""Phase 6 producer — drives the firmware-twin in a container, publishing
each polled record as:
  - `iot/{thing}/telemetry`       binary CBOR (production-equivalent)
  - `iot/{thing}/telemetry/json`  JSON (consumed by Telegraf → InfluxDB)

The JSON twin is purely to bridge to Telegraf's data parsers. In a real
deployment Telegraf would use an `execd` processor with a CBOR decoder.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import time

import paho.mqtt.client as mqtt

from simulator.firmware_twin import (
    DEFAULT_POLL_TABLE, TcpTransport, run_master,
)


logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("producer")


def decode_value_for_label(label: str, regs: list[int]) -> dict[str, float | int]:
    """Match the per-label semantics defined in simulator/tcp_slave.py."""
    if label == "tank_pressure" and len(regs) >= 2:
        pa = (regs[0] << 16) | regs[1]
        return {"pressure_pa": pa, "pressure_kpa": pa / 1000.0}
    if label == "ambient_temp" and len(regs) >= 1:
        return {"temp_centi_c": regs[0], "temp_c": regs[0] / 100.0}
    if label == "flow_meter" and len(regs) >= 4:
        flow = (regs[0] << 16) | regs[1]
        totalizer = (regs[2] << 16) | regs[3]
        return {"flow_m3h": flow, "totalizer_m3": totalizer}
    # Fallback: raw register dump
    return {f"reg_{i}": v for i, v in enumerate(regs)}


def run() -> None:
    modbus_host = os.environ.get("MODBUS_HOST", "127.0.0.1")
    modbus_port = int(os.environ.get("MODBUS_PORT", "5020"))
    mqtt_host   = os.environ.get("MQTT_HOST",  "127.0.0.1")
    mqtt_port   = int(os.environ.get("MQTT_PORT",  "1883"))
    mqtt_topic  = os.environ.get("MQTT_TOPIC", "iot/gateway-001/telemetry")

    log.info("connecting to Modbus %s:%d", modbus_host, modbus_port)
    # Retry the Modbus connect — the simulator container takes ~1 s to bind
    last_err: Exception | None = None
    for attempt in range(30):
        try:
            transport = TcpTransport(modbus_host, modbus_port)
            break
        except (OSError, ConnectionError) as e:
            last_err = e
            time.sleep(1.0)
    else:
        raise SystemExit(f"could not reach Modbus simulator after 30s: {last_err}")
    log.info("Modbus connection up")

    log.info("connecting to MQTT broker %s:%d", mqtt_host, mqtt_port)
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                         client_id="gateway-001")
    client.connect(mqtt_host, mqtt_port, keepalive=60)
    client.loop_start()
    log.info("MQTT loop started, publishing to %s", mqtt_topic)

    stop = False
    def _on_sigterm(_signum, _frame):
        nonlocal stop
        log.info("shutting down")
        stop = True
    signal.signal(signal.SIGTERM, _on_sigterm)
    signal.signal(signal.SIGINT, _on_sigterm)

    try:
        for reading in run_master(transport, poll_table=DEFAULT_POLL_TABLE):
            if stop:
                break
            cbor_frame = reading.to_framed_cbor()
            client.publish(mqtt_topic, cbor_frame, qos=0)

            decoded = decode_value_for_label(reading.entry.label, reading.registers)
            json_payload = {
                "label":  reading.entry.label,
                "slave":  reading.entry.slave_id,
                "ts_ms":  reading.timestamp_ms,
                **decoded,
            }
            client.publish(mqtt_topic + "/json", json.dumps(json_payload), qos=0)
            log.info("publish label=%s decoded=%s", reading.entry.label, decoded)
    finally:
        client.loop_stop()
        client.disconnect()
        transport.close()


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        sys.exit(0)
