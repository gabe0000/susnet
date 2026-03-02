# Susnet System Map

## Purpose
This is the private canonical system map for control-host architecture and cross-host coordination with MeshBox.

## Component Taxonomy
- Control broker and lifecycle topics
- Control runtime (`custom-agent-gateway`) and fallback runtime behavior
- Optional deep execution surface (OpenClaw/tool path)
- Edge bridge integration boundary
- Documentation and governance boundary

## Relationship Map
```mermaid
flowchart LR
  M[MeshBox Edge Bridge Mr Pink] --> Q[susnet/agent/query]
  Q --> C[Custom Agent Gateway]
  C --> L[susnet/agent/ack progress reply error dlq]
  L --> M
  C --> R[Redis State and Dedupe]
  C --> O[Local Model Runtime]
  C -. optional escalation .-> X[OpenClaw Tool Runtime]
  M --> S[Stock MQTT path msh/US/...]
```

## Operating Posture (Current Checkpoint)
1. Edge-first conversational reliability is the primary requirement.
2. Contract lifecycle behavior is preserved regardless of backend execution mode.
3. OpenClaw path is optional/degraded-safe; base operation remains available without it.
4. Authorization decisions remain identity-based and never depend on channel index.

## Linked Docs
- [Component Boundaries](component-boundaries.md)
- [Permission Gates Matrix](permission-gates-matrix.md)
- [Message Flows](message-flows.md)
- [Cross-Host Component Map](cross-host-component-map.md)
- [Surface: Stock Meshtastic](surfaces/stock-meshtastic.md)
- [Surface: Edge Bridge Mr. Pink](surfaces/edge-bridge-mr-pink.md)
- [Surface: Control Runtime Joe OpenClaw](surfaces/control-runtime-joe-openclaw.md)
- [Surface: Permission Gates](surfaces/permission-gates.md)
