---
factor: 8-state-concurrency
title: State Management, Concurrency & Side Effects
---

## Focus
How does this interact with shared mutable state or async code?

## Check for
- Race conditions
- Missing thread safety
- Accidental global state mutation
- Unhandled side effects (e.g. React `useEffect` loops)
