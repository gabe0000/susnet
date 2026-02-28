# Message Flows

## Flow A: Mesh Radio -> MeshBox Stock Broker Path
```mermaid
sequenceDiagram
  participant N as RF Node
  participant B as MeshBox Stock Broker
  participant E as MeshBox Edge Bridge
  N->>B: stock Meshtastic payload on msh/US/...
  B->>E: stock ingress event
  E->>E: policy + identity gate
```

## Flow B: MeshBox Custom Broker -> Susnet Agent/Joe Path
```mermaid
sequenceDiagram
  participant E as MeshBox Edge Bridge
  participant C as Susnet Broker
  participant J as Joe Runtime
  E->>C: susnet/agent/query
  C->>J: deliver query
  J->>C: susnet/agent/ack
  J->>C: susnet/agent/progress
  J->>C: susnet/agent/reply
  C->>E: lifecycle events
  E->>E: pacing + ordering + relay guard
```

## Explicit Gate Points
1. Broker authentication.
2. Topic ACL enforcement.
3. Edge policy allow/deny.
4. Control runtime schema and safety checks.
5. Outbound chunk ordering and pacing.
