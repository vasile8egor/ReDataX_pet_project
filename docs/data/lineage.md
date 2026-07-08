# Lineage

Lineage should make every reported number traceable.

## Path

```text
external source -> raw file -> parsed table -> feature table -> model artifact -> policy artifact -> report
```

## Requirements

- Keep source date ranges explicit.
- Store transformation parameters.
- Record run IDs in artifacts and analytical tables.
- Preserve failed or partial run logs when they explain missing dates.

