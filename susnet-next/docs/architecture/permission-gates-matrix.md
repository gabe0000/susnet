# Permission Gates Matrix

| Component | Identity Used | Auth Mechanism | Authorization Gate | Allowed Resources/Topics | Failure Mode | Audit Signal |
| --- | --- | --- | --- | --- | --- | --- |
| control broker | service account | broker auth | ACL rules | `susnet/agent/*` scoped topics | connect/publish denied | broker logs |
| control runtime | channel + sender context | envelope validation | policy + schema gates | lifecycle emit and state updates | `error` or `dlq` | policy events |
| edge bridge ingress | channel identity + sender | policy rules | dedicated-channel and allowlist gate | escalation or bounded local reply | deny path response | policy decision stream |
| edge relay egress | request correlation and chunk budget | runtime checks | sequencing and budget guard | bounded reply chunks | summary/refusal or timeout report | relay metrics |

## Rule
Authorization decisions must use channel name plus key fingerprint and sender policy, never channel index.
