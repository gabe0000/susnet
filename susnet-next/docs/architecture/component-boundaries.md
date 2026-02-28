# Component Boundaries

## Ownership
| Component | Runtime Location | Owner | Trust Boundary |
| --- | --- | --- | --- |
| `susnet-next-mosquitto` | Susnet | Susnet repo | broker auth and ACL boundary |
| `real-joe` | Susnet | Susnet repo | control execution and schema boundary |
| `real-joe-redis` | Susnet | Susnet repo | request/session state boundary |
| MeshBox edge bridge | MeshBox | meshbox-privat repo | channel identity and sender gate boundary |

## Boundary Rules
1. Stock transport semantics remain in stock MQTT path.
2. Custom lifecycle semantics remain in `susnet/agent/*`.
3. Channel index is not an authorization selector.
4. Cross-host contracts are versioned docs artifacts.
