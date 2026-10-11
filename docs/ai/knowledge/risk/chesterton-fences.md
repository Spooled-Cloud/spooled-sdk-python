# Fences

- Version metadata historically drifted (User-Agent vs package); keep `_version` + pyproject aligned.
- Worker `ActiveJob.settled` is the single-ack guard (complete/fail/timeout/shutdown race); do not drop it to "simplify" the ownership checks.
- `PurgeDlqParams.confirm` must stay required (no default): `purge({})` deletes the whole org's DLQ.

