#!/usr/bin/env bash
# Generate self-signed CA + server + one device certificate for local testing.
# Run this once before bringing up the docker stack with TLS enabled.
#
# DO NOT use these certs in production. They are entirely for the dev loop.

set -euo pipefail

cd "$(dirname "$0")"

CA_SUBJ="/C=IN/ST=Goa/O=Maniar Dev/CN=local-ca"
SERVER_SUBJ="/C=IN/ST=Goa/O=Maniar Dev/CN=mosquitto"
DEVICE_SUBJ="/C=IN/ST=Goa/O=Maniar Dev/CN=gateway-001"

if [[ -f ca.crt ]]; then
    echo "Certs already exist; delete *.crt *.key first if you want fresh ones."
    exit 0
fi

# CA
openssl genrsa -out ca.key 2048
openssl req -x509 -new -nodes -key ca.key -sha256 -days 3650 \
    -subj "$CA_SUBJ" -out ca.crt

# Server (mosquitto broker)
openssl genrsa -out server.key 2048
openssl req -new -key server.key -subj "$SERVER_SUBJ" -out server.csr
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out server.crt -days 365 -sha256 \
    -extfile <(printf "subjectAltName=DNS:mosquitto,DNS:localhost,IP:127.0.0.1")

# Device (this is what an ESP32 would use to authenticate)
openssl genrsa -out device.key 2048
openssl req -new -key device.key -subj "$DEVICE_SUBJ" -out device.csr
openssl x509 -req -in device.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out device.crt -days 365 -sha256

# Cleanup
rm -f *.csr *.srl

echo
echo "Generated: ca.crt, server.crt, server.key, device.crt, device.key"
echo "Test publish over TLS:"
echo "  mosquitto_pub -h localhost -p 8883 --cafile ca.crt \\"
echo "    --cert device.crt --key device.key -t test -m hello -d"
