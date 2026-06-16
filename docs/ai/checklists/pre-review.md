# Pre-review Checklist

- [ ] Active goal or task spec is clear.
- [ ] Diff is scoped to that goal.
- [ ] Worker output, if any, was inspected by Codex.
- [ ] `./scripts/ai-verify.sh` has run, or the blocker is documented.
- [ ] Focused tests for changed behavior have run, or the reason is documented.
- [ ] No forbidden external state mutation was executed.
- [ ] No `.env` contents, secrets, CASP author code, or PII were exposed.
