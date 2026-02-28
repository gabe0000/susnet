# Custom MeshBox-Susnet Agent Contract

## Topics
- `susnet/agent/query`
- `susnet/agent/ack`
- `susnet/agent/progress`
- `susnet/agent/reply`
- `susnet/agent/error`
- `susnet/agent/dlq`
- `susnet/agent/control`

## Required Keys (Query Envelope)
- `request_id`
- `session_id`
- `sender`
- `text`
- `channel_name`
- `channel_fingerprint`

## Notes
- `channel_index` is transport metadata only.
- Runtime may add non-breaking optional fields such as `engine`, `tool_run_id`, `safety_state`, `error_code`.
