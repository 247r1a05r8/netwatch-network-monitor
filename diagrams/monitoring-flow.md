# Monitoring Flow

The engine ticks every 2 seconds. Each check runs only when its interval has passed.

```text
tick (every 2 s)
  |-- interface + local IP + bandwidth   (every tick, 2 s)
  |-- gateway ping                       (every 4 s)
  |-- internet ping + HTTP check         (every 6 s)
  |-- DNS resolution                     (every 10 s)
  |-- TCP services + HTTP URLs           (every 6 s)
  `-- generate events (state changes)    (every tick)
Each check is wrapped in try/except: one failure never stops the others.
```

```mermaid
flowchart TD
  T[Tick every 2 s] --> I[Interface and bandwidth]
  T --> G{Gateway due?}
  G -- yes --> G1[Ping gateway]
  T --> N{Internet due?}
  N -- yes --> N1[Ping and HTTP check]
  T --> D{DNS due?}
  D -- yes --> D1[Resolve domain]
  T --> S{Services due?}
  S -- yes --> S1[TCP and URL checks]
  I --> E[Compare with previous state]
  G1 --> E
  N1 --> E
  D1 --> E
  S1 --> E
  E --> L[Write events and alerts]
  E --> H[Compute HEALTHY / DEGRADED / OFFLINE]
```
