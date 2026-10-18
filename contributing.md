# Contributing Guidelines

Thank you for considering contributing to the Zangbundel bibliotheek. This repository is a song library for the [Zangbundel](https://github.com/pe1mew/Zangbundel) app; contributions are songs, corrections to songs, and improvements to the metadata.

## What to contribute, and where

| You want to | Do this |
|---|---|
| Add a song | Open a pull request adding one `.cho` file under `songs/`. See "Adding a song" below. |
| Correct lyrics or metadata | Open a pull request against the song file. Quote the source you corrected from. |
| Report a problem with a song | Open an issue naming the file and the line. |
| Change the song file format | **Not here.** The format is defined in the app repository, `design/song-format.md`. Open an issue there. |
| Work on the app | See the [Zangbundel repository](https://github.com/pe1mew/Zangbundel). |

Discussion in Dutch or English is welcome.

## Licensing of contributions

Only contribute songs you have the right to distribute:

- **Traditional and public-domain songs**: words and melody out of copyright. Mark them `{lyricist: traditioneel}`, `{composer: traditioneel}` (or the known author when there is one), `{copyright: Public domain}` and `{meta: license public-domain}`.
- **Your own songs**: state yourself as lyricist and composer and choose a licence that permits redistribution, for example `{meta: license CC-BY-SA-4.0}` or `CC0-1.0`.
- **Songs under an open licence**: state the licence and the source.
- **Songs whose author or rights holder cannot be traced**: many campfire songs are passed on orally and appear in print without a name. Such a song can be accepted at the maintainer's discretion when a reasonable search (for example in the [Nederlandse Liederenbank](https://www.liederenbank.nl/)) finds no author. Mark it `{lyricist: onbekend}`, `{composer: onbekend}`, `{copyright: Rechthebbende onbekend}` and `{meta: license proprietary}`, and record in a `#` comment what you searched and the oldest print you found, so the status can be revisited.

Songs with a known author that are still under copyright are not accepted without a licence from the rights holder, however well known they are. Always fill `{meta: source …}` so the origin can be checked.

## Credits and corrections

Every effort is made to credit authors, composers and sources correctly, and to state the licence of every song truthfully. If you are a rights holder, or you know who is, and a song is credited wrongly, is licensed wrongly or should not be here, please [open an issue](https://github.com/pe1mew/Zangbundel-bibliotheek/issues) naming the song. The maintainer will correct the metadata or remove the song. If you cannot use GitHub, contact the maintainer through the link in `zangbundel.json`.

## Adding a song

1. **Fork and clone** the repository, and create a branch:
   ```sh
   git checkout -b song/your-song-id
   ```
2. **Choose the song id**: lower-case letters, digits and single hyphens, derived from the title with accents removed ("Zeg ken jij de mosselman?" becomes `zeg-ken-jij-de-mosselman`). The id is the file name and must be unique in the library. It never changes once published.
3. **Create `songs/<language>/<song id>.cho`**: UTF-8, LF line endings, no trailing spaces, one final newline. The `.editorconfig` and `.gitattributes` in this repository take care of that in most editors. Use [songs/nl/advocaatje.cho](songs/nl/advocaatje.cho) as a template:
   - Required: `{title: …}`, `{meta: id …}` equal to the file name, `{meta: language …}` (BCP 47: `nl`, `en`, `fy`, …).
   - Recommended: `{lyricist}`, `{composer}`, `{copyright}`, `{meta: license}`, `{meta: source}` and one or more `{meta: tag …}`.
   - Lyrics in `{start_of_verse}` … `{end_of_verse}`, `{start_of_chorus}` … `{end_of_chorus}` and `{start_of_bridge}` … `{end_of_bridge}` blocks. Repeat a chorus with `{chorus}`, so the app shows the complete text in sung order. Leave the labels out unless the song needs a specific one; the app generates "Couplet 1" / "Refrein" in the user's language.
   - Chords in `[F]` brackets are welcome but optional. A backslash escapes a literal bracket or brace.
   - Maintainer notes go in `#` lines; they are never shown.
4. **New tag?** Add its Dutch and English label to the `tags` map in `zangbundel.json`.
5. **Keep source material** under `raw/` when its licence allows it, and name it in `{meta: source …}`.
6. **Run the validator** and fix everything it reports; the pull request check runs it with `--strict`, so warnings fail too:
   ```bash
   python scripts/validate.py --strict --info .
   ```
7. **Add a line** under `[Unreleased]` in `changelog.md`.

## Commit messages

Imperative subject, under 72 characters, naming the song, for example `Add Advocaatje (traditioneel)`. Keep commits focused: one song or one correction per commit.

## Submitting a pull request

1. **Push to your fork**:
   ```sh
   git push origin song/your-song-id
   ```
2. **Open a pull request** against `main`, stating the source of the lyrics and their licence.

## Review process

- The validator runs automatically on every pull request; it must pass before review.
- Pull requests are reviewed by the maintainer, who checks the licence, the source and the format rules.
- Be open to feedback and make the requested changes.

## Community standards

- Follow the [Code of Conduct](code_of_conduct.md).
- Be respectful and collaborative.
