<#
.SYNOPSIS
    Almentor Task Management API - PowerShell Developer Script
    Native Windows alternative to the Makefile.

.DESCRIPTION
    Run any command by passing its name as an argument:
        .\scripts\dev.ps1 help
        .\scripts\dev.ps1 dev
        .\scripts\dev.ps1 test
        .\scripts\dev.ps1 token myusername

.NOTES
    Requires: UV (https://docs.astral.sh/uv/)
#>

param(
    [Parameter(Position=0)][string]$Command = "help",
    [Parameter(Position=1)][string]$Arg     = ""
)

# ---------------------------------------------------------------------------
# Coloured output helpers
# ---------------------------------------------------------------------------
$ESC = [char]27
function Write-Green  ($t) { Write-Host "${ESC}[0;32m${t}${ESC}[0m" }
function Write-Yellow ($t) { Write-Host "${ESC}[0;33m${t}${ESC}[0m" }
function Write-Cyan   ($t) { Write-Host "${ESC}[0;36m${t}${ESC}[0m" }
function Write-Red    ($t) { Write-Host "${ESC}[0;31m${t}${ESC}[0m" }
function Write-Bold   ($t) { Write-Host "${ESC}[1m${t}${ESC}[0m" }
function Write-Dim    ($t) { Write-Host "${ESC}[2m${t}${ESC}[0m" }
function Write-Sep          { Write-Host "${ESC}[1m$('-' * 48)${ESC}[0m" }

function Write-Row ($cmd, $desc) {
    Write-Host ("  " + "${ESC}[0;32m" + $cmd.PadRight(30) + "${ESC}[0m" + $desc)
}

# ---------------------------------------------------------------------------
# Always run from the project root
# ---------------------------------------------------------------------------
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

# ---------------------------------------------------------------------------
# Command dispatch
# ---------------------------------------------------------------------------
switch ($Command.ToLower()) {

    # -----------------------------------------------------------------------
    "help" {
        Write-Host ""
        Write-Sep
        Write-Bold  "  Almentor Task Management API - Dev Commands"
        Write-Sep
        Write-Host ""
        Write-Cyan  "  SETUP"
        Write-Row   "dev.ps1 install"           "Install all dependencies via UV"
        Write-Row   "dev.ps1 update"            "Update dependencies to latest allowed versions"
        Write-Host ""
        Write-Cyan  "  DEVELOPMENT"
        Write-Row   "dev.ps1 dev"               "Start the dev server at http://127.0.0.1:8000"
        Write-Row   "dev.ps1 shell"             "Open the Django interactive Python shell"
        Write-Row   "dev.ps1 superuser"         "Create a new superuser account"
        Write-Row   "dev.ps1 token [user]"      "Fetch a fresh JWT access token for [user]"
        Write-Host ""
        Write-Cyan  "  DATABASE"
        Write-Row   "dev.ps1 migrate"           "Apply all pending database migrations"
        Write-Row   "dev.ps1 migrations"        "Generate new migration files"
        Write-Row   "dev.ps1 check-migrations"  "Warn if any model changes lack a migration"
        Write-Host ""
        Write-Cyan  "  TESTING"
        Write-Row   "dev.ps1 test"              "Run ALL tests (unit + integration) vs PostgreSQL"
        Write-Row   "dev.ps1 test-unit"         "Run unit tests only (core / projects / tasks)"
        Write-Row   "dev.ps1 test-integration"  "Run integration tests only"
        Write-Row   "dev.ps1 test-fast"         "Unit tests with SQLite - no Postgres needed"
        Write-Host ""
        Write-Cyan  "  CLEANUP"
        Write-Row   "dev.ps1 clean"             "Remove all __pycache__ dirs and .pyc files"
        Write-Host ""
        Write-Dim   "  Git Bash / WSL users: use 'make [command]' instead"
        Write-Host ""
    }

    # -----------------------------------------------------------------------
    "install" {
        Write-Yellow "Installing dependencies via UV..."
        uv sync
        Write-Green  "OK Dependencies installed."
    }

    "update" {
        Write-Yellow "Updating dependencies..."
        uv sync --upgrade
        Write-Green  "OK Dependencies updated."
    }

    # -----------------------------------------------------------------------
    "dev" {
        Write-Green "Starting dev server at http://127.0.0.1:8000"
        Write-Green "Press Ctrl+C to stop."
        uv run python manage.py runserver
    }

    "shell" {
        Write-Cyan "Opening Django shell..."
        uv run python manage.py shell
    }

    "superuser" {
        Write-Cyan "Creating superuser..."
        uv run python manage.py createsuperuser
    }

    "token" {
        if (-not $Arg) {
            Write-Red "Usage: .\scripts\dev.ps1 token [username]"
            exit 1
        }
        $username = $Arg
        Write-Cyan "Fetching JWT token for user '$username'..."
        Write-Host "(The dev server must be running at http://127.0.0.1:8000)"

        $secPwd   = Read-Host -Prompt "Password" -AsSecureString
        $plainPwd = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
                        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secPwd))

        $body = @{ username = $username; password = $plainPwd } | ConvertTo-Json
        try {
            $resp = Invoke-RestMethod -Method POST `
                        -Uri "http://127.0.0.1:8000/api/token/" `
                        -Body $body `
                        -ContentType "application/json"
            Write-Host ""
            Write-Green "Access Token (copy and use as: Bearer [token]):"
            Write-Host  $resp.access
            Write-Host ""
            Write-Yellow "Refresh Token:"
            Write-Host   $resp.refresh
            Write-Host ""
        }
        catch {
            Write-Red "Failed: $($_.Exception.Message)"
            Write-Red "Make sure the dev server is running and credentials are correct."
        }
    }

    # -----------------------------------------------------------------------
    "migrate" {
        Write-Yellow "Applying database migrations..."
        uv run python manage.py migrate
        Write-Green  "OK Migrations applied."
    }

    "migrations" {
        Write-Yellow "Generating migration files..."
        uv run python manage.py makemigrations
        Write-Green  "OK Done. Review the new files before committing."
    }

    "check-migrations" {
        Write-Cyan "Checking for missing migrations..."
        uv run python manage.py makemigrations --check --dry-run
        if ($LASTEXITCODE -eq 0) {
            Write-Green "OK No missing migrations."
        }
        else {
            Write-Red "WARNING Missing migrations detected. Run: .\scripts\dev.ps1 migrations"
        }
    }

    # -----------------------------------------------------------------------
    "test" {
        Write-Host ""
        Write-Cyan "Running ALL tests (unit + integration) against PostgreSQL..."
        Write-Host ""
        uv run python manage.py test --verbosity=2
        if ($LASTEXITCODE -eq 0) { Write-Green  "`nOK All tests passed." }
        else                      { Write-Red    "`nFAIL Some tests failed."; exit 1 }
    }

    "test-unit" {
        Write-Host ""
        Write-Cyan "Running unit tests (core / projects / tasks)..."
        Write-Host ""
        uv run python manage.py test core projects tasks --verbosity=2
        if ($LASTEXITCODE -eq 0) { Write-Green  "`nOK Unit tests passed." }
        else                      { Write-Red    "`nFAIL Some tests failed."; exit 1 }
    }

    "test-integration" {
        Write-Host ""
        Write-Cyan "Running integration tests against PostgreSQL..."
        Write-Host ""
        uv run python manage.py test integration_tests --verbosity=2
        if ($LASTEXITCODE -eq 0) { Write-Green  "`nOK Integration tests passed." }
        else                      { Write-Red    "`nFAIL Some tests failed."; exit 1 }
    }

    "test-fast" {
        Write-Host ""
        Write-Cyan "Running unit tests with SQLite (fastest - no Postgres needed)..."
        Write-Host ""
        uv run python manage.py test core projects tasks `
            --settings=core.test_settings `
            --verbosity=2
        if ($LASTEXITCODE -eq 0) { Write-Green  "`nOK Fast tests passed." }
        else                      { Write-Red    "`nFAIL Some tests failed."; exit 1 }
    }

    # -----------------------------------------------------------------------
    "clean" {
        Write-Yellow "Removing __pycache__ and .pyc files..."

        $cleanScript = @'
import shutil, pathlib
root  = pathlib.Path(".")
count = 0
for p in list(root.rglob("__pycache__")):
    if ".venv" not in str(p):
        shutil.rmtree(str(p), ignore_errors=True)
        count += 1
for p in list(root.rglob("*.pyc")):
    if ".venv" not in str(p):
        p.unlink(missing_ok=True)
print(f"Removed {count} cache directories.")
'@

        $cleanScript | uv run python
        Write-Green "OK Cache cleared."
    }

    # -----------------------------------------------------------------------
    default {
        Write-Red "Unknown command: '$Command'"
        Write-Host "Run  .\scripts\dev.ps1 help  to see all available commands."
        exit 1
    }
}
