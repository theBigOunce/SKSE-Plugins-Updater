# SKSE Plugins Updater

An SKSE compatibility scanner with reviewed Nexus downloads and interactive MO2 installation.

**Version 0.4.0.** Scan compatibility, refresh Nexus versions, inspect ZIP candidates, and queue exact Nexus files for download followed by normal MO2 installer prompts. File selection is explicitly reviewed; the tool does not choose the newest main file automatically.

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

Root Builder components are listed as candidates. The scanner does not pretend that a candidate file is a verified deployment. Scanning does not modify the game root or installed mods. Queued installation is performed by MO2 after the user starts the reviewed queue.

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

## Reviewed download and installation queue

1. Open **Review update queue** after scanning in MO2.
2. Select an existing mod and use **Open Nexus files** to review its runtime requirements.
3. Paste an exact file ID or a public Nexus URL containing file_id. **Look up file** retrieves that file's name/version through MO2's authenticated requestFileInfo bridge; no copied API credentials are needed.
4. Confirm that you reviewed the file for the displayed target runtime and add it. Repeat for other mods. File names and page versions do not establish compatibility; choose applicable FOMOD branches yourself.
5. Click **Download, then open MO2 installers / Resume**. MO2 downloads all queued files first, then opens one installer at a time. The existing mod name is suggested, but the user retains MO2's rename, merge, replace, cancel and FOMOD choices.

The updater does not extract, move, merge, overwrite or delete installed files itself. It calls organizer.installMod(archive, existing_name) and waits for its synchronous return before scheduling the next item. A canceled/failed installer pauses the queue; Resume retries that item, or remove it to skip. Pause/closing the window stops further handoffs; a currently open installer must be handled in MO2, and existing downloads may continue. No automatic rollback or backup is performed.

Download row indices are not trusted: completion must have a matching MO2 archive .meta sidecar (Skyrim SE, mod ID, file ID). Unrelated downloads are ignored, and identity is checked again before installation. This is an identity check, not a cryptographic archive-content verification. The queue pauses when the reviewed profile, game directory or runtime changes. If you want a different environment, remove queued entries, rescan and reopen the queue.

Nexus access/subscription restrictions still apply. If direct downloading is unavailable, download the chosen file through the Nexus website into MO2 and **Attach completed MO2 download** to its queued entry. The matching .meta sidecar is required. Failed/paused downloads stop the queue when MO2 can identify them; a 30-minute wait limit handles requests that produce no usable callback. Resolve/resume the download in MO2, or attach the finished archive.

The queue is kept in memory for the current tool session. Use **Rescan** after installations to refresh compatibility and Nexus state. 7z/RAR archives can be handed to MO2, although the tool's own binary archive inspector currently handles ZIP only.

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

Scanning remains read-only. User-started downloads and installations use MO2 services and its configured directories; MO2 also maintains its normal metadata/logs. Queue tests use mocked downloads/installers and synthetic archives; real authenticated downloads and installer/FOMOD behavior still need an in-MO2 check. Development validation does not install mods.

## Development checks

~~~powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
python -B -m unittest discover -s src/tests -v
~~~

Tests use synthetic PE files, database headers and mod folders. Qt tests require a matching offscreen platform and QT_QPA_PLATFORM=offscreen. No actual mod binaries are distributed.

Only this README and Python source/tests under src are intended for publication. Reference repos, private reports, credentials and development notes remain outside Git through the development checkout's local exclude allowlist.

## Next milestones

1. Validate authenticated downloads and cancel/merge/replace/FOMOD flows inside a disposable MO2 instance.
2. Add hash-bound author/decoder evidence for remaining legacy and V5 uncertainties.
3. Validate a safe Nexus file-list transport, add 7z/RAR inspection and evaluate FOMOD branches.
4. Add verified post-install comparison and optional persisted queue recovery. Installation decisions remain with the user in MO2.

## Primary references

- [SKSE 2.2.6 loader rules](https://github.com/ianpatt/skse64/blob/9398d04592a7eb9d754f2997701116df1022f1b4/skse64/PluginManager.cpp)
- [SKSE 2.0.20 legacy loading](https://github.com/ianpatt/skse64/blob/v2.0.20/skse64/PluginManager.cpp)
- [SKSE 2.3.1 loader and V5 fallback](https://github.com/ianpatt/skse64/blob/7ff865f4a27d6dc936ab5fd0533ff2d706c8f857/skse64/PluginManager.cpp)
- [CommonLibSSE-NG database header](https://github.com/CharmedBaryon/CommonLibSSE-NG/blob/main/include/REL/ID.h)
- [MO2 Python API](https://www.modorganizer.org/python-plugins-doc/autoapi/mobase/index.html)
- [MO2 2.5.2 download manager](https://github.com/ModOrganizer2/modorganizer/blob/v2.5.2/src/downloadmanager.cpp)
- [MO2 2.5.2 installer handoff](https://github.com/ModOrganizer2/modorganizer/blob/v2.5.2/src/organizerproxy.cpp)
- [MO2 Nexus bridge implementation](https://github.com/ModOrganizer2/modorganizer/blob/master/src/nexusinterface.cpp)

The scanner and UI are independently implemented; reference-repository code and binaries are not distributed here.
