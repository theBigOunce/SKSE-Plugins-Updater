# SKSE Plugins Updater

A read-only SKSE compatibility scanner and Nexus update-status tool for Mod Organizer 2.

**Version 0.3.0.** Automatic Nexus refresh, linked mod names, release-specific runtime checks and read-only ZIP candidate inspection are implemented. Automatic download selection and installation remain disabled.

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
- Unknown flags produce Review; missing required version metadata is incompatible.

The matching Address Library is inspected independently: encoding, embedded runtime, executable name, 64-bit pointer size, address count and basic payload bounds. Formats 1 and 2 are understood. This does not validate every relocation entry or prove that a plugin's own offsets/signatures are correct.

For **1.5.97**, SKSE 2.0.20 requires a Query entry point. Its absence is incompatible; its presence alone remains Review because determining the function's answer would require more evidence. AE metadata does not prove the legacy Query path.

For **1.7.99**, the matrix models **SKSE 2.3.1** specifically. An Address Library DLL without the V5 capability flag, whose COFF timestamp is in [520128000, 1748217600) (before May 26, 2025), loses runtime independence under that loader. It is incompatible unless it explicitly lists 1.7.99. A V5 declaration, explicit runtime listing, or signature-only independence can pass the applicable metadata checks. Structure checks still apply when runtime independence is used.

Without V5 or an exact runtime declaration, timestamps outside that interval remain Review: reproducible builds can use non-date timestamps, and a recent timestamp does not prove decoder support. These checks reproduce loader decisions, not CommonLib version detection. SKSE 2.3.0 behaves differently; unknown future runtimes remain Review.

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

- On launch, reopening the tool, and **Rescan**, scan the active profile and refresh every identified Nexus mod through MO2.
- Cached results are labeled; unknown or unorderable versions stay Unknown.
- Select a row and click **Check selected on Nexus** to request the current page version through MO2's existing authenticated bridge.
- Refresh results stay in memory. No API keys are requested, copied or stored.
- Automatic refresh deduplicates mod IDs, requests one mod at a time with a one-second interval, times out after 30 seconds, and stops after three consecutive failures. Rescan/close discard queued work and stale callbacks.
- Failure leaves cached information intact with an explicit failed/not-checked label. Rows update without resetting selection.
- Multiple DLL rows belonging to the same Nexus mod are updated together.

A newer page release may be for a different runtime or optional file. The indicator does **not** identify an installable update, select the newest main file, or authorize a download.

Double-click an underlined mod name to open its public Nexus URL from meta.ini. If that field is absent/invalid, a known Skyrim SE domain and mod ID provide the link. Non-Nexus URLs and credentials/query parameters are not opened.

## Download candidate inspection

**Inspect downloaded ZIP** reads DLL variants directly inside a user-selected archive, shows SHA-256 and runtime evidence for each, and identifies a standard FOMOD configuration. It never extracts, executes or installs files. Size/count/compression limits bound DLL inspection. ZIP only; 7z/RAR and FOMOD condition evaluation are pending. A green DLL does not prove the archive's origin, dependencies, destination or selected FOMOD branch.

Automated Nexus file-list discovery is deferred: MO2 2.5.2's NexusBridge::nxmFilesAvailable appends pointers to stack-local ModRepositoryFileInfo objects before emitting the list. We avoid that unsafe API. A corrected bridge or a separate authenticated file-list transport must be validated before implementing candidate discovery. Existing mod-description refresh does not use this interface.

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

The application does not write to installed mods or change MO2 settings. MO2 itself may write normal logs/cache when its services are used. Automatic refresh integration is covered with mock MO2 contracts and headless Qt tests; real authenticated batch behavior still needs an in-MO2 check.

## Development checks

~~~powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
python -B -m unittest discover -s src/tests -v
~~~

Tests use synthetic PE files, database headers and mod folders. Qt tests require a matching offscreen platform and QT_QPA_PLATFORM=offscreen. No actual mod binaries are distributed.

Only this README and Python source/tests under src are intended for publication. Reference repos, private reports, credentials and development notes remain outside Git through the development checkout's local exclude allowlist.

## Next milestones

1. Validate the tool and Nexus refresh inside a disposable MO2 instance.
2. Add hash-bound author/decoder evidence for remaining legacy and V5 uncertainties.
3. Validate a safe Nexus file-list transport, add 7z/RAR inspection and evaluate FOMOD branches.
4. Implement backup, verified single-mod installation and restore before batch updates.

## Primary references

- [SKSE 2.2.6 loader rules](https://github.com/ianpatt/skse64/blob/9398d04592a7eb9d754f2997701116df1022f1b4/skse64/PluginManager.cpp)
- [SKSE 2.0.20 legacy loading](https://github.com/ianpatt/skse64/blob/v2.0.20/skse64/PluginManager.cpp)
- [SKSE 2.3.1 loader and V5 fallback](https://github.com/ianpatt/skse64/blob/7ff865f4a27d6dc936ab5fd0533ff2d706c8f857/skse64/PluginManager.cpp)
- [CommonLibSSE-NG database header](https://github.com/CharmedBaryon/CommonLibSSE-NG/blob/main/include/REL/ID.h)
- [MO2 Python API](https://www.modorganizer.org/python-plugins-doc/autoapi/mobase/index.html)
- [MO2 Nexus bridge implementation](https://github.com/ModOrganizer2/modorganizer/blob/master/src/nexusinterface.cpp)

The scanner and UI are independently implemented; reference-repository code and binaries are not distributed here.
