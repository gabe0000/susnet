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
