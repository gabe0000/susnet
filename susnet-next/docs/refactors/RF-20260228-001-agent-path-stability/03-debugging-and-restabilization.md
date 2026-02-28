# Debugging And Restabilization

Key recurring issues tracked:
1. channel identity confusion when channel index was treated as stable selector
2. callback/path timing causing intermittent relay behavior
3. poll-heavy observability path causing burst load noise

Stabilization action:
- treat channel index only as transport metadata
- preserve lifecycle ordering and bounded pacing
- document poll-to-event migration as follow-up
