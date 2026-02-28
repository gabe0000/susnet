# Stock Meshtastic MQTT Contract

## Scope
- stock-compatible topic family under `msh/US/...`
- stock payload semantics preserved
- no custom control-plane JSON envelope semantics on stock path

## Invariants
1. no schema-breaking reinterpretation of stock payloads
2. no authorization decisions based on channel index
