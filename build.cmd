@echo off
rem builds and checks the whole site from the plain windows command prompt.
rem double-click it, or run: build.cmd
rem steps that need a tool you do not have (node, gcc, perl) are skipped.

setlocal enabledelayedexpansion
cd /d "%~dp0"

rem use the first python that really runs (the "python" store shortcut can
rem exist but do nothing), and is 3.9 or newer
set "py="
for %%p in (py python python3) do (
	if not defined py (
		%%p -c "import sys; sys.exit(sys.version_info < (3, 9))" >nul 2>&1 && set "py=%%p"
	)
)
if not defined py (
	echo python 3.9 or newer is needed
	exit /b 1
)

call :step "python tests"
%py% -X utf8 -m unittest discover -s tests -t . -q || goto :failed

where node >nul 2>&1
if !errorlevel! == 0 (
	call :step "javascript tests"
	node tests\test_dates.js || goto :failed
)

call :step "build"
%py% -X utf8 -m builder || goto :failed

where node >nul 2>&1
if !errorlevel! == 0 (
	call :step "link check"
	node tools\checklinks.js || goto :failed
) else (
	call :step "link check skipped (no node)"
)

where gcc >nul 2>&1
if !errorlevel! == 0 (
	call :step "c timeline tool"
	gcc -std=c99 -O2 -Wall -Wextra -Werror -o tools\timeline.exe tools\timeline.c || goto :failed
	tools\timeline.exe --histogram
) else (
	call :step "c timeline tool skipped (no gcc)"
)

where perl >nul 2>&1
if !errorlevel! == 0 (
	call :step "content statistics"
	perl tools\stats.pl
) else (
	call :step "content statistics skipped (no perl)"
)

echo.
echo all done. open site\index.html, or run: %py% -m builder serve
exit /b 0

:step
echo.
echo == %~1
exit /b 0

:failed
echo.
echo the build stopped because a step failed.
exit /b 1
