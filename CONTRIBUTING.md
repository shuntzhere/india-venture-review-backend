# Contributing

This file documents the development conventions for the India Venture Review project.

---

## Documentation Convention

Every time a new file is created or updated inside `docs/implementation/`, the following must also be updated **in the same commit**:

- **`CHANGELOG.md`** — add a new versioned entry describing what was added or changed
- **`TODO.md`** — mark completed items and add any new upcoming items if relevant

This rule applies to every milestone, refinement, and documentation update without exception.

---

## Commit Message Convention

Every commit message should follow this format:

```
Step X.Y: Brief description of what was done
```

**Examples:**

```
Step 3.2: Implemented funding article classifier
Step 2.3: Added classification confidence migration
Step 3.3: Added implementation documentation for Steps 3, 3.1, and 3.2
```

---

## Migration Convention

Every database schema change must:

1. Be saved as a **new SQL file** in `sql/` — never modify existing SQL files
2. Be documented in `docs/implementation/step-X/`
3. Be recorded in `CHANGELOG.md`
