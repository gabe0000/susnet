# Stock Meshtastic MQTT Contract (Private Reference)

## Intent
Preserve stock Meshtastic topic and payload semantics on the stock path. No custom payload keys are injected into stock messages.

## Contract
- Topic root is `msh/US/...`.
- Payload format remains Meshtastic-native as produced by bridge/radio stack.
- Consumers must treat stock traffic as pass-through telemetry or commands under Meshtastic conventions.
- Custom agent orchestration must not reuse stock topics.

## Gate Requirements
- Broker auth is mandatory for all stock path clients.
- ACL grants only required stock prefixes (`msh/#`) for the service account.
- Any stock-to-custom transformation must happen outside stock topics and be documented in custom contract.

## Verification
- Publish and subscribe tests confirm `msh/US/...` continuity across bridge boundary.
- ACL deny tests confirm non-stock topics are blocked for stock-only identities.
