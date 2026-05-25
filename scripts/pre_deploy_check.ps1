Write-Host "=== Pre-Deployment Checks ===" -ForegroundColor Cyan
$Fail = $false

# 1. Check for print statements in app/ (ignoring comments and e2e/verify scripts)
$prints = Get-ChildItem -Path app -Recurse -Filter *.py | Where-Object { $_.Name -notmatch '^(e2e_|verify_|gemini_client)' } | Select-String 'print\(' | Where-Object { $_.Line -notmatch '^\s*#' }
if ($prints) {
    Write-Host "[FAIL] No print() statements" -ForegroundColor Red
    $prints | ForEach-Object { Write-Host "  $($_.Path):$($_.LineNumber): $($_.Line.Trim())" }
    $Fail = $true
} else {
    Write-Host "[OK] No print() statements" -ForegroundColor Green
}

# 2. Check for pdb imports
$pdbs = Get-ChildItem -Path app -Recurse -Filter *.py | Select-String 'import pdb'
if ($pdbs) {
    Write-Host "[FAIL] No pdb imports" -ForegroundColor Red
    $pdbs | ForEach-Object { Write-Host "  $($_.Path):$($_.LineNumber): $($_.Line.Trim())" }
    $Fail = $true
} else {
    Write-Host "[OK] No pdb imports" -ForegroundColor Green
}

# 3. Check for hardcoded secrets
$secrets = Get-ChildItem -Path app -Recurse -Filter *.py | Select-String "api_key\s*=\s*'"
if ($secrets) {
    Write-Host "[FAIL] No hardcoded secrets" -ForegroundColor Red
    $secrets | ForEach-Object { Write-Host "  $($_.Path):$($_.LineNumber): $($_.Line.Trim())" }
    $Fail = $true
} else {
    Write-Host "[OK] No hardcoded secrets" -ForegroundColor Green
}

# 4. Check .env not in git
$envInGit = git ls-files .env
if ($envInGit) {
    Write-Host "[FAIL] .env in git" -ForegroundColor Red
    $Fail = $true
} else {
    Write-Host "[OK] .env not in git" -ForegroundColor Green
}

# 5. Check pinned requirements
$unpinned = Get-Content requirements.txt | Select-String '^[a-zA-Z].*[^0-9]$' | Where-Object { $_ -notmatch '^#' }
if ($unpinned) {
    Write-Host "[FAIL] All requirements pinned" -ForegroundColor Red
    $unpinned | ForEach-Object { Write-Host "  $($_.Line)" }
    $Fail = $true
} else {
    Write-Host "[OK] All requirements pinned" -ForegroundColor Green
}

if (-not $Fail) {
    Write-Host "=== ALL CHECKS PASSED - Ready to deploy ===" -ForegroundColor Green
} else {
    Write-Host "=== CHECKS FAILED - Fix before deploying ===" -ForegroundColor Red
    exit 1
}
