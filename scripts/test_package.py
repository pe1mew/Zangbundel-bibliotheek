#!/usr/bin/env python3
"""Build a library package of a release archive, for testing only. Never publish the result.

A library package is the second library format, defined by the library manager's FDS
(`Zangbundel-bibliotheek-manager/design/FDS.md`) and song format 12.11. This library is published
as release archives, not as a package. A package needs a UUID library id, so it would be a
different library on every phone, and it has no release index, so phones would no longer find
updates. This script makes a package of the same songs, so the app's package reader and the
library manager can be tried with real content:

- the songs of the archive, as `songs/<id>/<id>.cho`;
- each setlist of the archive as a set. Title-only entries (`? title`) are left out and
  reported, because a set lists song ids only;
- the 1.1 view the FDS requires (`zangbundel.json`, `LICENSE`, `setlists/set-<n>.zbs`);
- a manifest with a test id and a title ending in "(testpakket)", so it sits next to the real
  library on a phone;
- a signature with the public RFC 8032 test key: anyone can check it, and anyone can sign with it.

Usage:
    python scripts/release.py build --tag v2026.11.0
    python scripts/test_package.py dist/zangbundel-bibliotheek-2026.11.0.zbl

The package is written to `dist/<library id>-testpakket.zbl`, which `.gitignore` keeps out of git.
The script uses `make_test_libraries.py` of the library manager repository for the view, the
files list and Ed25519 signing, so both build packages the same way. By default it looks for that
repository next to this one; `--manager` names another place. Output is deterministic.

Check the result with `python scripts/release.py verify <package>` (the format 1.1 side). For the
package side, use the library manager's engine (`webapp/src/core/validate.js`).

Standard library only. Python 3.8 or newer.

Copyright 2026 Remko Welling, PE1MEW.
Licensed under the Apache License 2.0 with the Commons Clause condition; see
scripts/LICENSE and license.md.
"""

import argparse
import importlib.util
import io
import json
import os
import re
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_LIBRARY_ID = 'b7a3e2d4-5c6f-4a8b-9d0e-1f2a3b4c5d6e'   # UUID v4 form, used for this test package only
DATE = '2026-11-07T12:00:00Z'


def load_builder(manager):
    path = os.path.join(manager, 'test-libraries', 'make_test_libraries.py')
    if not os.path.isfile(path):
        raise SystemExit('error: %s not found; give the library manager repository with --manager' % path)
    spec = importlib.util.spec_from_file_location('make_test_libraries', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._selftest()
    return module


def read_archive(path):
    """Library file, licence text, songs by id and setlists from a release archive or snapshot."""
    z = zipfile.ZipFile(path)
    names = [n for n in z.namelist() if not n.endswith('/')]
    root = '' if 'zangbundel.json' in names else names[0].split('/')[0] + '/'
    lib = json.loads(z.read(root + 'zangbundel.json'))
    license_text = z.read(root + lib['license']['file']).decode('utf-8')
    songs, setlists = {}, []
    for name in sorted(names):
        rel = name[len(root):]
        if rel.startswith('songs/') and rel.endswith('.cho'):
            song_id = rel.rsplit('/', 1)[1][:-4]
            if song_id in songs:
                raise SystemExit('error: song id %s occurs twice' % song_id)
            songs[song_id] = z.read(name)
        elif rel.startswith('setlists/') and rel.endswith('.zbs'):
            setlists.append((rel, z.read(name).decode('utf-8')))
    return lib, license_text, songs, setlists


def sets_from(setlists, lib_id, songs, notes):
    sets = []
    for rel, text in setlists:
        title = re.search(r'^\{title:\s*(.*?)\}\s*$', text, re.M).group(1)
        entries = []
        for line in text.splitlines():
            line = line.split(' #', 1)[0].strip()
            if not line or line.startswith('#') or line.startswith('{'):
                continue
            if line.startswith('? '):
                notes.append('%s: title-only entry "%s" left out (a set lists song ids only)' % (rel, line[2:]))
                continue
            entry_lib, _, song_id = line.partition('/')
            if entry_lib != lib_id or song_id not in songs:
                notes.append('%s: entry %s left out (not a song of this library)' % (rel, line))
                continue
            entries.append(song_id)
        sets.append({'name': title, 'songs': entries})
    return sets


def main(argv=None):
    parser = argparse.ArgumentParser(description='Build a library package of a release archive, for testing only.')
    parser.add_argument('archive', help='release archive (.zbl) or snapshot (.zip) of this library')
    parser.add_argument('--manager', default=os.path.join(os.path.dirname(REPO), 'Zangbundel-bibliotheek-manager'),
                        help='library manager repository (default: next to this repository)')
    parser.add_argument('--out', help='output file (default: dist/<library id>-testpakket.zbl)')
    args = parser.parse_args(argv)

    builder = load_builder(args.manager)
    lib, license_text, songs, setlists = read_archive(args.archive)
    notes = []
    manifest = {
        'formatVersion': 1,
        'libraryId': TEST_LIBRARY_ID,
        'version': 1,
        'title': '%s (testpakket)' % lib['name'],
        'description': lib['description'],
        'created': DATE,
        'modified': DATE,
        'changes': 'Testpakket van %s, niet gepubliceerd.' % os.path.basename(args.archive),
        'license': {'id': lib['license']['id'], 'summary': lib['license']['summary'], 'text': license_text},
        'maintainer': lib['maintainer'],
        'sets': sets_from(setlists, lib['id'], songs, notes),
    }
    for field, limit in (('title', 80), ('description', 1000)):
        if len(manifest[field]) > limit:
            raise SystemExit('error: %s is longer than %d characters (FDS 4.1)' % (field, limit))
    if len(manifest['license']['summary']) > 200 or len(license_text) > 32000:
        raise SystemExit('error: licence summary or text too long for a manifest (FDS 4.1)')

    files = {'songs/%s/%s.cho' % (s, s): b for s, b in songs.items()}
    files.update(builder.view_files(manifest))
    data, sig = builder.signed(manifest, files, builder.TEST_SEED)
    files['manifest.json'] = data
    files['manifest.sig'] = sig

    folder = re.sub(r'[<>:"/\\|?*()]', '', manifest['title']).strip()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        for name in sorted(files, key=lambda n: (n not in ('manifest.json', 'manifest.sig'), n.encode('utf-8'))):
            info = zipfile.ZipInfo('%s/%s' % (folder, name), date_time=builder.ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            zf.writestr(info, files[name], compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    out = args.out or os.path.join(REPO, 'dist', '%s-testpakket.zbl' % lib['id'])
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, 'wb') as fh:
        fh.write(buf.getvalue())

    print('wrote %s: %d bytes' % (out, len(buf.getvalue())))
    print('  %d songs; sets: %s' % (len(songs), ', '.join('%s (%d)' % (s['name'], len(s['songs']))
                                                           for s in manifest['sets']) or 'none'))
    print('  test id %s, signed with the RFC 8032 test key, fingerprint %s' % (
        TEST_LIBRARY_ID, builder.fingerprint(builder.public_key(builder.TEST_SEED))))
    for note in notes:
        print('note: ' + note)
    print('For testing only: never publish this file.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
