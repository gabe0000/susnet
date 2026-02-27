# Custom MeshBox-Susnet Agent Contract (Private Reference)

## Topics
- Request: `susnet/agent/query`
- Lifecycle responses: `susnet/agent/ack`, `susnet/agent/progress`, `susnet/agent/reply`
- Optional dead-letter/error path: `susnet/agent/error`

## Request Envelope
```json
{
  "request_id": "string",
  "sender": "string",
  "text": "string",
  "ts": 0,
  "context": {
    "source": "meshbox",
    "channel": "string"
  }
}
```

## Response Envelope
```json
{
  "request_id": "string",
  "status": "ack|progress|completed|error",
  "agent": "Joe Cabot",
  "text": "string",
  "chunk_index": 1,
  "chunk_count": 1,
  "ts": 0
}
```

## JSON Schema (Request)
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["request_id", "sender", "text"],
  "properties": {
    "request_id": {"type": "string", "minLength": 1},
    "sender": {"type": "string", "minLength": 1},
    "text": {"type": "string", "minLength": 1},
    "ts": {"type": "integer"},
    "context": {
      "type": "object",
      "properties": {
        "source": {"type": "string"},
        "channel": {"type": "string"}
      },
      "additionalProperties": true
    }
  },
  "additionalProperties": true
}
```

## Validation and Errors
- Non-JSON or non-object payloads are rejected.
- Missing required keys are rejected.
- Rejections emit `status=error` with the same `request_id` when possible.
- Runtime errors also emit error responses and are journaled.

## Compatibility Rule
This custom contract is intentionally separate from stock Meshtastic MQTT topics and may evolve independently.
