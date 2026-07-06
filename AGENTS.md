# DDMP repository guidance

## Scope

This repository implements the maize variety digital display platform described in
`docs/05-detailed-functional-requirements.md`.

## Stack

- Python 3.13
- Django 5.2 LTS
- PostgreSQL 17 in shared environments
- Django templates and plain CSS/JavaScript
- pytest, pytest-django, and Ruff

## Working rules

- Reference functional requirement IDs in task descriptions and tests.
- Keep the application as a Django monolith unless an approved design change says otherwise.
- Do not add Node.js, Redis, message queues, or a separate SPA without approval.
- Never commit `.env`, credentials, customer phone numbers, or production data.
- Public views must never expose internal notes or unpublished records.
- Enforce permissions and validation on the server, not only in templates.
- Every model change requires a checked-in migration.
- Prefer small, reversible migrations; do not edit applied migrations.
- Add or update tests with every behavior change.

## Verification

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

## Documentation

- Environment setup: `docs/02-windows-dev-test-environment.md`
- Runtime deployment: `docs/03-windows-runtime-deployment.md`
- Functional baseline: `docs/05-detailed-functional-requirements.md`

