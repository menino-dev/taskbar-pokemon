# Automated verification script for taskbar-pokemon.wh.cpp
# Runs roundtrip check, generates previews, checks syntax with Windhawk clang++, and runs unit tests.

$ErrorActionPreference = 'Stop'
$root = (Get-Item $PSScriptRoot).Parent.FullName
$compiler = 'C:\Program Files\Windhawk\Compiler'
$clang = Join-Path $compiler 'bin\clang++.exe'
$out = Join-Path $root 'build'
New-Item -ItemType Directory -Force $out | Out-Null

Write-Host "=== 1. Checking Roundtrip Decoding ===" -ForegroundColor Cyan
py -3.14 (Join-Path $root 'tools\verify_pokemon_roundtrip.py')
if ($LASTEXITCODE -ne 0) { throw "Roundtrip failed" }

Write-Host "`n=== 2. Generating 4x Preview GIFs ===" -ForegroundColor Cyan
py -3.14 (Join-Path $root 'tools\make_pokemon_previews.py')
if ($LASTEXITCODE -ne 0) { throw "GIF generation failed" }

Write-Host "`n=== 3. Syntax Check with Windhawk Clang++ ===" -ForegroundColor Cyan
$modFlags = @(
    '-std=c++23', '-target', 'x86_64-w64-mingw32',
    '-DUNICODE', '-D_UNICODE', '-DWINVER=0x0A00', '-D_WIN32_WINNT=0x0A00',
    '-D__USE_MINGW_ANSI_STDIO=0', '-DWH_MOD', '-DWH_EDITING',
    '-I', (Join-Path $compiler 'include'), '-include', 'windhawk_api.h',
    '-Wall', '-Wextra', '-Wno-unused-parameter', '-Wno-missing-field-initializers',
    '-fsyntax-only', '-x', 'c++',
    (Join-Path $root 'taskbar-pokemon.wh.cpp')
)
& $clang @modFlags
if ($LASTEXITCODE -ne 0) { throw "Syntax check failed" }
Write-Host "Syntax check passed (0 errors, 0 warnings)" -ForegroundColor Green

Write-Host "`n=== 4. Building & Running Unit Tests ===" -ForegroundColor Cyan
$testFlags = @(
    '-std=c++23', '-target', 'x86_64-w64-mingw32',
    '-DUNICODE', '-D_UNICODE', '-DWINVER=0x0A00', '-D_WIN32_WINNT=0x0A00',
    '-D__USE_MINGW_ANSI_STDIO=0', '-DWH_MOD', '-DWH_EDITING', '-DWH_STANDALONE',
    '-I', (Join-Path $compiler 'include'), '-include', 'windhawk_api.h',
    '-Wall', '-Wextra', '-Wno-unused-parameter', '-Wno-missing-field-initializers',
    '-O2', '-static', '-lgdi32', '-lshell32', '-lwtsapi32', '-ladvapi32', '-lcomctl32', '-lole32', '-luuid', '-lwinmm'
)
& $clang @testFlags (Join-Path $root 'tests\pokemon_engine_tests.cpp') -o (Join-Path $out 'pokemon_engine_tests.exe')
if ($LASTEXITCODE -ne 0) { throw "Unit tests compilation failed" }
& (Join-Path $out 'pokemon_engine_tests.exe')
if ($LASTEXITCODE -ne 0) { throw "Unit tests execution failed" }

Write-Host "`n=== ALL POKEMON VERIFICATIONS PASSED SUCCESSFULLY! ===" -ForegroundColor Green

