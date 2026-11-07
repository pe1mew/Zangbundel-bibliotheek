# Zangbundel bibliotheek

A song library for the [Zangbundel](https://github.com/pe1mew/Zangbundel) campfire songbook app. Zangbundel ("songbook" in Dutch) shows lyrics on the phones of everyone around a campfire, pushed by one leader phone over Bluetooth Low Energy. The app itself contains no songs: it imports libraries like this one from git repositories.

This library holds campfire, scouting and children's songs, most of them Dutch, with songs in English, German, French, Limburgish and a few other languages. It follows the **Zangbundel library format 1.1** defined in [design/song-format.md](https://github.com/pe1mew/Zangbundel/blob/main/design/song-format.md) of the app repository.

## Repository layout

```
zangbundel.json       library metadata: id, name, licence, maintainer, tag labels
LICENSE               full text of the collection licence (CC BY-NC 4.0)
songs/                one ChordPro (.cho) file per song, in the Zangbundel profile
  nl/                 Dutch songs
  en/, de/, fr/, li/  English, German, French and Limburgish songs
  af/, he/, it/, la/, mi/, nds/, srn/
                      songs in other languages; la/ also holds the demonstration song "Lorem Ipsum!"
setlists/             setlists (.zbs) shipped with the library, see "Setlists"
raw/                  source material the songs were transcribed from (ignored by the app)
releases.json         release index: every published .zbl archive with URL, size and SHA-256
scripts/validate.py   command-line validator applying the format's rules (see "Validating")
scripts/release.py    builds, verifies and indexes .zbl release archives (see "Releases")
scripts/conformance.py  runs the app's conformance corpus against these tools (see "The contract with the app")
scripts/test_package.py builds a library package of a release, for testing only (see "A test package")
release-menu.py       step-by-step menu for validating, committing, tagging and releasing (see "Releases")
.github/workflows/    on every push: the validator and the conformance corpus; on every tag: builds and publishes a release
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

### A test package (never published)

This library is published as release archives. The second library format, the *library package* of the library manager ([FDS](https://github.com/pe1mew/Zangbundel-bibliotheek-manager/blob/main/design/FDS.md), song format 12.11), would make it a different library on every phone (a package needs a UUID id) and would stop update checks (a package has no release index). To try the app's package reader or the library manager with this library's songs, `scripts/test_package.py` makes a package of a release archive for testing only:

```bash
python scripts/release.py build --tag v2026.11.0
```

```bash
python scripts/test_package.py dist/zangbundel-bibliotheek-2026.11.0.zbl
```

The package, `dist/zangbundel-bibliotheek-testpakket.zbl`, has the songs, each setlist as a set, the tag labels of `zangbundel.json` in the manifest's `tags` (song format v0.26), the 1.1 view (which carries no labels), a test id and the title "Zangbundel bibliotheek (testpakket)". It is signed with the public RFC 8032 test key (fingerprint `21FE-31DF-A154-A261`). Title-only setlist entries are left out and reported, because a set lists song ids only. The script uses the library manager repository's `test-libraries/make_test_libraries.py`, which it expects next to this repository (`--manager` names another place). Never publish the result: anyone can sign with the test key.

### Without git commands: the release menu

`release-menu.py` guides you through a release step by step, in Dutch, English or German. Double-click it in the library folder (Windows needs Python 3 and Git for Windows installed), or run `python release-menu.py`. The menu lists every step with its number; the release order is shown below the menu:

| Step | Menu item | What happens |
|---|---|---|
| 1 | 2 Validate library | Runs the validator. Nothing changes. |
| 2 | 4 Stage changes | Stages changes to the library's own files: `songs/`, `setlists/`, `zangbundel.json`, the licence, README and changelog. Other files are listed and left alone. |
| 3 | 5 Create commit | Checks GitHub for newer commits (and offers to pull them), refuses while library changes are unstaged, validates, and asks for a commit message. |
| 4 | 6 Set tag | Suggests the next tag, such as `v2026.11.1`. First it builds and verifies the commit exactly as GitHub will, so a pushed tag does not start a release that fails. |
| 5 | 10 Push commits | Uploads the commits to GitHub. |
| 6 | 11 Push tag | Uploads the tag, which starts the release on GitHub. |
| 7 | 12 Fetch changes | After the green tick under **Actions**: pulls the new `releases.json`. |

Every git command that changes something is shown first and runs only when you answer `j` or `y`. Pulling is fast-forward only: the menu never makes a merge commit. Menu item 1 switches on explanations of each step, and item 3 shows the state of your folder compared with GitHub.

The menu is based on Pepe's menu for his own library ([issue #3](https://github.com/pe1mew/Zangbundel-bibliotheek/issues/3)), which he dedicated to the public domain.

**GitHub Desktop.** If you prefer windows to a terminal, [GitHub Desktop](https://desktop.github.com/) does staging, committing, tagging (in the history, right-click a commit → **Create tag…**), pushing and pulling with dialog boxes. Then only the validator needs the terminal: run `python scripts/validate.py --strict --info .` before you commit, and push the tag after its commit.

## Song file format in short

A song is one `.cho` file whose name is the song id (`advocaatje.cho` has id `advocaatje`). Required metadata: `{title: …}`, `{meta: id …}` equal to the file name, and `{meta: language …}` (a language tag, see [Language codes](#language-codes) below). Lyrics go in `{start_of_verse}` … `{end_of_verse}` and `{start_of_chorus}` … `{end_of_chorus}` blocks; `{chorus}` repeats the last chorus in full, so the text is complete and in sung order. Chords in `[F]` brackets are allowed and ignored by the phase 1 app. Lines starting with `#` are maintainer notes and are never shown.

See [songs/nl/advocaatje.cho](songs/nl/advocaatje.cho) for a complete example, and the format specification for the full rules, the validation codes and the canonicalisation the content hash is computed over.

### Language codes

The language of a song is written as a **BCP 47 language tag**. BCP 47 is the international standard for naming languages, the one web pages and phones use; it is not an abbreviation of this project. Most tags are just the two- or three-letter code of the language: `nl` Dutch, `en` English, `fy` Western Frisian. A region or a script can follow after a hyphen: `nds-NL` is Low Saxon as spoken in the Netherlands, `he-Latn` is Hebrew written in Latin letters.

To find the code for a language, search the official list for the language's English name: the [IANA language subtag registry](https://www.iana.org/assignments/language-subtag-registry/language-subtag-registry). Each entry gives the code after `Subtag:` and the language after `Description:`. Use the shortest code the registry has for the language.

The folders under `songs/` are named after the languages used in this library. The folder name is only for people; the app reads the language from `{meta: language …}`.

| Folder | Tag | Language |
|---|---|---|
| `af` | `af` | Afrikaans |
| `de` | `de` | German |
| `en` | `en` | English |
| `fr` | `fr` | French |
| `he` | `he-Latn` | Hebrew, in Latin letters |
| `it` | `it` | Italian |
| `la` | `la` | Latin |
| `li` | `li` | Limburgish |
| `mi` | `mi` | Maori |
| `nds` | `nds-NL` | Low Saxon (Netherlands) |
| `nl` | `nl` | Dutch |
| `srn` | `srn` | Sranan Tongo |

## Setlists

A setlist (*setlist*) is the ordered programme of an evening. This library ships two: [setlists/voorbeeld-avond.zbs](setlists/voorbeeld-avond.zbs), an example evening, and [setlists/demo-setlist.zbs](setlists/demo-setlist.zbs), which holds only the demonstration song [songs/la/lorem-ipsum.cho](songs/la/lorem-ipsum.cho) (every metadata field filled in) for showing the app. The app imports every `.zbs` file under `setlists/` together with the library (song-format specification section 13, format 1.1). The file is plain text: `{title: …}` and `{meta: id …}` first, then one song per line as `<library id>/<song id>`, optionally followed by `# title` for readability, or `? <title>` for a song known only by name. Lines starting with `#` are comments. Leaders can write such a file on a computer, import it in the app from a file or URL, and export their own setlists in the same form. The validator checks setlists (codes `SL…`) and the release tool puts them in the archive and its manifest.

## Validating

`scripts/validate.py` applies the rules of section 11 of the format specification to the whole library: the library metadata, every song file, the canonicalisation and the canonical line list. It needs Python 3.8 or newer and no other dependencies.

```bash
python scripts/validate.py .
```

It prints one line per finding as `path:line LEVEL CODE message`, using the codes of the specification (`L…` library errors, `S…` song errors, `W…` warnings, `I…` informational), then one line per song with its content hash and canonical line count, and a summary. The exit status is non-zero when the library would be refused or a song would be skipped by the app. Options: `--strict` also fails on warnings (the CI workflow uses it), `--info` shows informational findings, `--app-version X.Y.Z` checks `min_app_version`, `--allow-empty` tolerates an empty `songs/`.

The same check runs on GitHub for every push and pull request.

### The contract with the app

The format is defined by [design/song-format.md](https://github.com/pe1mew/Zangbundel/blob/main/design/song-format.md) in the app repository; this repository's tools and the app each implement it. Both are held to the same **conformance corpus**: test vectors with the result the specification requires, in the app repository under `android/core/testing/src/main/resources/conformance/`. The vectors cover songs, setlists, library files (`zangbundel.json`) and archives, both good and bad. They also cover library packages: the library manager's shared test libraries, which these tools read as an app from before packages does, through the package's format 1.1 view. The app's tests run them, and so does `scripts/conformance.py` here:

```bash
python scripts/conformance.py <path to the conformance folder>
```

The validation workflow runs it on every push, against the corpus at a pinned commit of the app repository (`CONFORMANCE_REF` in `.github/workflows/validate.yml`). A disagreement is a bug in one implementation or in the specification. The script's docstring says what is compared for each kind of vector.

## Your own songs the easy way: a ZIP file

The quickest way to put a group's own songs in the app needs no GitHub, no git and no Python. Write the songs, put them in a folder with two small files, zip the folder's contents, and open the ZIP in the app. The app checks every song on import and reports anything it cannot use.

What you give up compared with a library on GitHub: the app cannot check for updates, so after a change you zip and import again; the library has no version number (the app shows "snapshot, revision unknown"); and nothing proves the ZIP was not altered on the way. Singers do not need the ZIP: the leader pushes each song over Bluetooth during the campfire.

### 1. Make the folder

```
mijn-liedjes/
  zangbundel.json        about the library (see below)
  LICENSE                a text file saying who may use the songs
  songs/                 one .cho file per song
    ons-groepslied.cho
  setlists/              optional: setlists (.zbs) for your evenings
    eerste-avond.zbs
```

`zangbundel.json` describes the library. Copy this and change the values:

```json
{
  "format": "zangbundel-library",
  "format_version": "1.1",
  "id": "scouting-voorbeeld",
  "name": "Liederen van Scouting Voorbeeld",
  "description": "Onze eigen kampvuurliederen.",
  "maintainer": { "name": "Jan Jansen", "email": "liederen@example.org" },
  "license": { "id": "proprietary", "file": "LICENSE", "summary": "Alleen voor eigen gebruik binnen de groep." },
  "min_app_version": "0.1.0"
}
```

- `id`: lower-case letters, digits and hyphens. It names your library and must not be the id of another library you use, such as `zangbundel-bibliotheek`.
- `name`, `description`: shown in the app.
- `maintainer`: a name, plus an `email` or a `url`.
- `license`: for songs meant only for your group, keep `proprietary` and write a one-line `summary`. `file` names the licence file, which must exist: without it the app refuses the library. A single line in `LICENSE`, such as "Alleen voor eigen gebruik binnen Scouting Voorbeeld.", is enough.
- `format`, `format_version` and `min_app_version`: leave as shown.

### 2. Write the songs

Each song is a plain text file under `songs/`, named after the song's id: `ons-groepslied.cho` starts with `{meta: id ons-groepslied}`. See "Song file format in short" below, and use [songs/la/lorem-ipsum.cho](songs/la/lorem-ipsum.cho) as an example: it uses every field. Save the files as UTF-8 text in any editor, such as Notepad; the line endings do not matter. Check that the name ends in `.cho` and not in `.cho.txt`: Windows hides known extensions by default, so turn on **View → File name extensions** in Explorer.

A setlist (optional) names songs as `<library id>/<song id>`, so with the example id: `scouting-voorbeeld/ons-groepslied`. See "Setlists" below.

### 3. Zip it

Zip the **contents** of the folder, not the folder itself: open `mijn-liedjes`, select everything in it (`zangbundel.json`, `LICENSE`, `songs`, `setlists`), and then:

- **Windows:** right-click → **Send to** → **Compressed (zipped) folder** (on Windows 11, first choose **Show more options**).
- **macOS:** right-click → **Compress**.

Do not use the `Compress-Archive` command of Windows PowerShell 5.1: it writes backslashes into the ZIP, and the app refuses such a file.

### 4. Open it in the app

Copy the ZIP to the leader's phone, by cable, by e-mail to yourself or through your own cloud storage, and open it in the app with **import from file**.

The app shows a report:
- A song with a mistake is left out and listed with the reason; the other songs are imported.
- Only a missing or wrong `zangbundel.json` or licence file stops the whole import.

To change something, edit the files, zip again and import the new ZIP. The app replaces the library and shows which songs were added, changed or removed.

**Checking before you import (optional).** With Python 3 installed and a copy of this repository's `scripts/` folder, run the same checks the app runs:

```bash
python scripts/release.py verify mijn-liedjes.zip
```

"Archive accepted" means the app will import it. The warning A102 (no manifest, no update checks) is expected for a ZIP made this way.

When the group outgrows this, because it wants version numbers, update checks or several maintainers, move the same folder into a repository as described next.

### Planned: easier still

Two further steps are planned ([issue #1](https://github.com/pe1mew/Zangbundel-bibliotheek/issues/1)). Neither exists yet.

- **A library builder in the browser.** A web page on GitHub Pages where you choose your song files or your ZIP.
  - It runs the validator's checks and explains problems in plain language.
  - It can turn folders into setlists.
  - It hands back a finished `.zbl` with a version number and a checksum.
  - The checks run in your own browser and nothing is uploaded: the project has no server, also not for library maintainers.
- **A seal against tampering.** The builder would sign the archive with a key that stays on the maintainer's computer. The app would remember a library's key at the first import and refuse any later archive of that library not signed with it. This needs a change to the format specification (open question Q12, signing release archives) and to the app, so it follows the builder.

## Your own private library

A group that wants songs of its own, for example its group song, or songs it may sing but not publish, can copy this repository into a private one and build its library there. The scripts, the validator and the release workflow come along. Nothing of the private library is ever published. This takes more setup than the ZIP file above, and in return gives version numbers, release archives and checks on every push.

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
| `scripts/`, `release-menu.py` | Keep as they are, including `scripts/LICENSE`. If your folder layout differs, adjust `LIBRARY_PATHS` at the top of the menu. The Commons Clause allows using and changing the scripts for your own library; it asks you to keep the licence notice. |
| `raw/` | Delete it; it holds the source material of this library's songs. |
| `.gitignore` | **Keep it.** It keeps `dist/` and `*.zbl` out of git: the archives you build locally belong on the release page, not in the repository. If you committed them anyway, remove them from git (the files stay on your disk) with `git rm -r --cached dist` and commit. |

Write songs as described in "Song file format in short" above. Then check the whole library:

```bash
python scripts/validate.py .
```

Commit and push when it reports no errors.

### 3. Build a release

**With the release menu (easiest).** Double-click `release-menu.py` and follow the release order it shows; see "Without git commands: the release menu" above. It checks and builds the tagged commit before you push the tag.

**On GitHub, with git commands.** Tag the commit and push the tag. The release workflow builds the archive, verifies it, publishes it as a release in your private repository and writes your new `releases.json`. Private repositories use GitHub Actions minutes from your account; one release takes well under a minute.

```bash
git tag v2026.11.0
```

```bash
git push origin v2026.11.0
```

Download `<your id>-2026.11.0.zbl` from the release page while signed in to GitHub.

If no release appears, open the run under **Actions**. The summary page of a failed run lists the cause, for example a song with an error, with the file and line where possible, and the steps to fix it. Fix the cause, delete the tag, and tag and push again:

```bash
git tag -d v2026.11.0
```

```bash
git push origin :refs/tags/v2026.11.0
```

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
