
## 2026-02-07 - SQLAlchemy AsyncSession rowcount typing
**Learning:** Mypy does not recognize `rowcount` on the `Result` object returned by `AsyncSession.execute` for update statements, even though it exists at runtime (via `CursorResult`).
**Action:** When using `rowcount` after an update/delete, explicit casting `int(result.rowcount or 0)` and `# type: ignore` is required to satisfy mypy.
