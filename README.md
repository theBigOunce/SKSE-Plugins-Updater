# SKSE Plugins Updater

A read-only SKSE DLL inventory and compatibility tool for Mod Organizer 2.

**Status: scanner preview (0.1.0).** Downloads, archive selection, backups and mod installation are not implemented. The update button is intentionally disabled.

## Features

- MO2 tool with a single Qt window, runtime matrix, filtering, progress and evidence details.
- Obtains the game directory and active profile from MO2; no hardcoded installation paths.
- Enumerates active mod DLLs, helper DLLs, unmanaged Data and Overwrite.
- Uses MO2's virtual path resolver to identify winning files when running inside MO2.
- Offline command-line inventory for standard MO2 layouts; explicitly marks its mapping as provisional.
- Reads game and SKSE version resources without executing scanned binaries.
- Reads AMD64 PE exports and schema-1 SKSE declarations directly from bytes.
- Reports Address Library file presence and root-managed SKSE candidates.
- Keeps mod release strings, DLL declaration versions and runtime compatibility separate.
- Optional private JSON report from the command line.

## Compatibility meanings

| Status | Meaning |
| --- | --- |
| Supported* | Exact runtime appears in the DLL declaration and initial metadata checks pass. Other dependencies, successful loading and save compatibility are not established. |
| Incompatible | A known architecture/runtime mismatch or missing declared runtime database was found. |
| Review | Evidence is incomplete, legacy, unsupported or requires more validation. |
| Shadowed | Another provider wins this DLL path. |
| Helper | No SKSE entry point; the DLL may be an auxiliary library. |

Current policy targets are 1.5.97, 1.6.1170 and 1.7.99. Unknown runtimes remain Review. Runtime-independence flags do not automatically produce green results. Full Address Library encoding/ABI validation and 1.7.99 V5 rules are pending. CommonLib family/version is not inferred from a filename.

Root Builder components are listed as candidates. Their effective mapping and SKSE/game agreement are not yet verified. Offline results cannot account for live file-mapper plugins, unsaved changes or all unusual MO2 layouts.

## Requirements and installation

Target: MO2 2.5.x with its Python 3.12 and Qt 6 plugin support. Core scanning uses only Python's standard library; Windows version-resource detection requires Windows.

When ready to test in an MO2 installation, place the src/skse_updater folder under MO2's plugins directory and restart MO2. Launch **SKSE Plugins Updater** from the tools menu. Do not install the folder as a normal Data mod.

The plugin does not save settings, contact Nexus, download files or modify mods. MO2 itself can write its normal logs/settings when run. Live integration has not yet been tested inside an MO2 process; use a disposable instance for that validation.

## Offline scan

From the repository root in PowerShell:

~~~powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
python -B -m skse_updater --mo2 'C:\ModOrganizer'
~~~

The selected profile and game path are read from ModOrganizer.ini. Optional arguments:

~~~text
--game PATH       Override the game directory
--profile NAME    Override the selected profile
--output PATH     Write a private JSON report (contains local paths/mod inventory)
~~~

Report output must be outside the scanned installation and mod directories. No report is written unless requested. Keep reports and credentials out of Git.

## Development checks

~~~powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
python -B -m unittest discover -s src/tests -v
~~~

Tests use generated PE bytes and temporary synthetic mod folders. No actual mod binaries are included. UI tests, when Qt is available, can run with QT_QPA_PLATFORM=offscreen and a matching Qt offscreen platform plugin.

Only README.md and Python source/tests under src are intended for publication. The development checkout uses a local Git exclude allowlist; local reference repositories, environment reports and planning notes are not tracked.

## Next milestones

1. Validate live MO2 origin resolution and profile changes in a disposable instance.
2. Validate runtime-specific SKSE and Address Library rules with matching fixtures.
3. Use MO2's Nexus bridge for candidate metadata through its existing login.
4. Inspect candidate archives and present exact file choices for review.
5. Add backups, verified single-mod installation and restoration before batch updates.

No separate Nexus credentials are required by this preview. MO2 exposes authenticated metadata/download interfaces; their live behavior will be validated before enabling updates.

## Technical references

- [MO2 Python API](https://www.modorganizer.org/python-plugins-doc/autoapi/mobase/index.html)
- [SKSE metadata declarations](https://github.com/ianpatt/skse64/blob/master/skse64/PluginAPI.h)
- [SKSE loader compatibility checks](https://github.com/ianpatt/skse64/blob/master/skse64/PluginManager.cpp)

The scanner and UI are independently implemented. No code or binaries from the local reference repositories are distributed here.
