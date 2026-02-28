# Cross-Host Component Map

| Component | Host | Repo Owner | Input Contract | Output Contract |
| --- | --- | --- | --- | --- |
| stock MQTT ingest and edge bridge | MeshBox | meshbox-privat | `msh/US/...` | `susnet/agent/query` |
| control broker and runtime | Susnet | susnet | `susnet/agent/query` | `susnet/agent/ack|progress|reply|error|dlq` |
| public documentation projection | docs repo | resevoir-pis | private canonical docs | public-safe projection |

## Compatibility Rule
No contract-breaking changes to stock or custom paths without explicit versioned doc updates.
