# Containerization Boundary Map

## Goal
Maximize practical containerization while leaving only unavoidable host-level operations outside containers.

## Containerized Services
| Service | Responsibility | Primary Mounts | Read/Write |
| --- | --- | --- | --- |
| `real-joe` | control runtime lifecycle and policy events | `/data/Resevoir-Comms-HQ/Offices/Joe`, `/data/Resevoir-Comms-HQ/Desks/Joe`, `/data/Resevoir-Comms-HQ/Library` | mixed by subpath policy |
| `office-redis` | desk hot context cache | `/data/Resevoir-Comms-HQ/Offices/Joe/redis` | rw |
| `library-stream-writer` | protobuf stream ring writes | `/data/Resevoir-Comms-HQ/Library/streams` | rw |
| `library-normalizer` | books and summaries | `/data/Resevoir-Comms-HQ/Library/books` | rw |
| `library-indexer` | corpus indexing | `/data/Resevoir-Comms-HQ/Library/index` | rw |
| `library-cap-manager` | thresholds and cap enforcement | `/data/Resevoir-Comms-HQ/Library` | rw |
| `expertise-manager` | become_an_expert staging and promotion | `/data/Resevoir-Comms-HQ/Library/corpus`, `/data/Resevoir-Comms-HQ/Offices/*/expertise` | rw |
| `live-curated-monitor` | high-signal monitor stream | `/data/Resevoir-Comms-HQ/Library/streams/live-curated.ndjson` | rw |
| `alert-dispatcher` | dedicated-channel and mqtt alerts | none | n/a |
| `openclaw-ollama` | local model serving | `/data/Resevoir-Comms-HQ/Models/Ollama` | rw |

## Host-Level Exceptions
- One-time filesystem bootstrap.
- One-time migration copy operations.
- Emergency break-glass cleanup if cap response automation is unavailable.

## Runtime Controls
- All container services publish structured lifecycle/policy events.
- All writer containers must include cap checks before write operations.
