# Troubleshooting Flow

```text
Run Network Diagnostics
  1. Local interface   -> FAIL: check Wi-Fi/Ethernet, adapter
  2. Default gateway   -> not found: set manually
  3. Gateway ping      -> FAIL: local network/router may be unavailable
  4. DNS resolution    -> FAIL: DNS server may be unreachable
  5. Internet check    -> FAIL + gateway OK: possible upstream/WAN problem
  6. Configured services -> FAIL: service stopped, blocked or host down
Result: "No basic connectivity problem detected" or "Possible problem areas: ..."
```

```mermaid
flowchart TD
  S[Run diagnostics] --> A{Interface has IP?}
  A -- no --> A1[FAIL: check connection]
  A -- yes --> B{Gateway ping ok?}
  B -- no --> B1[FAIL: local path or router]
  B -- yes --> C{DNS resolves?}
  C -- no --> C1[FAIL: DNS problem possible]
  C -- yes --> D{Internet reachable?}
  D -- no --> D1[FAIL: upstream problem possible]
  D -- yes --> E{Services up?}
  E -- no --> E1[FAIL: service problem]
  E -- yes --> OK[No basic problem detected]
```
All wording is "possible cause": the tool cannot identify every root cause.
