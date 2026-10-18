# Zangbundel bibliotheek

A song library for the [Zangbundel](https://github.com/pe1mew/Zangbundel) campfire songbook app. Zangbundel ("songbook" in Dutch) shows lyrics on the phones of everyone around a campfire, pushed by one leader phone over Bluetooth Low Energy. The app itself contains no songs: it imports libraries like this one from git repositories.

This library holds Dutch campfire and children's songs. It follows the **Zangbundel library format 1.0** defined in [design/song-format.md](https://github.com/pe1mew/Zangbundel/blob/main/design/song-format.md) of the app repository.

## Repository layout

```
zangbundel.json       library metadata: id, name, licence, maintainer, tag labels
LICENSE               full text of the collection licence (CC BY-NC 4.0)
songs/                one ChordPro (.cho) file per song, in the Zangbundel profile
  nl/                 Dutch songs
raw/                  source material the songs were transcribed from (ignored by the app)
scripts/validate.py   command-line validator applying the format's rules (see "Validating")
.github/workflows/    runs the validator on every push and pull request
.gitattributes        pins LF line endings, so song files hash identically everywhere
.editorconfig         editor settings matching the format (UTF-8, LF, no trailing spaces)
```

The app reads `zangbundel.json`, every `.cho` file under `songs/` and the licence file. Everything else is ignored. The subdirectories under `songs/` carry no meaning; a song's language comes from its `{meta: language …}` directive.

## Adding the library to the app

In the app, add a library and enter this repository's URL:

```
https://github.com/pe1mew/Zangbundel-bibliotheek.git
```

The library id is `zangbundel-bibliotheek`. The app shows the licence summary and the full `LICENSE` text on first import.

## Song file format in short

A song is one `.cho` file whose name is the song id (`advocaatje.cho` has id `advocaatje`). Required metadata: `{title: …}`, `{meta: id …}` equal to the file name, and `{meta: language …}` (a BCP 47 tag). Lyrics go in `{start_of_verse}` … `{end_of_verse}` and `{start_of_chorus}` … `{end_of_chorus}` blocks; `{chorus}` repeats the last chorus in full, so the text is complete and in sung order. Chords in `[F]` brackets are allowed and ignored by the phase 1 app. Lines starting with `#` are maintainer notes and are never shown.

See [songs/nl/advocaatje.cho](songs/nl/advocaatje.cho) for a complete example, and the format specification for the full rules, the validation codes and the canonicalisation the content hash is computed over.

## Validating

`scripts/validate.py` applies the rules of section 11 of the format specification to the whole library: the library metadata, every song file, the canonicalisation and the canonical line list. It needs Python 3.8 or newer and no other dependencies.

```bash
python scripts/validate.py .
```

It prints one line per finding as `path:line LEVEL CODE message`, using the codes of the specification (`L…` library errors, `S…` song errors, `W…` warnings, `I…` informational), then one line per song with its content hash and canonical line count, and a summary. The exit status is non-zero when the library would be refused or a song would be skipped by the app. Options: `--strict` also fails on warnings (the CI workflow uses it), `--info` shows informational findings, `--app-version X.Y.Z` checks `min_app_version`, `--allow-empty` tolerates an empty `songs/`.

The same check runs on GitHub for every push and pull request.

## Contributing

See [contributing.md](contributing.md) and the [Code of Conduct](code_of_conduct.md). Only contribute songs you have the right to distribute: traditional and public-domain songs, your own work, or songs whose licence allows it. Every song states its origin and licence in its metadata.

## License

See [license.md](license.md) for details.

The collection (the selection, the transcriptions, the metadata and the documentation) is licensed under the Creative Commons Attribution-NonCommercial 4.0 International License (CC BY-NC 4.0) by Remko Welling, PE1MEW (https://github.com/pe1mew). The full text is in [LICENSE](LICENSE). Individual songs can carry a licence of their own in their `{meta: license …}` directive; traditional songs are marked `public-domain`. The validator under `scripts/` is code and is licensed under the Apache License 2.0 with the Commons Clause condition (see [scripts/LICENSE](scripts/LICENSE)), as in the app repository.

<a rel="license" href="http://creativecommons.org/licenses/by-nc/4.0/"><img alt="Creative Commons License" style="border-width:0" src="https://i.creativecommons.org/l/by-nc/4.0/88x31.png" /></a><br />This work is licensed under a <a rel="license" href="http://creativecommons.org/licenses/by-nc/4.0/">Creative Commons Attribution-NonCommercial 4.0 International License</a>.

## Disclaimer

This library is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
