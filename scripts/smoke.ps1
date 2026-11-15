param(
    [string]$BackendUrl = "http://localhost:8000",
    [string]$FrontendUrl = "http://localhost:5173"
)
$ErrorActionPreference = "Stop"
$live = Invoke-RestMethod "$BackendUrl/health"
if ($live.status -ne "ok") { throw "Backend liveness failed" }
$ready = Invoke-RestMethod "$BackendUrl/health/ready"
if ($ready.status -ne "ready" -or $ready.checks.postgresql -ne "up" -or $ready.checks.redis -ne "up") {
    throw "Dependency readiness failed"
}
$page = Invoke-WebRequest "$FrontendUrl/health"
if ($page.Content -notmatch '<div id="root"></div>') { throw "Frontend entry point missing" }
$proxy = Invoke-RestMethod "$FrontendUrl/api/health/ready"
if ($proxy.status -ne "ready") { throw "Frontend-to-backend proxy failed" }
Write-Output "PASS: backend live, PostgreSQL and Redis ready, frontend served, frontend API proxy connected."
