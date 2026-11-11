#!/usr/bin/env python3
"""Build a signed library package of a release archive, to publish next to that archive.

A library package is the second library format, defined by the library manager's FDS
(`Zangbundel-bibliotheek-manager/design/FDS.md`) and song format 12.11. Unlike a release archive
it carries a signature (`manifest.sig`, Ed25519, FDS section 5): the app shows the author name and
fingerprint, remembers the key, and warns when an update is signed with another key.

The package holds the same songs as the archive:

- the songs as `songs/<id>/<id>.cho`, byte for byte;
- each setlist with songs of this library as a set; entries naming other libraries and title-only
  entries are left out and reported, and a setlist left without songs is not a set (SET-03);
- the tag labels of `zangbundel.json` in the manifest's `tags` (song format 12.11);
- the 1.1 view the FDS requires;
- `libraryId` and `created` from `library-package.json` in the repository, so every release
  updates the same library in the app. Create that file once with `--init`;
- `version` from the release version: `2026.11.3` becomes 20261103 (year, month, two digits of
  sequence), so a later release always has a higher version;
- `modified` from the archive's `created`, and `changes` from the release's summary in
  `changelog.md` at the archive's revision, at most 500 characters;
- `author` and the signature from the key file (`.zbkey`, FDS 5.3). The key is read locally and
  never written anywhere.

A package has its own library id (a UUID), so on a phone it is a different library from the
release archive: install one or the other, not both.

Usage:
    python scripts/package.py --init                 (once: creates library-package.json)
    python scripts/package.py <archive.zbl> --key <file.zbkey>

The package is written to `dist/<library id>-<version>-pakket.zbl`, which `.gitignore` keeps out of
git. The script uses `make_test_libraries.py` of the library manager repository for the view, the
files list and Ed25519 signing, so both build packages the same way; by default it looks for that
repository next to this one (`--manager` names another place). Output is deterministic.

Standard library only. Python 3.8 or newer.

Copyright 2026 Remko Welling, PE1MEW.
Licensed under the Apache License 2.0 with the Commons Clause condition; see
scripts/LICENSE and license.md.
"""

import argparse
import base64
import datetime
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import release  # noqa: E402
import test_package  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ID_FILE = 'library-package.json'
UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')
VERSION_RE = re.compile(r'^(\d{4})\.(\d{1,2})\.(\d{1,2})$')
MAX_CHANGES = 500


def init(repo):
    path = os.path.join(repo, ID_FILE)
    if os.path.exists(path):
        raise SystemExit('error: %s exists already; a library id is assigned once (FDS 4.1)' % ID_FILE)
    data = {'libraryId': str(uuid.uuid4()),
            'created': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(json.dumps(data, indent=2) + '\n')
    print('wrote %s: libraryId %s, created %s' % (ID_FILE, data['libraryId'], data['created']))
    print('Commit it: the id must never change, or phones see a new library.')


def read_id_file(repo):
    path = os.path.join(repo, ID_FILE)
    try:
        with open(path, encoding='utf-8') as fh:
            data = json.load(fh)
    except OSError:
        raise SystemExit('error: %s not found; create it once with --init and commit it' % ID_FILE)
    if not UUID_RE.match(str(data.get('libraryId', ''))):
        raise SystemExit('error: %s: libraryId is not a lower-case UUID version 4 (FDS 4.1)' % ID_FILE)
    if not re.match(r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$', str(data.get('created', ''))):
        raise SystemExit('error: %s: created is not YYYY-MM-DDThh:mm:ssZ' % ID_FILE)
    return data


def read_key(path, builder):
    """The seed and name of a key file (FDS 5.3), checked as SG-11 says. The seed is never printed."""
    with open(path, encoding='utf-8') as fh:
        key = json.load(fh)
    if key.get('type') != 'songbook-signing-key' or key.get('formatVersion') != 1 or key.get('algorithm') != 'Ed25519':
        raise SystemExit('error: %s is not an Ed25519 key file of format 1 (FDS 5.3)' % path)
    try:
        seed = base64.b64decode(key['privateKey'], validate=True)
        pub = base64.b64decode(key['publicKey'], validate=True)
    except (KeyError, ValueError):
        raise SystemExit('error: %s: privateKey or publicKey is not base64' % path)
    if len(seed) != 32 or len(pub) != 32 or builder.public_key(seed) != pub:
        raise SystemExit('error: %s: the private key does not belong to the public key (SG-11)' % path)
    name = key.get('name')
    if not isinstance(name, str) or not 1 <= len(name) <= 100:
        raise SystemExit('error: %s: name must be 1 to 100 characters (FDS 4.1, author.name)' % path)
    return seed, name


def package_version(version):
    m = VERSION_RE.match(version)
    if not m:
        raise SystemExit('error: release version %s is not year.month.sequence; a package version must be a '
                         'number that only goes up' % version)
    year, month, seq = (int(x) for x in m.groups())
    if not 1 <= month <= 12 or seq > 99:
        raise SystemExit('error: release version %s gives no package version (month 1-12, sequence 0-99)' % version)
    return year * 10000 + month * 100 + seq


def changes_note(repo, revision, version):
    """The summary of the version's changelog section at the archive's revision, at most 500 characters."""
    for name in ('changelog.md', 'CHANGELOG.md'):
        try:
            text = subprocess.run(['git', 'show', '%s:%s' % (revision, name)], cwd=repo, capture_output=True,
                                  check=True).stdout.decode('utf-8')
        except (subprocess.CalledProcessError, OSError):
            continue
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'changelog.md')
            with open(path, 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(text)
            section = release.changelog_section(path, version)
        if not section or not section[0]:
            return None
        note = ' '.join(section[0].split())
        if len(note) > MAX_CHANGES:
            cut = note[:MAX_CHANGES - 1]
            end = max(cut.rfind('. '), cut.rfind('; '))
            note = (cut[:end + 1] if end > MAX_CHANGES // 2 else cut.rstrip()) + '…'
        return note
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description='Build a signed library package of a release archive.')
    parser.add_argument('archive', nargs='?', help='release archive (.zbl) of this library')
    parser.add_argument('--key', help='key file (.zbkey, FDS 5.3) to sign with')
    parser.add_argument('--init', action='store_true', help='create %s with a new library id, once' % ID_FILE)
    parser.add_argument('--repo', default=REPO, help='library repository (default: the one holding this script)')
    parser.add_argument('--manager', default=os.path.join(os.path.dirname(REPO), 'Zangbundel-bibliotheek-manager'),
                        help='library manager repository (default: next to this repository)')
    parser.add_argument('--out', help='output file (default: dist/<library id>-<version>-pakket.zbl)')
    args = parser.parse_args(argv)
    if args.init:
        init(args.repo)
        return 0
    if not args.archive or not args.key:
        parser.error('give the release archive and --key, or --init')

    ids = read_id_file(args.repo)
    builder = test_package.load_builder(args.manager)
    seed, author = read_key(args.key, builder)

    with zipfile.ZipFile(args.archive) as z:
        if release.MANIFEST_NAME not in z.namelist():
            raise SystemExit('error: %s is not a release archive (no %s)' % (args.archive, release.MANIFEST_NAME))
        archive = json.loads(z.read(release.MANIFEST_NAME))
    lib, license_text, songs, setlists = test_package.read_archive(args.archive)
    version = archive['version']

    notes = []
    sets = [s for s in test_package.sets_from(setlists, lib['id'], songs, notes) if s['songs']]
    left = len(setlists) - len(sets)
    if left:
        notes.append('%d setlist(s) without songs of this library left out (SET-03)' % left)
    manifest = {
        'formatVersion': 1,
        'libraryId': ids['libraryId'],
        'version': package_version(version),
        'title': lib['name'],
        'description': lib['description'],
        'created': ids['created'],
        'modified': archive['created'],
        'license': {'id': lib['license']['id'], 'summary': lib['license']['summary'], 'text': license_text},
        'maintainer': lib['maintainer'],
        'sets': sets,
    }
    note = changes_note(args.repo, archive['revision'], version)
    if note:
        manifest['changes'] = note
    tags = test_package.tags_from(lib, notes)
    if tags:
        manifest['tags'] = tags
    for field, limit in (('title', 80), ('description', 1000)):
        if len(manifest[field]) > limit:
            raise SystemExit('error: %s is longer than %d characters (FDS 4.1)' % (field, limit))
    if len(manifest['license']['summary']) > 200 or len(license_text) > 32000:
        raise SystemExit('error: licence summary or text too long for a manifest (FDS 4.1)')

    files = {'songs/%s/%s.cho' % (s, s): b for s, b in songs.items()}
    files.update(builder.view_files(manifest))
    data, sig = builder.signed(manifest, files, seed, name=author)
    files['manifest.json'] = data
    files['manifest.sig'] = sig

    stamp = datetime.datetime.strptime(archive['created'], '%Y-%m-%dT%H:%M:%SZ')
    folder = re.sub(r'[<>:"/\\|?*()]', '', manifest['title']).strip()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        for name in sorted(files, key=lambda n: (n not in ('manifest.json', 'manifest.sig'), n.encode('utf-8'))):
            info = zipfile.ZipInfo('%s/%s' % (folder, name), date_time=stamp.timetuple()[:6])
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            zf.writestr(info, files[name], compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    out = args.out or os.path.join(args.repo, 'dist', '%s-%s-pakket.zbl' % (lib['id'], version))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, 'wb') as fh:
        fh.write(buf.getvalue())

    print('wrote %s: %d bytes' % (out, len(buf.getvalue())))
    print('  libraryId %s, version %d, %d songs; sets: %s' % (
        manifest['libraryId'], manifest['version'], len(songs),
        ', '.join('%s (%d)' % (s['name'], len(s['songs'])) for s in sets) or 'none'))
    print('  tag labels: %s' % ('%d tags, %d labels' % (len(tags), sum(len(v) for v in tags.values()))
                                if tags else 'none'))
    print('  changes: %s' % ('%d characters' % len(note) if note else 'none (no changelog summary)'))
    print('  signed by %s, fingerprint %s' % (author, builder.fingerprint(builder.public_key(seed))))
    for n in notes:
        print('note: ' + n)
    return 0


if __name__ == '__main__':
    sys.exit(main())
