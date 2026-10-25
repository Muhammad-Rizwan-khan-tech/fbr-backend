# Cloud connectivity update

This archive contains the backend folder only. Extract its contents into the existing repository's `backend/` directory. Do not replace the entire repository or its frontend.

## Changes
- Install Psycopg 3 binary and retain Psycopg 2 compatibility.
- Include Alembic in backend dependencies.
- Normalize plain PostgreSQL URLs to the installed Psycopg 3 driver; accept legacy postgres URLs and preserve explicit driver URLs.
- Reject incomplete URLs without printing credentials.
- Use the same resolved database URL for API and Alembic.
- Add PostgreSQL connection timeout and pool recycling.

## Render
Build command from repository root: `pip install -r backend/requirements.txt`
Start command: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
If your existing build uses root requirements.txt, ensure that it includes `-r backend/requirements.txt` or the same PostgreSQL dependencies.
Keep DATABASE_URL set to the existing database's complete Internal Database URL. Never place real credentials in this archive or source control.

## UI connectivity
The frontend is not included. Set its API origin to `https://fbr-backend.onrender.com` and use the existing `/api/v1` route prefix exactly once.
Set backend `CORS_ORIGINS` to a comma-separated list of actual frontend origins, including scheme and port where needed, without URL paths or trailing slash. Retain the required desktop and localhost origins for your app. Do not use wildcard CORS with credentials.
Rebuild the UI after changing build-time API settings. Verify `/health`, the browser login request and an authenticated request from the actual UI origin.

This package does not change cloud settings, deploy the service, create a database or include UI end-to-end verification. Existing production environment validation remains enabled.
