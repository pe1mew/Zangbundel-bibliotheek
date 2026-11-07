# Changelog

All notable changes to this library are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/). The library follows Zangbundel library format 1.1 (`format_version` in `zangbundel.json`; 1.0 until release 2026.10.0). Releases are tagged `v<version>` with calendar versions (`year.month.sequence`) and published as `.zbl` archives; see `releases.json`.

## [Unreleased]

### Changed
- `validate.py` and `release.py` follow song format v0.23, as the owner approved on 2026-11-06 (`design/proposals/2026-11-06-shared-test-libraries.md` in the app repository, 3.7 and O-11 f):
  - S005: a file already skipped for another song error is not a song of the library and takes no part in the duplicate-id check. The good file of a pair now imports, where before neither did.
  - A003: `release.py verify` takes the ratio limit (20 times) against the size of the archive file, not against the compressed sizes the central directory declares.
- `scripts/conformance.py` also reads the corpus's `packages/` vectors, the library manager's 56 shared test libraries. It checks each one's `format_1_1` verdict and codes, as an app that reads only format 1.1 sees the package.
  - On the app's corpus at `f658f51`, 113 of 114 vectors agree. The exception is `song-two-files`, whose `expected.json` still lists the old S005 reading (`A102, S004, S005, SL101`); under v0.23 the tools report `A102, S004`, and the old tools agree with all 114.
  - The pin (`CONFORMANCE_REF`) stayed at `dcc174d`, where all 58 vectors agree, until that expectation was corrected: in the library manager on 2026-11-07 (`cb5fd82`) and in the app's copy (`71f0477`).
  - The pin then moved to `71f0477`, where all 114 vectors agree.
  - The published 2026.11.0 archive still passes `verify --strict`.

### Added
- `scripts/conformance.py` runs the app repository's conformance corpus against `validate.py` and `release.py`: songs, setlists, library files and archives. The validation workflow runs it on every push, with the corpus fetched at a pinned commit of the app repository (`CONFORMANCE_REF`). All 58 vectors agree, including the new library-file vectors. With one expectation deliberately changed, the script reports the difference and exits with an error. README section "The contract with the app". The first run on GitHub passed with the pin on app commit `41eb28c` (46 vectors, no library vectors yet). The pin then moved to `dcc174d`, which adds the twelve library-file vectors; all 58 agree locally.

- `release-menu.py`: a step-by-step menu for validating, staging, committing, tagging, pushing and pulling, in Dutch, English and German, with explanations that can be shown or hidden ([#3](https://github.com/pe1mew/Zangbundel-bibliotheek/issues/3), Pepe's proposal 10). It is adapted from Pepe's CC0 menu for his own library:
  - Dutch is added.
  - Only the library's own files are staged; other changes are listed and left alone.
  - A commit is refused while library changes are unstaged, so the check matches what is committed.
  - Before a tag is set, the commit is built and verified exactly as the release workflow will do it.
  - Newer commits on GitHub are offered as a pull instead of ending the menu, and pulling is fast-forward only.
  - Unexpected errors keep a double-clicked window open.

  Tested in a scratch clone with scripted answers in all three languages: staging left a stray file alone, the pre-flight build passed, and the unstaged-change refusal and the error handler worked. Every commit, tag and push was shown but declined.
- README:
  - Release menu: a "Without git commands: the release menu" section with the step table.
  - GitHub Desktop: how to use it, so that only the validator needs the terminal (Pepe's proposal 10, part A).
  - The private-library instructions name the menu as the easiest way to release.
  - Language codes: what a BCP 47 language tag is, how to find one in the official IANA language subtag registry, and a table of the twelve languages in `songs/` with their folder, tag and name ([#4](https://github.com/pe1mew/Zangbundel-bibliotheek/issues/4), Pepe's proposal 11). `contributing.md` points to it.

### Changed
- `license.md`: the code licence covers `release-menu.py`, with the menu's origin in Pepe's public-domain menu.

### Fixed
- `release.py verify` now validates the songs in a ZIP with a single wrapping folder (song-format 12.5). It used to accept such a ZIP after the A102 warning without looking inside it. Conformance vector `snapshot-top-directory` found this.

### Removed
- *Nothing.*

## [2026.11.0] - 2026-11-04

Fourth release: 238 songs from the Drasva songbook, bringing the library to 247 songs in twelve languages, a README route for your own songs as a ZIP file, and a release workflow that no longer breaks on committed build output.

### Added
- 238 songs from the Drasva songbook (scouting, campfire and children's songs): 65 in the public domain, 134 whose rights holder could not be traced and 39 translations of free songs by an unknown translator. The last two groups are marked `proprietary` with "Rechthebbende onbekend", and their `#` lines record the sources searched and the oldest print found. Songs with a known author still under copyright are not included. `zangbundel.json` gains the languages `en`, `de`, `fr`, `li`, `af`, `he-Latn`, `it`, `mi`, `nds-NL` and `srn`, and the tags `geestelijk`, `kerst`, `scouting` and `welpen`.
- README section "Your own songs the easy way: a ZIP file" ([#1](https://github.com/pe1mew/Zangbundel-bibliotheek/issues/1), Pepe's proposal 8, step 1). It describes the route with no GitHub, git or Python: a folder with `zangbundel.json` (a template to fill in), `LICENSE` and `songs/`, its contents zipped with Explorer, then "import from file" in the app, which checks every song. It warns against `Compress-Archive` of Windows PowerShell 5.1, and against `.cho.txt` names. Tested with ZIPs made by Python, by Explorer's "Send to → Compressed (zipped) folder", by `Compress-Archive` (refused, as the app will) and without a licence file (refused, L007). It also lists the two planned steps: a library builder in the browser without uploads, and signed archives (song-format Q12).
- Validation workflow: a warning when build output (`dist/`, `*.zbl`) is committed to git.
- README, "Your own private library": a `.gitignore` row (keep it; how to remove committed build output), and what to do when no release appears (the run's summary page names the cause; delete and re-push the tag).

### Changed
- Workflows use `actions/checkout@v7` and `actions/setup-python@v7`, which run on Node.js 24, so GitHub no longer warns about Node.js 20.
- `.gitignore` also ignores `*.zbl` anywhere in the repository.
- Release notes say to add the library by the URL of its `releases.json` instead of its repository URL (the app imports release archives only).
- README: the library is described as mostly Dutch with songs in other languages, and the repository layout lists the new language folders.

### Fixed
- A committed `dist/` folder broke the release with only "Process completed with exit code 2" on the run's summary page ([#2](https://github.com/pe1mew/Zangbundel-bibliotheek/issues/2), Pepe's proposal 7):
  - **7B:** the old archive in `dist/` made `dist/*.zbl` match two files, and `release.py verify` stopped on "unrecognized arguments". The release workflow now builds in a fresh folder outside the checkout (`$RUNNER_TEMP`) and names every archive exactly, so committed build output no longer affects it. `release.py build` warns when build output is committed.
  - **7A:** `release.py` reports errors as GitHub Actions annotations, which the summary page shows: wrong arguments (with a hint about a stray archive), build errors, and each verification finding with file and line. A final workflow step adds a summary with the common causes when a release fails. Outside GitHub Actions the output is unchanged.

  The archive is unchanged: rebuilding tag `v2026.10.2` with the new tool gives the published SHA-256 `f63559de…b47f`.
- `release.py verify` checks entry names as stored in the ZIP. On Windows, Python turns backslashes into slashes when reading, which hid ZIPs that the app refuses, such as those made by `Compress-Archive` of Windows PowerShell 5.1.

## [2026.10.2] - 2026-10-26

Third release: the app's development builds can import the library.

### Added
- README section "Your own private library". It explains how to copy this repository into a private one (only `main`, with this repository kept as `upstream`) and what to change: a new id, no `release_index` or `homepage`, and deleting `releases.json`, because the release tool refuses another library's index. It covers how to build a release on GitHub or locally, and how to get the `.zbl` file onto the leader's phone with "import from file", since the app cannot read private repositories. Rehearsed on a scratch clone: the validator accepts the result.

### Changed
- `zangbundel.json`: `min_app_version` lowered from `1.0.0` to `0.1.0`. The library uses nothing newer than the first app builds, and the app (version 0.1.0 during development) refused it with L005. The song-format specification asks to keep this value as low as the content allows (section 4.3).
- README:
  - It now says format 1.1 instead of 1.0.
  - The repository layout lists `songs/la/`.
  - The app is added by the URL of `releases.json` instead of the git repository URL, since the app imports release archives only (app architecture A-11).

### Fixed
- *Nothing.*

### Removed
- *Nothing.*

## [2026.10.1] - 2026-10-25

Second release: setlists (format 1.1) and a demonstration song.

### Added
- `songs/la/lorem-ipsum.cho`, "Lorem Ipsum!", a demonstration song written for the Zangbundel project in 2026 and licensed CC0-1.0. It sets lorem-ipsum words to the tune of Vader Jacob and has four verses with the refrain "Lorem ipsum, lorem ipsum!" between them, plus chords in F. Every metadata field of the format is filled in except `variant-group`, which needs a second song (W011). It validates with 22 canonical lines.
- `setlists/demo-setlist.zbs`, "Demo setlist", with only that song.
- `zangbundel.json`: `la` added to `languages`; tag label `demo` (Demo).
- Setlists (song-format specification section 13, format 1.1): `setlists/voorbeeld-avond.zbs`, an example evening with the eight songs and one title-only entry; `format_version` raised to `1.1` in `zangbundel.json`. `scripts/validate.py` validates `setlists/**/*.zbs` (codes SL001–SL104, I004, I005, a warning when `format_version` is below 1.1); `scripts/release.py` puts valid setlists in the archive in canonical form, lists them in the manifest's `setlists` field with archive version 1.1, and verifies them (A104). README section "Setlists".
- `releases.json` with release 2026.10.0 (archive SHA-256 `a4730fdc…d0e9`, verified against the published asset).

### Changed
- *Nothing.*

### Fixed
- Release workflow: the index step treated a newly created `releases.json` as unchanged and never committed it; it now checks the staged file.
- `license.md` and `README.md` no longer say the scripts have the same licence as the app: the app dropped the Commons Clause for F-Droid on 2026-10-20, this repository keeps it (decisions driven by F-Droid do not apply here).

### Removed
- *Nothing.*

## [2026.10.0] - 2026-10-18

First release.

### Added
- `zangbundel.json`: library metadata, id `zangbundel-bibliotheek`, format version 1.0, collection licence CC BY-NC 4.0, tag labels for `kampvuur`, `kinderlied`, `volkslied` and `canon`, and the `release_index` URL.
- `songs/nl/advocaatje.cho`: "Advocaatje" (traditioneel, public domain), transcribed from `raw/ADVOCAAT.WPF` with the chords of the original.
- `songs/nl/daar-was-laatst-een-meisje-loos.cho`, `songs/nl/de-boer-had-maar-ene-schoen.cho`, `songs/nl/drie-schuintamboers.cho`: traditional songs, public domain (oldest prints 1771, c. 1860 and c. 1850 per the Nederlandse Liederenbank), transcribed from the Word files under `raw/`.
- `songs/nl/hoog-laait-het-vuur.cho`, `songs/nl/de-uil-zat-in-de-olmen.cho`, `songs/nl/de-koning-van-siam.cho`, `songs/nl/ik-heb-een-tante-in-marokko.cho`: campfire songs with no identifiable author (oldest documented prints c. 1952, 1992, 1993 and 1986); lyricist and composer `onbekend`, licence `proprietary`, copyright "Rechthebbende onbekend". Added at the maintainer's decision; report the rights holder if you know it.
- `.gitattributes` and `.editorconfig` pinning UTF-8, LF line endings and no trailing whitespace, as the format requires.
- Community files: `README.md`, `contributing.md`, `code_of_conduct.md`, `license.md`, `LICENSE`, this changelog. "Credits and corrections" notice: rights holders can request a correction or removal through a GitHub issue; the contribution rules allow songs with an untraceable author at the maintainer's discretion, marked `onbekend`.
- `scripts/validate.py`: command-line validator applying the library, song, warning and info codes of song-format specification section 11, with content hash and canonical line count per song. Licensed Apache 2.0 with Commons Clause (`scripts/LICENSE`).
- `scripts/release.py`: builds, verifies and indexes `.zbl` release archives per song-format specification section 12 (deterministic ZIP, manifest `zangbundel-archive.json`, archive checks A001 to A103, release index `releases.json`).
- `.github/workflows/validate.yml`: runs the validator with `--strict` on every push and pull request.
- `.github/workflows/release.yml`: on a pushed tag `v*`, builds and verifies the archive, publishes a GitHub release with the versioned and `-latest` archive, and updates `releases.json` on `main`.
- `.gitignore` for the `dist/` build output.

### Changed
- *Nothing.*

### Fixed
- *Nothing.*

### Removed
- *Nothing.*

<!-- Template for a release entry. Copy it above this comment when a version is cut.

## [x.y.z] - yyyy-mm-dd

### Added
- *Nothing.*

### Changed
- *Nothing.*

### Fixed
- *Nothing.*

### Removed
- *Nothing.*
-->
