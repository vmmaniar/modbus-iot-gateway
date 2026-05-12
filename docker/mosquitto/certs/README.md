# Mosquitto TLS certs

Run `bash init-certs.sh` once before bringing up the stack. This generates a
local CA, a server cert for the broker, and a sample device cert that mirrors
what an ESP32 would carry in NVS.

**Never commit the resulting `.key` files** — `.gitignore` already excludes them.

For real AWS IoT Core, replace these self-signed certs with AWS-issued ones
per `docs/aws_iot_provisioning.md`. The Mosquitto stack here intentionally
mirrors the same mTLS handshake so swapping endpoints is a config-only change.
