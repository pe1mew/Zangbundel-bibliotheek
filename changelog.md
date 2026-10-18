# Changelog

All notable changes to this library are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/). The library follows Zangbundel library format 1.0 (`format_version` in `zangbundel.json`).

## [Unreleased]

### Added
- `zangbundel.json`: library metadata, id `zangbundel-bibliotheek`, format version 1.0, collection licence CC BY-NC 4.0, tag labels for `kampvuur` and `kinderlied`.
- `songs/nl/advocaatje.cho`: "Advocaatje" (traditioneel, public domain), transcribed from `raw/ADVOCAAT.WPF` with the chords of the original.
- `.gitattributes` and `.editorconfig` pinning UTF-8, LF line endings and no trailing whitespace, as the format requires.
- Community files: `README.md`, `contributing.md`, `code_of_conduct.md`, `license.md`, `LICENSE`, this changelog.
- `scripts/validate.py`: command-line validator applying the library, song, warning and info codes of song-format specification section 11, with content hash and canonical line count per song. Licensed Apache 2.0 with Commons Clause (`scripts/LICENSE`).
- `.github/workflows/validate.yml`: runs the validator with `--strict` on every push and pull request.

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
