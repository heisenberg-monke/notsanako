# Repository Guidelines

## Project Structure & Modules

This repository contains a Next.js frontend and a FastAPI backend. Frontend pages live in `frontend/src/app`, reusable UI in `frontend/src/components`, and shared types and browser audio helpers in `frontend/src/types` and `frontend/src/utils`. The backend application is in `backend/app`; API routers are in `backend/app/routers`, and pytest tests are in `backend/tests`. Keep tests alongside the backend test suite and static public assets under `frontend/public`.

## Build, Test, and Development Commands

- Backend: from `backend`, run `./run.sh` to start the API (normally at `http://localhost:8000`). Run `pytest` there to execute the test suite.
- Frontend: from `frontend`, run `npm install` once, then `npm run dev` for local development, `npm run build` for a production build, and `npm start` to serve that build.
- `npm run lint` invokes the repository's configured lint script. Run commands from their respective directories so dependencies and configuration resolve correctly.

## Coding Style & Naming

Follow the surrounding code style. Frontend code uses TypeScript and React: components use PascalCase filenames and names, while utilities and hooks use camelCase. Use two-space indentation in frontend files. Backend code follows conventional Python style with four-space indentation, `snake_case` module/function names, and PascalCase classes. Keep API schemas, database models, and route behavior consistent with existing modules; avoid committing generated build output, virtual environments, databases, or credentials.

## Testing Guidelines

Backend tests use pytest and live in `backend/tests`; files follow `test_*.py` and test functions use `test_*`. Run `pytest` from `backend` after changing backend behavior. Add or update focused tests for changes to alignment, Indic-language rules, remediation, or full-loop behavior. No frontend test framework or coverage threshold is currently configured; validate frontend changes with the available build and lint commands.

## Commits & Pull Requests

Recent commits use short, informal summaries, but prefer clear imperative subjects such as `Fix audio upload handling`. Keep each commit focused. Pull requests should explain user-visible and API changes, link related issues when available, note configuration changes, and include screenshots for visual updates. Mention the commands used to validate the change and any test gaps.

## Configuration & Secrets

Copy `backend/.env.example` to `backend/.env` for local setup. Keep API keys and local configuration out of commits. The backend relies on configured speech and story-generation providers for those features; see the root README for setup details.
