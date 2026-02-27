# Permission Gates Matrix (Susnet)

| Component | Identity Used | Auth Mechanism | Authorization Gate | Allowed Resources/Topics | Failure Mode | Audit Signal |
| --- | --- | --- | --- | --- | --- | --- |
| Susnet backend broker | `meshbox_bridge` | Mosquitto username/password | Mosquitto ACL | bridge topics for custom path and approved prefixes | Connection rejected or topic deny | Mosquitto auth/ACL logs |
| Susnet backend broker | `susnet_mesh` | Mosquitto username/password | Mosquitto ACL | `msh/#` stock-compatible path | Topic publish/subscribe denied | Mosquitto auth/ACL logs |
| Joe runtime subscriber | service account process | Local systemd unit + broker auth | JSON envelope validator | `susnet/agent/query` valid JSON objects | Payload rejected, DLQ/error response | Joe service logs |
| Joe runtime publisher | service account process | Local broker auth | Topic allowlist in code and ACL | `susnet/agent/ack`, `progress`, `reply` | Publish denied | Joe service logs + broker ACL logs |
| Control API handlers | internal app identity | local auth/session | role/intent checks | Joe request orchestration endpoints | 4xx/5xx refusal | app logs + journal update |

## Notes
- Channel identity gate (`name + key fingerprint`) is enforced at edge and documented in canonical public contract.
- Susnet assumes only validated custom envelopes arrive for Joe processing.
