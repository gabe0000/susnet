# Component Boundaries (Susnet View)

## Ownership and Trust Boundaries
| Component | Owner | Runtime Location | Trust Boundary | In Scope for Susnet Docs |
| --- | --- | --- | --- | --- |
| RF node firmware | Edge operator | Radio hardware | Untrusted radio network input | Behavioral expectations only |
| MeshBox edge bridge | Edge operator | MeshBox host | Boundary crossing from RF to MQTT | Yes (interface contract) |
| MeshBox stock broker | Edge operator | MeshBox host | ACL + bridge boundary | Yes (interface contract) |
| Susnet backend broker | Control operator | Susnet host | Broker auth and ACL enforcement | Yes (full) |
| Joe runtime | Control operator | Susnet host | Query validation and response policy | Yes (full) |
| Public docs repo | Documentation owner | GitHub public | Sanitized projection only | Yes (mapping only) |

## Documentation Rules
- Runtime-sensitive details remain in private repos.
- Public `resevoir-pis` receives sanitized architectural projection only.
- Every identity/topic change must update contracts and `docs/CHANGE_IMPACTS.md`.
