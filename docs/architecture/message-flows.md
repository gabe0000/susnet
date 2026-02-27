# Message Flows (Susnet)

## Flow A: Mesh Radio -> Stock Meshtastic MQTT Path
```mermaid
sequenceDiagram
  participant Radio as RF Node
  participant Edge as MeshBox Bridge
  participant Stock as MeshBox Stock Broker
  participant Back as Susnet Broker

  Radio->>Edge: Mesh packet
  Edge->>Stock: Publish stock-compatible topic (msh/US/...)
  Note over Stock: Gate 1: broker auth
  Stock->>Back: Broker bridge relay
  Note over Back: Gate 2: bridge ACL allowlist
  Back-->>Stock: Optional downstream stock subscription data
```

## Flow B: MeshBox Custom Broker -> Susnet Agent/Joe
```mermaid
sequenceDiagram
  participant Edge as MeshBox Bridge
  participant Stock as MeshBox Broker
  participant Back as Susnet Broker
  participant Joe as Joe Runtime

  Edge->>Stock: Publish susnet/agent/query JSON envelope
  Note over Stock: Gate 1: bridge credentials
  Stock->>Back: Forward susnet/agent/query
  Note over Back: Gate 2: ACL topic permission
  Back->>Joe: Deliver JSON envelope
  Note over Joe: Gate 3: payload validation (required keys)
  Joe->>Back: ack/progress/reply
  Note over Back: Gate 4: publisher ACL allowlist
  Back->>Stock: Forward reply topics
  Stock->>Edge: Deliver response for RF relay
```

## Failure Handling
- Auth failure: broker rejects client session.
- ACL failure: publish/subscribe denied; no relay.
- Schema failure: Joe rejects malformed payload and emits error path.
