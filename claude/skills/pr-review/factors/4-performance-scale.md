---
factor: 4-performance-scale
title: Performance, Scale & Resource Efficiency
---

## Focus
Will this slow the system under load or waste memory?

## Check for
- N+1 queries
- Missing indexes
- Unoptimized loops
- Memory leaks (unclosed streams/listeners)
- Blocked event loops
- Heavy computation on the main thread
