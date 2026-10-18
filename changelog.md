# Changelog

All notable changes to this library are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/). The library follows Zangbundel library format 1.0 (`format_version` in `zangbundel.json`). Releases are tagged `v<version>` with calendar versions (`year.month.sequence`) and published as `.zbl` archives; see `releases.json`.

## [Unreleased]

### Added
- *Nothing.*

### Changed
- *Nothing.*

### Fixed
- *Nothing.*

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
