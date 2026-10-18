# License Information

Three kinds of material meet in this library, and they are licensed differently.

## The collection: Creative Commons BY-NC 4.0

The collection as a whole, meaning the selection and arrangement of songs, the transcriptions, the song metadata, `zangbundel.json` and the documentation in this repository, is licensed under the **Creative Commons Attribution-NonCommercial 4.0 International License (CC BY-NC 4.0)**. The full legal text is in the [LICENSE file](LICENSE). This is the licence the Zangbundel app shows when the library is imported, and the licence that applies to any song that does not state one of its own.

You may:

- **Share**: copy and redistribute the collection in any medium or format for non-commercial purposes.
- **Adapt**: remix, transform and build upon the collection for non-commercial purposes.

Under these conditions:

- **Attribution**: give appropriate credit, provide a link to the licence and indicate if changes were made, but not in any way that suggests the licensor endorses you or your use.
- **Non-commercial**: the collection may not be used for commercial purposes.

Summary: https://creativecommons.org/licenses/by-nc/4.0/

## Individual songs: see the song file

Each song file carries its own origin and licence metadata, which the app shows to its users:

| Directive | Meaning |
|---|---|
| `{lyricist: …}`, `{composer: …}` | Who wrote the words and the melody. `traditioneel` for traditional songs. |
| `{copyright: …}` | Copyright holder or notice, or `Public domain`. |
| `{meta: license …}` | An SPDX identifier (`CC-BY-SA-4.0`, `CC0-1.0`, …), `public-domain` or `proprietary`. When absent, the collection licence above applies. |
| `{meta: source …}` | Where the text came from. |

Traditional songs whose words and melody are in the public domain are marked `public-domain`; the collection licence does not restrict them beyond the transcription itself. Contributors are responsible for having the right to distribute every song they add, and for stating its licence correctly. Songs that are neither public domain nor released under a licence that permits redistribution are not accepted; see [contributing.md](contributing.md).

## Code: Apache License 2.0 with the Commons Clause

The code in this repository, today the validator under `scripts/`, is licensed under the **Apache License 2.0**, subject to the **Commons Clause License Condition v1.0**, the same terms as the Zangbundel app. In short:

- **Use, modify and redistribute** the code under the terms of the Apache License 2.0.
- **No selling**: the Commons Clause withholds the right to sell the software, meaning to provide it, or a product or service whose value derives substantially from it, to third parties for a fee or other consideration. Running it for your own library, modifying it and sharing your changes are all fine.
- **Attribution**: keep the licence and attribution notices, including the Commons Clause notice, in any copy or derivative.

The full condition is in [scripts/LICENSE](scripts/LICENSE). The Apache License 2.0 text is at https://www.apache.org/licenses/LICENSE-2.0.

---

*By using this repository, you agree to comply with the licensing terms described above.*
