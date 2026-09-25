# builds and checks the whole site on windows. run: powershell -file build.ps1
# steps that need a tool you do not have (node, gcc, perl) are skipped.

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

function step($name) { Write-Host "`n== $name" }
function have($cmd) { return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function run($exe, [string[]]$arguments) {
	& $exe @arguments
	if ($LASTEXITCODE -ne 0) { throw "$exe failed with exit code $LASTEXITCODE" }
}

$python = if (have 'python') { 'python' } else { 'py' }

step 'python tests'
run $python @('-X', 'utf8', '-m', 'unittest', 'discover', '-s', 'tests', '-t', '.', '-q')

if (have 'node') {
	step 'javascript tests'
	run 'node' @('tests/test_dates.js')
}

step 'build'
run $python @('-X', 'utf8', '-m', 'builder')

if (have 'node') {
	step 'link check'
	run 'node' @('tools/checklinks.js')
} else {
	step 'link check skipped (no node)'
}

if (have 'gcc') {
	step 'c timeline tool'
	run 'gcc' @('-std=c99', '-O2', '-Wall', '-Wextra', '-Werror', '-o', 'tools/timeline.exe', 'tools/timeline.c')
	run '.\tools\timeline.exe' @('--histogram')
} else {
	step 'c timeline tool skipped (no gcc)'
}

if (have 'perl') {
	step 'content statistics'
	run 'perl' @('tools/stats.pl')
} else {
	step 'content statistics skipped (no perl)'
}

Write-Host "`nall done. open site\index.html, or run: $python -m builder serve"
