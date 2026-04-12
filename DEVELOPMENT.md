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
2. Implement document model and dirty state sync.
3. Wire toolbar actions to service layer.
4. Add smoke tests for app shell launch and file open flow.
