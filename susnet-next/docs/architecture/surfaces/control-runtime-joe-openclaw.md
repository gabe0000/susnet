# Surface: Control Runtime (Joe/OpenClaw)

Responsibilities:
- validate query envelope
- emit lifecycle (`ack/progress/reply/error`)
- execute runtime path (OpenClaw or controlled fallback)
- preserve contract shape regardless of execution mode
