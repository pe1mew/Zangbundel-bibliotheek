# Changelog

All notable changes to this library are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/). The library follows Zangbundel library format 1.1 (`format_version` in `zangbundel.json`; 1.0 until release 2026.10.0). Releases are tagged `v<version>` with calendar versions (`year.month.sequence`) and published as `.zbl` archives; see `releases.json`.

## [Unreleased]

### Added
- README section "Your own private library". It explains how to copy this repository into a private one (only `main`, with this repository kept as `upstream`) and what to change: a new id, no `release_index` or `homepage`, and deleting `releases.json`, because the release tool refuses another library's index. It covers how to build a release on GitHub or locally, and how to get the `.zbl` file onto the leader's phone with "import from file", since the app cannot read private repositories. Rehearsed on a scratch clone: the validator accepts the result.

### Changed
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
