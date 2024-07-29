#!/bin/bash
export PYTHONUNBUFFERED=1
export ACAPY_ADMIN=[0.0.0.0,8021]
export ACAPY_ADMIN_INSECURE_MODE=true
export ACAPY_AUTO_ACCEPT_INVITES=true
export ACAPY_AUTO_ACCEPT_REQUESTS=true
export ACAPY_AUTO_PING_CONNECTION=true
export ACAPY_AUTO_PROVISION=true
export ACAPY_AUTO_RESPOND_MESSAGES=true
export ACAPY_AUTO_STORE_CREDENTIAL=true
export ACAPY_EMIT_NEW_DIDCOMM_PREFIX=true
export ACAPY_ENDPOINT=https://172.28.56.159:8020
export ACAPY_GENESIS_URL=http://test.bcovrin.vonx.io/genesis
export ACAPY_LABEL=anton
export ACAPY_OUTBOUND_TRANSPORT=http3
export ACAPY_PRESERVE_EXCHANGE_RECORDS=true
export ACAPY_PUBLIC_INVITES=true
export ACAPY_REQUESTS_THROUGH_PUBLIC_DID=true
export ACAPY_WALLET_KEY=secret
export ACAPY_WALLET_NAME=anton
export ACAPY_WALLET_SEED=anton000000000000000000000000000
export ACAPY_WALLET_TYPE=askar
export ENABLE_PROMETHEUS=true
export PROMETHEUS_PORT=8022
aca-py start \
  --inbound-transport http3 0.0.0.0 8020 \
  --log-level info \
  --admin 0.0.0.0 8021 \
  --admin-insecure-mode \
  --auto-accept-invites \
  --auto-accept-requests \
  --auto-respond-messages \
  --auto-store-credential \
  --emit-new-didcomm-prefix \
  --endpoint "https://172.28.56.159:8020" \
  --genesis-url "http://test.bcovrin.vonx.io/genesis" \
  --label "anton" \
  --outbound-transport http3 \
  --preserve-exchange-records \
  --public-invites \
  --requests-through-public-did \
  --wallet-key "secret" \
  --wallet-name "anton" \
  --wallet-type askar \
  --seed "anton000000000000000000000000000"