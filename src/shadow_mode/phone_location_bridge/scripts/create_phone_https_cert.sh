#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${1:-Data/certs/phone_location_bridge}"
HOST_IP="${2:-}"

mkdir -p "${OUT_DIR}"

if [[ -z "${HOST_IP}" ]]; then
    HOST_IP="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i=1; i<=NF; i++) if ($i == "src") {print $(i+1); exit}}')"
fi

if [[ -z "${HOST_IP}" ]]; then
    echo "[ERROR] Could not detect host IP. Pass it explicitly: create_phone_https_cert.sh <out_dir> <ip>" >&2
    exit 1
fi

cat >"${OUT_DIR}/openssl.cnf" <<EOF
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
x509_extensions = v3_req

[dn]
CN = phone-location-bridge

[v3_req]
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
IP.1 = 127.0.0.1
IP.2 = ${HOST_IP}
EOF

openssl req -x509 -nodes -days 365 \
    -newkey rsa:2048 \
    -keyout "${OUT_DIR}/phone_location_bridge.key" \
    -out "${OUT_DIR}/phone_location_bridge.crt" \
    -config "${OUT_DIR}/openssl.cnf"

cat <<EOF
[INFO] Created:
  ${OUT_DIR}/phone_location_bridge.crt
  ${OUT_DIR}/phone_location_bridge.key

[INFO] HTTPS launch args:
  use_https:=true tls_cert_file:=${OUT_DIR}/phone_location_bridge.crt tls_key_file:=${OUT_DIR}/phone_location_bridge.key

[WARN] For phone geolocation, the phone browser must trust this certificate/CA.
EOF
