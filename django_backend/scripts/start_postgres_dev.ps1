$ErrorActionPreference = "Stop"
$backend = Split-Path -Parent $PSScriptRoot
Set-Location $backend
if (-not (Test-Path (Join-Path $backend ".env.postgres") -PathType Leaf)) { throw "Missing .env.postgres. Create it from .env.postgres.example and enter credentials privately." }
$env:DJANGO_SETTINGS_MODULE = "config.settings"
$env:DJANGO_ENV_FILE = ".env.postgres"
$python = Join-Path $backend ".venv\Scripts\python.exe"
if (-not (Test-Path $python -PathType Leaf)) { throw "Project virtual environment Python was not found." }
& $python scripts\check_postgres_target.py
if ($LASTEXITCODE -ne 0) { throw "PostgreSQL preflight failed; backend was not started." }
Write-Host "Starting verified PostgreSQL development backend on 127.0.0.1:8000. Stop stale runserver processes on port 8000 first."
& $python manage.py runserver 127.0.0.1:8000 --noreload
