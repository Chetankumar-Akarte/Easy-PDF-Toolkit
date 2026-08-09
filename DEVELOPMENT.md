# Development Notes

## Architectural Rule

Keep UI code in app/ui, business rules in app/core, and external integrations in app/infra.

## Coding Conventions

- Prefer small service methods with explicit inputs.
- Keep PDF engine calls behind adapter classes.
- Use command objects for state-changing editor actions.
- Keep long-running jobs off the UI thread.

## Immediate Backlog

1. Introduce dependency container for services.
2. Add autosave snapshots and crash recovery on top of the document dirty-state model.
3. Implement annotation commands using the existing per-document command history.
4. Add smoke tests for packaged app launch and file open flow.
