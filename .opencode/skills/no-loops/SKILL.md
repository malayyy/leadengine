---
name: no-loops
description: Use ONLY when writing or editing Python code. Enforces the project rule that for, while, and comprehensions are forbidden — use map, filter, reduce, recursion, or lambda instead.
---

# No Loops Rule

This project **strictly forbids** the following Python constructs:
- `for` loops
- `while` loops
- List comprehensions (`[x for x in y]`)
- Dict comprehensions (`{k: v for k, v in x}`)
- Set comprehensions (`{x for x in y}`)

## Allowed Alternatives
- `map(function, iterable)` — transform each element
- `filter(predicate, iterable)` — keep matching elements
- `reduce(function, iterable, initial)` — cumulative fold (from `functools`)
- `lambda` expressions — anonymous functions
- Recursion — function calling itself
- Generator expressions passed to `list()`, `dict()`, `set()` — these are acceptable ONLY when needed for lazy evaluation

## Examples

### BAD (forbidden)
```python
results = []
for item in items:
    if item.active:
        results.append(item.name)

names = [item.name for item in items if item.active]
```

### GOOD (allowed)
```python
results = list(map(
    lambda item: item.name,
    filter(lambda item: item.active, items)
))

from functools import reduce
total = reduce(lambda acc, x: acc + x.price, filter(lambda x: x.active, items), 0)
```
