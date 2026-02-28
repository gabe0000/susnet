# Surface: Permission Gates

Gate layers:
1. broker authentication and ACL
2. edge channel identity and sender policy
3. control runtime schema and safety state
4. outbound budget and sequencing controls

Anti-pattern:
- channel index must never be used for authorization logic.
