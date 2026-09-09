# SKSE Plugins Updater

A read-only SKSE compatibility scanner and Nexus update-status tool for Mod Organizer 2.

**Version 0.2.0.** Runtime checks and Nexus version indicators are implemented. Automatic download selection, archive verification and installation remain disabled.

## Compatibility methods

The scanner reads each DLL's AMD64 PE exports and SKSEPlugin_Version structure without loading or executing it. Game and SKSE file-version resources are read separately. Results distinguish two questions:

- **Runtime matrix:** Does this DLL pass the known runtime-specific metadata checks?
- **Local prerequisites (row details):** Are the required Address Library and effective SKSE installation established in this environment?

An offline scan no longer turns a supported DLL amber just because MO2's live file mapping is unavailable. Its mapping limitation remains visible in the header/details and local-prerequisite result.

For **1.6.1170**, the evaluator follows SKSE 2.2.6's loader checks:

- Explicit runtime lists when runtime independence is not declared.
- Address Library and signature-scanning independence flags.
- Post-1.6.629 structure layouts or declared cross-layout/no-structure usage.
- Minimum SKSE requirements, evaluated against a verified local root runtime when available.
- Unknown flags or missing declarations produce Review.

The matching Address Library is inspected independently: encoding, embedded runtime, executable name, 64-bit pointer size, address count and basic payload bounds. Formats 1 and 2 are understood. This does not validate every relocation entry or prove that a plugin's own offsets/signatures are correct.

For **1.5.97**, SKSE 2.0.20 requires a Query entry point. Its absence is incompatible; its presence alone remains Review because determining the function's answer would require more evidence. AE metadata does not prove the legacy Query path.

For **1.7.99**, V5 capability is displayed but does not automatically turn green. SKSE 2.3.0 and 2.3.1 have different loader behavior; later rules include a build-timestamp fallback for older declarations. Timestamp heuristics alone are insufficient proof of the binary's database decoder. Full release-specific V5 validation remains pending. Unknown future runtimes are never inferred as supported.

CommonLib family/version generally cannot be reliably recovered from a statically linked DLL. Author evidence tied to an exact release/hash and a matching load observation can strengthen uncertain cases; filename labels and old unbound logs cannot. No plugin code is executed during scanning.

## Status meanings

| Status | Meaning |
| --- | --- |
| Supported* | Runtime-specific static metadata/structure checks pass. Inspect local prerequisites separately. |
| Incompatible | A known architecture, entry-point or runtime declaration mismatch was found. Local checks can also identify invalid/missing dependencies. |
| Review | Evidence is absent, unsupported or insufficient for this particular check. |
| Shadowed | Another provider wins the DLL path. |
| Helper | No SKSE entry point; possibly an auxiliary library. |

Green is not a guarantee of successful game loading, correct signatures/relocations, all transitive dependencies or save compatibility.

Root Builder components are listed as candidates. The scanner does not pretend that a candidate file is a verified deployment. The game root and mod installation are never modified.

## Nexus update indicator

An upward arrow marks a newer mod-page release, independently of DLL compatibility.

- On scan, read MO2's cached newest version and available check date.
- Cached results are labeled; unknown or unorderable versions stay Unknown.
- Select a row and click **Check selected on Nexus** to request the current page version through MO2's existing authenticated bridge.
- Refresh results stay in memory. No API keys are requested, copied or stored.
- Requests are limited to one selected mod at a time, time out after 30 seconds, and ignore stale callbacks.
- Failure leaves the cached information intact.
- Multiple DLL rows belonging to the same Nexus mod are updated together.

A newer page release may be for a different runtime or optional file. The indicator does **not** identify an installable update, select the newest main file, or authorize a download.

## MO2 and offline operation

Target: MO2 2.5.x, embedded Python 3.12 and Qt 6. The core scanner uses only the standard library; version-resource detection requires Windows.

When ready to test in a disposable MO2 instance, put the src/skse_updater folder under MO2's plugins directory and restart MO2. Open **SKSE Plugins Updater** from its tools menu. The plugin gets the game directory and selected profile directly from MO2.

Live MO2 resolves winning virtual paths; offline mode uses saved standard profile priority. Offline mode cannot see unsaved changes or every file-mapper plugin. No hardcoded personal paths are present.

From the repository root:

~~~powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
python -B -m skse_updater --mo2 'C:\ModOrganizer'
~~~

Optional arguments:

~~~text
--game PATH       Override game directory
--profile NAME    Override selected profile
--output PATH     Private JSON report destination outside scanned directories
~~~

Reports contain local paths and mod inventory; keep them private. No report is written unless requested. Report schema 2 adds separate environment evidence and update-status fields.

The application does not write to installed mods or change MO2 settings. MO2 itself may write normal logs/cache when its services are used. Live registration and authenticated Nexus refresh still need validation inside a disposable MO2 process; current integration coverage uses mock contracts and headless Qt tests.

## Development checks

~~~powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
python -B -m unittest discover -s src/tests -v
~~~

Tests use synthetic PE files, database headers and mod folders. Qt tests require a matching offscreen platform and QT_QPA_PLATFORM=offscreen. No actual mod binaries are distributed.

Only this README and Python source/tests under src are intended for publication. Reference repos, private reports, credentials and development notes remain outside Git through the development checkout's local exclude allowlist.

## Next milestones

1. Validate the tool and Nexus refresh inside a disposable MO2 instance.
2. Add exact-release evidence for legacy Query-only and V5-dependent plugins.
3. Discover and inspect compatible Nexus file candidates and FOMOD branches.
4. Implement backup, verified single-mod installation and restore before batch updates.

## Primary references

- [SKSE 2.2.6 loader rules](https://github.com/ianpatt/skse64/blob/9398d04592a7eb9d754f2997701116df1022f1b4/skse64/PluginManager.cpp)
- [SKSE 2.0.20 legacy loading](https://github.com/ianpatt/skse64/blob/v2.0.20/skse64/PluginManager.cpp)
- [SKSE 2.3.1 loader and V5 fallback](https://github.com/ianpatt/skse64/blob/7ff865f4a27d6dc936ab5fd0533ff2d706c8f857/skse64/PluginManager.cpp)
- [CommonLibSSE-NG database header](https://github.com/CharmedBaryon/CommonLibSSE-NG/blob/main/include/REL/ID.h)
- [MO2 Python API](https://www.modorganizer.org/python-plugins-doc/autoapi/mobase/index.html)
- [MO2 Nexus bridge implementation](https://github.com/ModOrganizer2/modorganizer/blob/master/src/nexusinterface.cpp)

The scanner and UI are independently implemented; reference-repository code and binaries are not distributed here.
