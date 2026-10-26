# Zangbundel bibliotheek

A song library for the [Zangbundel](https://github.com/pe1mew/Zangbundel) campfire songbook app. Zangbundel ("songbook" in Dutch) shows lyrics on the phones of everyone around a campfire, pushed by one leader phone over Bluetooth Low Energy. The app itself contains no songs: it imports libraries like this one from git repositories.

This library holds Dutch campfire and children's songs. It follows the **Zangbundel library format 1.1** defined in [design/song-format.md](https://github.com/pe1mew/Zangbundel/blob/main/design/song-format.md) of the app repository.

## Repository layout

```
zangbundel.json       library metadata: id, name, licence, maintainer, tag labels
LICENSE               full text of the collection licence (CC BY-NC 4.0)
songs/                one ChordPro (.cho) file per song, in the Zangbundel profile
  nl/                 Dutch songs
  la/                 the demonstration song "Lorem Ipsum!"
setlists/             setlists (.zbs) shipped with the library, see "Setlists"
raw/                  source material the songs were transcribed from (ignored by the app)
releases.json         release index: every published .zbl archive with URL, size and SHA-256
scripts/validate.py   command-line validator applying the format's rules (see "Validating")
scripts/release.py    builds, verifies and indexes .zbl release archives (see "Releases")
.github/workflows/    runs the validator on every push; builds and publishes a release on every tag
.gitattributes        pins LF line endings, so song files hash identically everywhere
.editorconfig         editor settings matching the format (UTF-8, LF, no trailing spaces)
```

The app reads `zangbundel.json`, every `.cho` file under `songs/` and the licence file. Everything else is ignored. The subdirectories under `songs/` carry no meaning; a song's language comes from its `{meta: language …}` directive.

## Adding the library to the app

The easiest way is a **release archive**: a `.zbl` file (a ZIP with a manifest) that the app downloads over HTTPS, opens from a file, or receives from another phone. The newest archive is always at

```
https://github.com/pe1mew/Zangbundel-bibliotheek/releases/latest/download/zangbundel-bibliotheek-latest.zbl
```

and every release is listed in [releases.json](releases.json), which the app uses to check for updates. Alternatively, add the library by the URL of that release index:

```
https://raw.githubusercontent.com/pe1mew/Zangbundel-bibliotheek/main/releases.json
```

The app does not clone git repositories; it imports release archives only (app architecture decision A-11).

The library id is `zangbundel-bibliotheek`. The app shows the licence summary and the full `LICENSE` text on first import.

## Releases

A release is a git tag `v<version>` (calendar versioning, `v2026.10.0`) on the commit it describes. Pushing the tag runs `.github/workflows/release.yml`, which builds the archive from the tagged revision with `scripts/release.py`, verifies it, publishes it as a GitHub release under both `zangbundel-bibliotheek-<version>.zbl` and `zangbundel-bibliotheek-latest.zbl`, and updates `releases.json` on `main`.

The archive contains the manifest `zangbundel-archive.json` (revision, version, build time, content hash of every song), `zangbundel.json`, `LICENSE`, `README.md` and every song file that passes validation, in canonical form. Builds are deterministic: two builds of the same revision are byte-identical, so the SHA-256 in `releases.json` can be checked by anyone.

To build locally:

```bash
python scripts/release.py build --tag v2026.10.0
```

```bash
python scripts/release.py verify dist/zangbundel-bibliotheek-2026.10.0.zbl
```

```bash
python scripts/release.py index dist/zangbundel-bibliotheek-2026.10.0.zbl
```

`build` reads the tagged commit from git, never the working tree, and writes the archive and release notes to `dist/`. `verify` applies the archive checks the app applies (A001 to A103) and the library validator to the archive. `index` adds the archive to `releases.json`.

## Song file format in short

A song is one `.cho` file whose name is the song id (`advocaatje.cho` has id `advocaatje`). Required metadata: `{title: …}`, `{meta: id …}` equal to the file name, and `{meta: language …}` (a BCP 47 tag). Lyrics go in `{start_of_verse}` … `{end_of_verse}` and `{start_of_chorus}` … `{end_of_chorus}` blocks; `{chorus}` repeats the last chorus in full, so the text is complete and in sung order. Chords in `[F]` brackets are allowed and ignored by the phase 1 app. Lines starting with `#` are maintainer notes and are never shown.

See [songs/nl/advocaatje.cho](songs/nl/advocaatje.cho) for a complete example, and the format specification for the full rules, the validation codes and the canonicalisation the content hash is computed over.

## Setlists

A setlist (*setlist*) is the ordered programme of an evening. This library ships two: [setlists/voorbeeld-avond.zbs](setlists/voorbeeld-avond.zbs), an example evening, and [setlists/demo-setlist.zbs](setlists/demo-setlist.zbs), which holds only the demonstration song [songs/la/lorem-ipsum.cho](songs/la/lorem-ipsum.cho) (every metadata field filled in) for showing the app. The app imports every `.zbs` file under `setlists/` together with the library (song-format specification section 13, format 1.1). The file is plain text: `{title: …}` and `{meta: id …}` first, then one song per line as `<library id>/<song id>`, optionally followed by `# title` for readability, or `? <title>` for a song known only by name. Lines starting with `#` are comments. Leaders can write such a file on a computer, import it in the app from a file or URL, and export their own setlists in the same form. The validator checks setlists (codes `SL…`) and the release tool puts them in the archive and its manifest.

## Validating

`scripts/validate.py` applies the rules of section 11 of the format specification to the whole library: the library metadata, every song file, the canonicalisation and the canonical line list. It needs Python 3.8 or newer and no other dependencies.

```bash
python scripts/validate.py .
```

It prints one line per finding as `path:line LEVEL CODE message`, using the codes of the specification (`L…` library errors, `S…` song errors, `W…` warnings, `I…` informational), then one line per song with its content hash and canonical line count, and a summary. The exit status is non-zero when the library would be refused or a song would be skipped by the app. Options: `--strict` also fails on warnings (the CI workflow uses it), `--info` shows informational findings, `--app-version X.Y.Z` checks `min_app_version`, `--allow-empty` tolerates an empty `songs/`.

The same check runs on GitHub for every push and pull request.

## Your own private library

A group that wants songs of its own, for example its group song, or songs it may sing but not publish, can copy this repository into a private one and build its library there. The scripts, the validator and the release workflow come along. Nothing of the private library is ever published.

**What a private library means for the app.** The app downloads libraries only over plain HTTPS without logging in, so it cannot read a private repository or its releases. A private library therefore reaches the phones as a `.zbl` file: you build it, copy it to the leader's phone and open it there. Singers do not need it: the leader pushes each song over Bluetooth during the campfire. Leave `{meta: redistribute …}` at its default (`yes`) for songs singers should see, and only add songs you are allowed to share with the group.

### 1. Make the private copy

Create a new **private** repository on GitHub, for example `mijn-bibliotheek`, and leave it empty: no README, licence or `.gitignore`. Then copy this repository into it. Only the `main` branch is pushed; the tags of this library's releases are not, so its releases are not rebuilt in your repository.

```bash
git clone https://github.com/pe1mew/Zangbundel-bibliotheek.git mijn-bibliotheek
```

```bash
cd mijn-bibliotheek
```

```bash
git remote rename origin upstream
```

```bash
git remote add origin https://github.com/<your account>/mijn-bibliotheek.git
```

```bash
git push -u origin main
```

`origin` must be your private repository: the release tool takes the repository URL for the archive's manifest from it. `upstream` keeps a link to this repository, so you can later fetch improved scripts with `git fetch upstream` and copy them over.

### 2. Make it yours

| File | What to do |
|---|---|
| `zangbundel.json` | Give it a new `id` (lower case, digits and hyphens, for example `scouting-voorbeeld-liederen`). The app refuses a second library with the id `zangbundel-bibliotheek` from another source. Set `name`, `description`, `maintainer`, `license` (for songs only for your group, `"id": "proprietary"` with a one-line `summary`) and `languages`. **Remove `release_index` and `homepage`**: they point at this repository, and a private repository's URLs do not work in the app anyway. Keep or extend `tags`. |
| `releases.json` | **Delete it.** It lists this library's releases, and the release tool refuses to add your releases to another library's index. Your first release creates a new one. |
| `songs/` | Delete the songs you do not want and add your own `.cho` files. Songs you keep from this library stay under their own licence and the collection licence CC BY-NC 4.0; keep their metadata unchanged. |
| `setlists/` | Delete `voorbeeld-avond.zbs` and `demo-setlist.zbs`, or change their entries: an entry names a song as `<library id>/<song id>`, so after your id change the entries must use your id. |
| `LICENSE`, `license.md` | Replace them with the licence of your collection, or a short "for use within our group only" statement for `proprietary`. `LICENSE` is the file `zangbundel.json` names in `license.file`. |
| `README.md`, `changelog.md`, `contributing.md` | Rewrite them for your library, or delete what you do not need. |
| `scripts/` | Keep as is, including `scripts/LICENSE`. The Commons Clause allows using and changing the scripts for your own library; it asks you to keep the licence notice. |
| `raw/` | Delete it; it holds the source material of this library's songs. |

Write songs as described in "Song file format in short" above. Then check the whole library:

```bash
python scripts/validate.py .
```

Commit and push when it reports no errors.

### 3. Build a release

**On GitHub (recommended).** Tag the commit and push the tag. The release workflow builds the archive, verifies it, publishes it as a release in your private repository and writes your new `releases.json`. Private repositories use GitHub Actions minutes from your account; one release takes well under a minute.

```bash
git tag v2026.11.0
```

```bash
git push origin v2026.11.0
```

Download `<your id>-2026.11.0.zbl` from the release page while signed in to GitHub.

**Locally, without GitHub Actions.** Tag the commit (pushing the tag is optional) and build and verify the archive yourself; it is written to `dist/`:

```bash
python scripts/release.py build --tag v2026.11.0
```

```bash
python scripts/release.py verify dist/<your id>-2026.11.0.zbl
```

Builds are deterministic: the same tag always gives a byte-identical archive.

### 4. Put it on the leader's phone

Copy the `.zbl` file to the phone, by cable, by e-mail to yourself or through your own cloud storage, and open it in the app with **import from file**. For an update, build a new release and import the new file the same way. The app keeps the old version until the new one is complete, and shows which songs were added, changed or removed.

## Contributing

See [contributing.md](contributing.md) and the [Code of Conduct](code_of_conduct.md). Only contribute songs you have the right to distribute: traditional and public-domain songs, your own work, or songs whose licence allows it. Every song states its origin and licence in its metadata.

## Credits and corrections

Every effort is made to credit authors, composers and sources correctly and to state each song's licence truthfully. Songs whose author could not be traced after a reasonable search are marked as such in their metadata. If you are a rights holder, or know who is, and a song is credited wrongly, licensed wrongly or should not be distributed here, please [open an issue](https://github.com/pe1mew/Zangbundel-bibliotheek/issues) naming the song; the metadata will be corrected or the song removed. If you cannot use GitHub, contact the maintainer through the link in `zangbundel.json`.

## License

See [license.md](license.md) for details.

The collection (the selection, the transcriptions, the metadata and the documentation) is licensed under the Creative Commons Attribution-NonCommercial 4.0 International License (CC BY-NC 4.0) by Remko Welling, PE1MEW (https://github.com/pe1mew). The full text is in [LICENSE](LICENSE). Individual songs can carry a licence of their own in their `{meta: license …}` directive; traditional songs are marked `public-domain`. The validator and release tool under `scripts/` are code and are licensed under the Apache License 2.0 with the Commons Clause condition (see [scripts/LICENSE](scripts/LICENSE)).

<a rel="license" href="http://creativecommons.org/licenses/by-nc/4.0/"><img alt="Creative Commons License" style="border-width:0" src="https://i.creativecommons.org/l/by-nc/4.0/88x31.png" /></a><br />This work is licensed under a <a rel="license" href="http://creativecommons.org/licenses/by-nc/4.0/">Creative Commons Attribution-NonCommercial 4.0 International License</a>.

## Disclaimer

This library is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
