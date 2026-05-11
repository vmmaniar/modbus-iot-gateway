# AWS IoT provisioning

The ESP32 firmware reads its X.509 device cert, private key, and the Amazon Root CA from the `aws_certs` NVS namespace at boot. Before the first deployment you must provision these.

## 1. Create the thing in AWS IoT Core

```bash
aws iot create-thing --thing-name gateway-001
aws iot create-keys-and-certificate --set-as-active \
    --certificate-pem-outfile gateway-001.cert.pem \
    --private-key-outfile      gateway-001.private.key \
    --public-key-outfile       gateway-001.public.key
aws iot attach-policy --policy-name gateway-publish --target <cert-arn>
aws iot attach-thing-principal --thing-name gateway-001 --principal <cert-arn>
```

Get the Amazon Root CA:

```bash
curl -o AmazonRootCA1.pem https://www.amazontrust.com/repository/AmazonRootCA1.pem
```

## 2. Write certificates into NVS on the ESP32

Use the `nvs_partition_gen.py` utility from ESP-IDF to build a CSV and flash it:

```csv
key,type,encoding,value
aws_certs,namespace,,
cert_pem,data,string,gateway-001.cert.pem
private_key,data,string,gateway-001.private.key
ca_root,data,string,AmazonRootCA1.pem
```

```bash
python $IDF_PATH/components/nvs_flash/nvs_partition_generator/nvs_partition_gen.py \
    generate nvs_certs.csv nvs_certs.bin 0x6000
esptool.py write_flash 0x9000 nvs_certs.bin
```

## 3. IAM policy (minimum scope)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "iot:Connect",
      "Resource": "arn:aws:iot:us-east-1:<acct>:client/gateway-001"
    },
    {
      "Effect": "Allow",
      "Action": "iot:Publish",
      "Resource": "arn:aws:iot:us-east-1:<acct>:topic/iot/gateway-001/telemetry"
    }
  ]
}
```

## 4. Verify

After flashing, monitor the serial console:

```
I (1234) aws-mqtt: AWS IoT connected
I (2345) app: published 47 bytes to iot/gateway-001/telemetry
```

In the AWS IoT Console → Test → MQTT test client, subscribe to `iot/gateway-001/telemetry` and you should see binary CBOR payloads arriving.
