# JOURNAL

## RP-20260222-002
- Date/Time: 2026-02-22 18:30 EST
- Context:
  - Susnet needed storage headroom and stable local-only control runtime before advancing agent integration.
- Decision:
  - Expand root partition to 100GiB, create dedicated 100GiB `/data` partition, and defer migration/remapping.
  - Activate Joe Cabot lightweight MQTT runtime for immediate control-plane value with bounded outputs.
- Implementation:
  - Repartitioned `/dev/mmcblk0` (msdos):
    - `p2` resized to 100GiB
    - `p3` created at 100GiB and formatted ext4 (`DATA`)
  - Mounted `/data` by UUID in `/etc/fstab` and created data skeleton directories.
  - Deployed `joe-cabot-lite.service` on host Python venv:
    - consumes `meshbox/agent/events/{rx,policy,health,nodes}`
    - serves query/reply on `susnet/agent/query` and `susnet/agent/reply`
  - Updated OpenClaw host exposure:
    - host bind changed to `28789`
    - Tailscale serve mapped `18789 -> localhost:28789`
- Failure(s) / Incident(s):
  - Initial `piwheels` timeout during dependency fetch.
  - Stuck docker build process during helper image approach.
  - Post-reboot OpenClaw bind conflict on `18789` due Tailscale serve interaction.
- Verification:
  - Root/data mounts and capacities validated after reboot.
  - Joe Cabot service active and subscribed to required topics.
  - Direct terminal query/reply workflow verified from SSH.
  - OpenClaw endpoint reachable at `susnet:18789`.
- Open Risks / Follow-ups:
  - Move heavy raw/log retention paths to `/data` in a dedicated migration wave.
  - Add robust retry wrapper for intermittent package-download timeouts.


## RP-20260222-003
- Date/Time: 2026-02-22 19:02 EST
- Context:
  - Mr. Pink dedicated-channel behavior needed stronger conversational handling and not just fixed utility replies.
- Decision:
  - Expand Joe Cabot reply logic to support lightweight conversational prompts while preserving strict bounded-output policy.
- Implementation:
  - Updated `/home/codex/joe-cabot-lite/joe_cabot_lite.py` with:
    - broker query handling for richer conversational prompts
    - local-model best-effort generation path
    - deterministic local conversational fallback templates
    - broad-request refusal guardrails retained
  - Restarted `joe-cabot-lite.service` after syntax validation.
- Failure(s) / Incident(s):
  - Local LLM HTTP path can exceed timeout budget under load, triggering fallback responses.
- Verification:
  - MQTT query/reply tests returned contextual conversational text for greeting and identity prompts.
  - Utility intents (traffic summary) remained functional.
- Open Risks / Follow-ups:
  - Tune model timeout/latency tradeoff after live RF testing.
  - Optional future optimization: persistent local model endpoint with faster first-token behavior.


## RP-20260222-004
- Date/Time: 2026-02-22 19:52 EST
- Context:
  - Operator requested a simpler direct terminal interaction path than manual `mosquitto_pub/sub` flows.
- Decision:
  - Add a one-command CLI wrapper for Joe Cabot direct query and optional chat mode.
- Implementation:
  - Added runtime script: `/home/codex/joe-cabot-lite/ask_joe.py`.
  - Added command aliases: `/usr/local/bin/ask-joe` and `/usr/local/bin/joe`.
  - Configured defaults: broker `100.124.168.35`, timeout `25s`, retries `2`.
- Failure(s) / Incident(s):
  - Initial timeout at lower default timeout; solved by raising timeout and retrying.
- Verification:
  - `joe "traffic load summary please"` returned live summary.
  - `joe "who are you"` returned conversational response.
  - `joe "status"` returned online snapshot.
- Open Risks / Follow-ups:
  - If model latency rises, tune `--timeout` upward for direct CLI sessions.

## RP-20260224-001
- Date/Time: 2026-02-24 14:10 EST
- Context:
  - MeshBox front-desk refactor introduced lifecycle topics and timeout semantics that must be mirrored in Susnet control-plane documentation.
- Decision:
  - Align Susnet docs and control contract with Mr Pink and Joe deterministic lifecycle model.
- Implementation:
  - Updated owner manual canonical state with full Joe lifecycle topic set.
  - Recorded front-desk timing defaults and escalation semantics.
  - Added logbook and changelog entries for cross-repo traceability.
- Failure(s) / Incident(s):
  - No runtime incident during documentation sync.
- Verification:
  - Joe service active and subscribed to `susnet/agent/query` and `susnet/agent/control`.
  - Recent lifecycle tests observed ack/progress/reply and cancellation states on broker.
- Open Risks / Follow-ups:
  - Track runtime source in versioned repo path instead of host-only `/home/codex/joe-cabot-lite`.

## RP-20260224-002
- Date/Time: 2026-02-24 16:03 EST
- Context:
  - A user-visible wrong arithmetic answer (`2+2` -> `8`) was observed during front-desk validation and treated as a high-priority reliability defect.
- Decision:
  - Add deterministic correctness guardrail for simple arithmetic and remove upstream metadata noise from query text before intent processing.
- Implementation:
  - Updated `/home/codex/joe-cabot-lite/joe_cabot_lite.py` runtime with:
    - `_extract_user_request()` to strip appended `RF output constraints` metadata from edge escalations.
    - `_safe_arithmetic_reply()` for deterministic handling of simple numeric expressions.
    - model temperature changed to `0.0` for lower variance on short factual replies.
  - Restarted `joe-cabot-lite.service` and revalidated direct and edge-escalated query paths.
- Failure(s) / Incident(s):
  - Root cause was not duplicate message processing; it was a combination of model variance and un-sanitized escalated prompt text.
- Verification:
  - Direct CLI repeated probes returned stable `4` responses.
  - MeshBox->Joe escalated path returned `4` with `status=reply` and sub-second processing for arithmetic prompt.
- Open Risks / Follow-ups:
  - Runtime source currently lives in host path outside repo tracking; migrate runtime source to versioned repo path for stronger change control.
