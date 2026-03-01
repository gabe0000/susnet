# 02 Design and Changes

## Phase B: Implementation

### Documentation Architecture Additions
- Added HQ layout contract doc.
- Added Office/Library/Desk boundary contract doc.
- Added containerization boundary map doc.
- Added storage governance policy doc.
- Added `become_an_expert` contract doc.
- Added external memory-management runbook.

### Governance Additions
- Added new refactor bundle with mandatory phased sections.
- Updated change impacts mapping to include HQ and expert corpus change classes.
- Updated consistency validator to require new docs and phase markers.

### Chosen Defaults
- Canonical root: `/data/Resevoir-Comms-HQ`.
- Max practical containerization target.
- Two-phase migration model.
- 20GB Library cap with 100MB raw ring.
- Threshold checkpoints at 5/10/15GB then every 500MB.
- Overflow policy: pause ingest and alert.
