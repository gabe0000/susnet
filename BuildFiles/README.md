# BuildFiles

Working folder for high-level documentation around "the box" project. Use this tree for:
- Journaling daily/weekly progress and lessons learned.
- Capturing design constraints, ideas, and future improvements.
- Troubleshooting logs and fixes.
- Builder notes for specific subsystems (APRS, Meshtastic, AllStar, power, etc.).
- Converting idea sparks into shippable features (IdeaBacklog + FeatureRoadmap).
- Detailing replication steps so another builder can recreate the box.

Every document should reinforce:
1. What the box is and does.
2. How it is used and operated.
3. How to replicate or extend it.
4. What to change or improve next time.

Current key files:
- `../Journal/` (top-level) – daily wins/losses/lessons, one file per entry.
- `BuilderNotes.md` – subsystem deep dives (APRS RF experiments, Pi split, etc.).
- `IdeaBacklog.md` / `FeatureRoadmap.md` – pipeline from brainstorming to delivery.
- `DesignConsiderations.md` – overarching requirements and constraints.
- `ReplicationGuide.md` – how to build another box (WIP).
- `../Troubleshooting/` (top-level) – support tickets and resolutions.

Add new files as needed, but keep the structure predictable so others can follow along.
