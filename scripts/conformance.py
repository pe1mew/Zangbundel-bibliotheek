#!/usr/bin/env python3
"""Run the shared conformance corpus against this repository's validator and release tool.

The Zangbundel app keeps a corpus of test vectors with the result the format specification
requires for each: song files, setlists, library files (zangbundel.json) and archives. The app's
own tests read the same files. Running them here as well keeps the two implementations of the
format, this repository's Python tools and the app's Kotlin code, in agreement (app architecture
A-21, A-22). The corpus lives in the app repository:

    android/core/testing/src/main/resources/conformance/

Usage:
    python scripts/conformance.py <path to the conformance folder>

What is compared, per kind of vector:

    songs      verdict, report codes, content hash and canonical line list of the song alone.
               Findings that need the whole library (tag labels, variant groups) are not part of
               a song vector and are not produced here.
    setlists   verdict and report codes, checked against the songs that library-state.json lists
               for the vector's library. A vector without a library is checked as a setlist of an
               otherwise empty library; I004 (entry of another library) is then left out, because
               the validator only knows setlists inside a library. How entries resolve against
               installed libraries is app behaviour (section 13.5) and is not compared.
    libraries  verdict and report codes of zangbundel.json, for the app version the vector names.
    archives   verdict, and every code the vector expects must be among the codes reported. The
               release tool may report more findings after the first error; the app may stop
               earlier, which the specification allows.
    packages   the library manager's shared test libraries (its FDS O-04), as an app that reads
               only format 1.1 sees them: through the package's 1.1 view (song format 12.5). The
               verdict and the codes of `format_1_1` in each expected.json, compared as for archives.
               The package side (FDS rules, signature) is for the app and the manager, not for
               these tools.

Validator-only codes (W014) are left out of every comparison: the app never reports them.

Every vector's expected.json may carry the SHA-256 of the vector; a changed vector is reported.
Exit code 0 when everything agrees, 1 otherwise. Standard library only, Python 3.8 or newer.

Copyright 2026 Remko Welling, PE1MEW.
Licensed under the Apache License 2.0 with the Commons Clause condition; see
scripts/LICENSE and license.md.
"""

import argparse
import contextlib
import hashlib
import io
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import release  # noqa: E402
import validate  # noqa: E402

# Codes the validator reports and the app never does, so a vector cannot expect them (song format
# v0.25: W014, a "#" line with spaces or tabs before it). They are left out of every comparison.
VALIDATOR_ONLY = {'W014'}
FINDING = re.compile(r'^(\S+?)(?::\d+)? (ERROR|WARNING|INFO) (\S+) ')
LIBRARY = {
    'format': 'zangbundel-library', 'format_version': '1.1', 'id': '', 'name': 'Conformance',
    'description': 'Conformance vectors', 'maintainer': {'name': 'Zangbundel-project'},
    'license': {'id': 'CC0-1.0', 'file': 'LICENSE', 'summary': 'CC0'}, 'min_app_version': '0.1.0',
}


class Checker:
    def __init__(self):
        self.failures = 0
        self.count = 0

    def result(self, kind, name, problems):
        self.count += 1
        if problems:
            self.failures += 1
            print('DIFF %-9s %-28s %s' % (kind, name, '; '.join(problems)))
        else:
            print('ok   %-9s %s' % (kind, name))


def read(path, mode='r'):
    with open(path, mode, **({} if 'b' in mode else {'encoding': 'utf-8'})) as fh:
        return fh.read()


def names(folder):
    return [n for n in read(os.path.join(folder, 'index.txt')).split() if n]


def integrity(expected, data):
    want = expected.get('sha256')
    if want and hashlib.sha256(data).hexdigest() != want:
        return ['vector bytes differ from the SHA-256 in expected.json']
    return []


def codes_of(report):
    return sorted({f[3] for f in report.findings} - VALIDATOR_ONLY)


def check_songs(folder, checker):
    for name in names(folder):
        expected = json.loads(read(os.path.join(folder, name + '.expected.json')))
        data = read(os.path.join(folder, name + '.cho'), 'rb')
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, 'songs'))
            with open(os.path.join(root, 'songs', name + '.cho'), 'wb') as fh:
                fh.write(data)
            report = validate.Report()
            song = validate.validate_song(root, 'songs/%s.cho' % name, report, dict(LIBRARY))
        problems = integrity(expected, data)
        accepted = not song.skipped
        if accepted != expected['accepted']:
            problems.append('verdict %s, expected %s' % (accepted, expected['accepted']))
        if codes_of(report) != sorted(expected['codes']):
            problems.append('codes %s, expected %s' % (codes_of(report), sorted(expected['codes'])))
        if accepted and expected['accepted']:
            if song.hash_hex != expected['hash']:
                problems.append('hash %s, expected %s' % (song.hash_hex, expected['hash']))
            if 'lines' in expected and song.lines != expected['lines']:
                problems.append('line list differs')
        checker.result('song', name, problems)


def check_setlists(folder, checker):
    state = json.loads(read(os.path.join(folder, 'library-state.json')))
    for name in names(folder):
        expected = json.loads(read(os.path.join(folder, name + '.expected.json')))
        data = read(os.path.join(folder, name + '.zbs'), 'rb')
        library = expected.get('library')
        lib = dict(LIBRARY, id=library or 'conformance-only')
        song_ids = {s['id'] for s in state.get(library, [])} if library else set()
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, 'setlists'))
            with open(os.path.join(root, 'setlists', name + '.zbs'), 'wb') as fh:
                fh.write(data)
            report = validate.Report()
            setlist = validate.validate_setlist(root, 'setlists/%s.zbs' % name, report, lib, song_ids)
        problems = integrity(expected, data)
        codes = [c for c in codes_of(report) if library or c != 'I004']
        accepted = not setlist.skipped
        if accepted != expected['accepted']:
            problems.append('verdict %s, expected %s' % (accepted, expected['accepted']))
        if codes != sorted(expected['codes']):
            problems.append('codes %s, expected %s' % (codes, sorted(expected['codes'])))
        checker.result('setlist', name, problems)


def check_libraries(folder, checker):
    for name in names(folder):
        expected = json.loads(read(os.path.join(folder, name + '.expected.json')))
        data = read(os.path.join(folder, name + '.json'), 'rb')
        with tempfile.TemporaryDirectory() as root:
            with open(os.path.join(root, 'zangbundel.json'), 'wb') as fh:
                fh.write(data)
            with open(os.path.join(root, 'LICENSE'), 'w', encoding='utf-8') as fh:
                fh.write('Licence text\n')
            report = validate.Report()
            lib = validate.validate_library_json(root, report, validate.parse_semver(expected['app_version']))
        problems = integrity(expected, data)
        accepted = lib is not None and not validate.library_errors(report)
        if accepted != expected['accepted']:
            problems.append('verdict %s, expected %s' % (accepted, expected['accepted']))
        if codes_of(report) != sorted(expected['codes']):
            problems.append('codes %s, expected %s' % (codes_of(report), sorted(expected['codes'])))
        checker.result('library', name, problems)


def check_archives(folder, checker):
    for name in names(folder):
        expected = json.loads(read(os.path.join(folder, name + '.expected.json')))
        path = os.path.join(folder, name + '.zbl')
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            release.verify(argparse.Namespace(archive=path, info=True, strict=False))
        text = out.getvalue()
        accepted = 'Archive accepted' in text
        codes = sorted({m.group(3) for m in map(FINDING.match, text.splitlines()) if m} - VALIDATOR_ONLY)
        problems = integrity(expected, read(path, 'rb'))
        if accepted == expected['refused']:
            problems.append('verdict %s, expected %s' % ('accepted' if accepted else 'refused',
                                                        'refused' if expected['refused'] else 'accepted'))
        missing = sorted(set(expected['codes']) - set(codes))
        if missing:
            problems.append('expected codes not reported: %s (reported %s)' % (missing, codes))
        checker.result('archive', name, problems)


def verify_archive(path):
    """Run release.py verify on a file; return (accepted, sorted codes)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        release.verify(argparse.Namespace(archive=path, info=True, strict=False))
    text = out.getvalue()
    return 'Archive accepted' in text, sorted({m.group(3) for m in map(FINDING.match, text.splitlines()) if m} - VALIDATOR_ONLY)


def check_packages(folder, checker):
    """Library packages (the library manager's shared test libraries), read as format 1.1 does."""
    for name in names(folder):
        expected = json.loads(read(os.path.join(folder, name + '.expected.json')))
        want = expected['format_1_1']
        path = os.path.join(folder, name + '.zbl')
        accepted, codes = verify_archive(path)
        problems = integrity(expected, read(path, 'rb'))
        want_accepted = want['verdict'] != 'refused'
        if accepted != want_accepted:
            problems.append('verdict %s, expected %s' % ('accepted' if accepted else 'refused', want['verdict']))
        missing = sorted(set(want['codes']) - set(codes))
        if missing:
            problems.append('expected codes not reported: %s (reported %s)' % (missing, codes))
        checker.result('package', name, problems)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Run the Zangbundel conformance corpus against the Python tools.')
    parser.add_argument('corpus', help='path to the conformance folder')
    args = parser.parse_args(argv)
    checker = Checker()
    for kind, check in (('songs', check_songs), ('setlists', check_setlists),
                        ('libraries', check_libraries), ('archives', check_archives),
                        ('packages', check_packages)):
        folder = os.path.join(args.corpus, kind)
        if os.path.isfile(os.path.join(folder, 'index.txt')):
            check(folder, checker)
        else:
            print('note: no %s vectors in this corpus' % kind)
    print('%d vector(s), %d disagreement(s).' % (checker.count, checker.failures))
    if checker.failures:
        release.annotate('error', '%d conformance vector(s) disagree with the Python tools; see the log.' %
                         checker.failures, title='conformance')
    return 1 if checker.failures else 0


if __name__ == '__main__':
    sys.exit(main())
