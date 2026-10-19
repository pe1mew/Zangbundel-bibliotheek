#!/usr/bin/env python3
"""Build, verify and index Zangbundel release archives (.zbl).

Implements section 12 of the song-format specification (Zangbundel app
repository, design/song-format.md, format 1.0, archive format 1.0).

Usage:
    python scripts/release.py build  --tag v2026.10.0 [--out dist] [--repository URL]
                                     [--previous VERSION:REVISION]
    python scripts/release.py build  --version 2026.10.0 --allow-untagged ...
    python scripts/release.py verify dist/<library id>-<version>.zbl
    python scripts/release.py index  dist/<library id>-<version>.zbl [--tag TAG] [--url URL]
                                     [--index releases.json]

`build` reads the tree of the tagged commit from the git object store (never
the working tree), validates it with validate.py, writes the manifest and the
archive deterministically (sorted entries, manifest first, modification times
from the commit time, fixed deflate level, no extra fields), so that two builds
of the same revision are byte-identical. With --allow-untagged it builds from
HEAD under the version given, for a tag that will be placed on HEAD.

`verify` applies the archive checks A001-A012 and A101 of section 12.8 to an
archive and runs the library validator on its contents.

`index` adds or replaces the archive's entry in the release index
(releases.json, section 12.6), newest first.

Standard library only. Python 3.8 or newer. Git must be on the PATH for build.

Copyright 2026 Remko Welling, PE1MEW.
Licensed under the Apache License 2.0 with the Commons Clause condition; see
scripts/LICENSE and license.md.
"""

import argparse
import datetime
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate  # noqa: E402

BUILDER = 'zangbundel-release 1.1.0'
ARCHIVE_VERSION = '1.0'
ARCHIVE_VERSION_WITH_SETLISTS = '1.1'
ARCHIVE_MAJOR_SUPPORTED = 1
MANIFEST_NAME = 'zangbundel-archive.json'
DEFLATE_LEVEL = 9

MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
WARN_ARCHIVE_BYTES = 16 * 1024 * 1024
MAX_ENTRIES = 10000
MAX_UNCOMPRESSED = 256 * 1024 * 1024
MAX_RATIO = 20
MAX_NAME_BYTES = 255

REVISION_RE = re.compile(r'^[0-9a-f]{40}(?:[0-9a-f]{24})?$')
CREATED_RE = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$')
UTF8_FLAG = 0x800


class ReleaseError(Exception):
    pass


# ---------------------------------------------------------------------------
# git helpers
# ---------------------------------------------------------------------------

def git(*args, cwd=None, binary=False):
    result = subprocess.run(['git'] + list(args), cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise ReleaseError('git %s failed: %s' % (' '.join(args), result.stderr.decode('utf-8', 'replace').strip()))
    return result.stdout if binary else result.stdout.decode('utf-8').strip()


def repository_url(repo_dir):
    """HTTPS URL of origin, derived from the remote URL; empty when there is no origin."""
    try:
        url = git('remote', 'get-url', 'origin', cwd=repo_dir)
    except ReleaseError:
        return ''
    m = re.match(r'^(?:git@|ssh://git@)([^:/]+)[:/](.+?)(?:\.git)?/?$', url)
    if m:
        return 'https://%s/%s' % (m.group(1), m.group(2))
    m = re.match(r'^https?://(.+?)(?:\.git)?/?$', url)
    if m:
        return 'https://' + m.group(1)
    return url


def export_tree(repo_dir, revision, dest):
    """Writes every blob of the revision's tree under dest, using the git object store."""
    listing = git('ls-tree', '-r', '-z', revision, cwd=repo_dir, binary=True)
    paths = []
    for item in listing.split(b'\0'):
        if not item:
            continue
        meta, path = item.split(b'\t', 1)
        mode, kind, _ = meta.decode('ascii').split(' ')
        path = path.decode('utf-8')
        if kind != 'blob':
            continue
        if mode == '120000':
            raise ReleaseError('symbolic link in the repository tree: %s' % path)
        data = git('show', '%s:%s' % (revision, path), cwd=repo_dir, binary=True)
        full = os.path.join(dest, *path.split('/'))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, 'wb') as fh:
            fh.write(data)
        paths.append(path)
    return paths


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def manifest_json(manifest):
    return (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def dos_time(epoch):
    t = datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc)
    year = max(1980, t.year)
    return (year, t.month, t.day, t.hour, t.minute, t.second - t.second % 2)


class Utf8ZipInfo(zipfile.ZipInfo):
    """ZipInfo that always writes the name as UTF-8 with general-purpose flag bit 11 set (12.2).

    zipfile sets the flag only for non-ASCII names and resets flag_bits while
    writing, so the encoder hook is the one place where it sticks for both the
    local header and the central directory.
    """

    def _encodeFilenameFlags(self):
        return self.filename.encode('utf-8'), self.flag_bits | UTF8_FLAG


def add_entry(zf, name, data, date_time):
    info = Utf8ZipInfo(name, date_time=date_time)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3            # Unix, fixed for determinism
    info.external_attr = (0o100644 << 16)
    zf.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=DEFLATE_LEVEL)


def build(args):
    repo_dir = args.repo
    git('rev-parse', '--git-dir', cwd=repo_dir)

    if args.tag:
        tag = args.tag
        try:
            revision = git('rev-parse', '--verify', 'refs/tags/%s^{commit}' % tag, cwd=repo_dir)
        except ReleaseError:
            if not args.allow_untagged:
                raise ReleaseError('tag "%s" does not exist; create it first, or build from HEAD with '
                                   '--allow-untagged' % tag)
            revision = git('rev-parse', '--verify', 'HEAD^{commit}', cwd=repo_dir)
            print('note: tag %s does not exist yet; building from HEAD %s' % (tag, revision))
        version = args.version or (tag[1:] if tag.startswith('v') else tag)
    elif args.version:
        if not args.allow_untagged:
            raise ReleaseError('--version without --tag needs --allow-untagged (build from HEAD)')
        version = args.version
        tag = 'v' + version
        revision = git('rev-parse', '--verify', 'HEAD^{commit}', cwd=repo_dir)
        print('note: building from HEAD %s for tag %s' % (revision, tag))
    else:
        raise ReleaseError('give --tag or --version')
    if len(version) > 32:
        raise ReleaseError('version "%s" is longer than 32 characters' % version)

    commit_time = int(git('show', '-s', '--format=%ct', revision, cwd=repo_dir))
    created = datetime.datetime.fromtimestamp(commit_time, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    repo_url = args.repository or repository_url(repo_dir)

    with tempfile.TemporaryDirectory() as tmp:
        tree_paths = export_tree(repo_dir, revision, tmp)
        report, lib, songs, setlists = validate.run(tmp)
        report.print(sys.stdout, args.info)
        if lib is None or validate.library_errors(report):
            raise ReleaseError('library-level errors; nothing built')

        entries = {}  # archive name -> bytes

        # Library metadata and licence, byte-identical to the repository (12.3).
        with open(os.path.join(tmp, 'zangbundel.json'), 'rb') as fh:
            entries['zangbundel.json'] = fh.read()
        license_file = lib['license']['file']
        with open(os.path.join(tmp, *license_file.split('/')), 'rb') as fh:
            entries[license_file] = fh.read()
        if 'README.md' in tree_paths:
            with open(os.path.join(tmp, 'README.md'), 'rb') as fh:
                entries['README.md'] = fh.read()

        included, skipped, notation = [], [], []
        for song in songs:
            if song.skipped:
                first = next((f for f in report.findings if f[0] == song.path and f[2] == 'error'), None)
                skipped.append({'path': song.path,
                                'code': first[3] if first else 'S000',
                                'message': first[4] if first else 'skipped'})
                continue
            with open(os.path.join(tmp, *song.path.split('/')), 'rb') as fh:
                canonical, _ = validate.canonicalise(fh.read())
            entries[song.path] = canonical
            included.append({'path': song.path, 'id': song.meta['id'][0],
                             'hash': hashlib.sha256(canonical).digest()[:16].hex(),
                             'size': len(canonical)})
            if 'notation' in song.meta:
                npath = song.meta['notation'][0]
                full = os.path.join(tmp, *npath.split('/'))
                if os.path.isfile(full) and npath not in entries:
                    with open(full, 'rb') as fh:
                        data = fh.read()
                    entries[npath] = data
                    notation.append({'path': npath, 'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)})
        if not included:
            raise ReleaseError('no song passed validation; nothing built')
        included.sort(key=lambda e: e['path'])
        skipped.sort(key=lambda e: e['path'])
        notation.sort(key=lambda e: e['path'])

        # Setlists (section 13.7): valid ones go in canonical form and into the manifest; archive 1.1.
        setlist_entries = []
        for sl in setlists:
            if sl.skipped:
                first = next((f for f in report.findings if f[0] == sl.path and f[2] == 'error'), None)
                skipped.append({'path': sl.path, 'code': first[3] if first else 'SL000',
                                'message': first[4] if first else 'skipped'})
                continue
            entries[sl.path] = sl.canonical
            setlist_entries.append({'path': sl.path, 'id': sl.meta['id'][0], 'title': sl.meta['title'][0],
                                    'songs': len(sl.entries), 'sha256': hashlib.sha256(sl.canonical).hexdigest(),
                                    'size': len(sl.canonical)})
        setlist_entries.sort(key=lambda e: e['path'])
        skipped.sort(key=lambda e: e['path'])

        manifest = {
            'format': 'zangbundel-archive',
            'archive_version': ARCHIVE_VERSION_WITH_SETLISTS if setlist_entries else ARCHIVE_VERSION,
            'library': lib['id'],
            'format_version': lib['format_version'],
            'version': version,
            'revision': revision,
            'created': created,
            'source': {'repository': repo_url, 'ref': tag},
            'songs': included,
            'skipped': skipped,
        }
        if notation:
            manifest['notation'] = notation
        if setlist_entries:
            manifest['setlists'] = setlist_entries
        manifest['builder'] = BUILDER
        if args.previous:
            pv, _, pr = args.previous.partition(':')
            if not pv or not REVISION_RE.match(pr):
                raise ReleaseError('--previous must be VERSION:REVISION with a full commit hash')
            manifest['previous'] = {'version': pv, 'revision': pr}

    date_time = dos_time(commit_time)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        add_entry(zf, MANIFEST_NAME, manifest_json(manifest), date_time)
        for name in sorted(entries):
            add_entry(zf, name, entries[name], date_time)
    data = buf.getvalue()

    os.makedirs(args.out, exist_ok=True)
    file_name = '%s-%s.zbl' % (lib['id'], version)
    out_path = os.path.join(args.out, file_name)
    with open(out_path, 'wb') as fh:
        fh.write(data)
    digest = hashlib.sha256(data).hexdigest()

    notes_path = os.path.join(args.out, 'release-notes.md')
    with open(notes_path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('Zangbundel library **%s** release %s\n\n' % (lib['name'], version))
        fh.write('| | |\n|---|---|\n')
        fh.write('| Library id | `%s` |\n' % lib['id'])
        fh.write('| Revision | `%s` |\n' % revision)
        fh.write('| Created | %s |\n' % created)
        fh.write('| Songs | %d included, %d skipped |\n' % (len(included), len(skipped)))
        if setlist_entries:
            fh.write('| Setlists | %d |\n' % len(setlist_entries))
        fh.write('| Archive | `%s`, %d bytes |\n' % (file_name, len(data)))
        fh.write('| SHA-256 | `%s` |\n\n' % digest)
        fh.write('Open the `.zbl` file with the Zangbundel app, or add the library by its repository URL.\n')
        if skipped:
            fh.write('\nSkipped songs:\n\n')
            for s in skipped:
                fh.write('- `%s`: %s %s\n' % (s['path'], s['code'], s['message']))

    print('built %s: %d bytes, sha256 %s' % (out_path, len(data), digest))
    print('  version %s, revision %s, created %s, %d song(s), %d skipped' %
          (version, revision, created, len(included), len(skipped)))
    print('  release notes: %s' % notes_path)
    return 0


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------

def check_entry_name(name):
    raw = name.encode('utf-8')
    if len(raw) > MAX_NAME_BYTES:
        return 'name longer than 255 bytes'
    if name.startswith('/') or '\\' in name:
        return 'absolute name or backslash'
    if re.match(r'^[A-Za-z]:', name):
        return 'drive letter'
    parts = name.split('/')
    if any(p in ('', '.', '..') for p in parts):
        return '"." or ".." component or empty component'
    return None


def verify(args):
    path = args.archive
    report = validate.Report()
    name = os.path.basename(path)
    size = os.path.getsize(path)

    if size > MAX_ARCHIVE_BYTES:
        report.error(name, None, 'A002', 'archive is %d bytes, larger than 64 MiB' % size)
        return finish_verify(report, args)
    if size > WARN_ARCHIVE_BYTES:
        report.warning(name, None, 'A101', 'archive is %d bytes, larger than 16 MiB' % size)
    if not zipfile.is_zipfile(path):
        report.error(name, None, 'A001', 'not a ZIP file')
        return finish_verify(report, args)

    zf = zipfile.ZipFile(path)
    infos = zf.infolist()
    if len(infos) > MAX_ENTRIES:
        report.error(name, None, 'A002', '%d entries, more than %d' % (len(infos), MAX_ENTRIES))
        return finish_verify(report, args)
    seen = set()
    files = {}
    uncompressed = compressed = 0
    for info in infos:
        if info.is_dir():
            continue
        problem = check_entry_name(info.filename)
        if problem:
            report.error(name, None, 'A006', 'entry "%s": %s' % (info.filename, problem))
        key = info.filename.lower()
        if key in seen:
            report.error(name, None, 'A006', 'entry "%s" duplicates another (case-insensitive)' % info.filename)
        seen.add(key)
        if info.flag_bits & 0x1:
            report.error(name, None, 'A004', 'entry "%s" is encrypted' % info.filename)
        if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            report.error(name, None, 'A004', 'entry "%s" uses compression method %d' %
                         (info.filename, info.compress_type))
        mode = (info.external_attr >> 16) & 0o170000
        if info.create_system == 3 and mode not in (0, 0o100000):
            report.error(name, None, 'A005', 'entry "%s" is not a regular file' % info.filename)
        uncompressed += info.file_size
        compressed += info.compress_size
        files[info.filename] = info
    if uncompressed > MAX_UNCOMPRESSED or (compressed and uncompressed > MAX_RATIO * compressed):
        report.error(name, None, 'A003', 'uncompressed total %d bytes exceeds the limits (compressed %d)' %
                     (uncompressed, compressed))
    if validate.library_errors(report):
        return finish_verify(report, args)

    if 'zangbundel.json' not in files:
        top = {n.split('/')[0] for n in files}
        if len(top) == 1 and ('%s/zangbundel.json' % next(iter(top))) in files:
            report.warning(name, None, 'A102', 'repository snapshot (single top-level directory, no manifest): '
                           'revision unknown, no update checks')
        else:
            report.error(name, None, 'A001', 'no zangbundel.json at the archive root')
        return finish_verify(report, args)
    if MANIFEST_NAME not in files:
        report.warning(name, None, 'A102', 'repository snapshot without manifest: revision unknown, no update checks')
        manifest = None
    else:
        try:
            manifest = json.loads(zf.read(MANIFEST_NAME).decode('utf-8'))
        except (UnicodeDecodeError, ValueError) as exc:
            report.error(MANIFEST_NAME, None, 'A007', 'not valid JSON: %s' % exc)
            return finish_verify(report, args)
        if not isinstance(manifest, dict):
            report.error(MANIFEST_NAME, None, 'A007', 'top level is not an object')
            return finish_verify(report, args)
        for field, typ in (('format', str), ('archive_version', str), ('library', str), ('format_version', str),
                           ('version', str), ('revision', str), ('created', str), ('source', dict),
                           ('songs', list)):
            if not isinstance(manifest.get(field), typ):
                report.error(MANIFEST_NAME, None, 'A007', 'field "%s" is missing or has the wrong type' % field)
        if validate.library_errors(report):
            return finish_verify(report, args)
        if manifest['format'] != 'zangbundel-archive':
            report.error(MANIFEST_NAME, None, 'A007', 'format is "%s"' % manifest['format'])
        m = re.match(r'^(\d+)\.(\d+)$', manifest['archive_version'])
        if not m:
            report.error(MANIFEST_NAME, None, 'A007', 'archive_version "%s" is not major.minor' %
                         manifest['archive_version'])
        elif int(m.group(1)) != ARCHIVE_MAJOR_SUPPORTED:
            report.error(MANIFEST_NAME, None, 'A008', 'archive_version %s is not supported; update the app' %
                         manifest['archive_version'])
        if not REVISION_RE.match(manifest['revision']):
            report.error(MANIFEST_NAME, None, 'A010', 'revision "%s" is malformed' % manifest['revision'])
        if not CREATED_RE.match(manifest['created']):
            report.error(MANIFEST_NAME, None, 'A010', 'created "%s" is not RFC 3339 UTC' % manifest['created'])
        if len(manifest['version']) > 32:
            report.error(MANIFEST_NAME, None, 'A007', 'version longer than 32 characters')
        for field in ('repository', 'ref'):
            if not isinstance(manifest['source'].get(field), str):
                report.error(MANIFEST_NAME, None, 'A007', 'source.%s is missing' % field)
        try:
            lib = json.loads(zf.read('zangbundel.json').decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            lib = {}
        if manifest['library'] != lib.get('id'):
            report.error(MANIFEST_NAME, None, 'A009', 'manifest library "%s" differs from zangbundel.json id "%s"' %
                         (manifest['library'], lib.get('id')))
        if manifest['format_version'] != lib.get('format_version'):
            report.error(MANIFEST_NAME, None, 'A009', 'format_version differs between manifest and zangbundel.json')

        listed = {}
        for entry in manifest['songs']:
            if not isinstance(entry, dict) or not all(isinstance(entry.get(k), t) for k, t in
                                                      (('path', str), ('id', str), ('hash', str), ('size', int))):
                report.error(MANIFEST_NAME, None, 'A007', 'malformed songs entry: %r' % (entry,))
                continue
            listed[entry['path']] = entry
            if entry['path'] not in files:
                report.error(MANIFEST_NAME, None, 'A012', 'listed song "%s" is missing from the archive' %
                             entry['path'])
                continue
            data = zf.read(entry['path'])
            canonical, deviations = validate.canonicalise(data)
            if deviations:
                report.error(entry['path'], None, 'A011', 'song entry is not canonical: %s' % ', '.join(deviations))
            digest = hashlib.sha256(data).digest()[:16].hex()
            if digest != entry['hash'] or len(data) != entry['size']:
                report.error(entry['path'], None, 'A012', 'content hash or size differs from the manifest')
        for fname in files:
            if fname.startswith('songs/') and fname.endswith('.cho') and fname not in listed:
                report.error(fname, None, 'A012', '.cho entry under songs/ is not listed in the manifest')
        for entry in manifest.get('notation', []) or []:
            if isinstance(entry, dict) and entry.get('path') in files:
                if hashlib.sha256(zf.read(entry['path'])).hexdigest() != entry.get('sha256'):
                    report.warning(entry['path'], None, 'A103', 'notation sha256 does not match; file dropped')
        for entry in manifest.get('setlists', []) or []:
            if not isinstance(entry, dict) or not isinstance(entry.get('path'), str):
                report.error(MANIFEST_NAME, None, 'A007', 'malformed setlists entry: %r' % (entry,))
            elif entry['path'] not in files:
                report.warning(entry['path'], None, 'A104', 'listed setlist is missing; dropped')
            elif hashlib.sha256(zf.read(entry['path'])).hexdigest() != entry.get('sha256'):
                report.warning(entry['path'], None, 'A104', 'setlist sha256 does not match; dropped')

    # Validate the contents like a git import (12.7 step 5).
    with tempfile.TemporaryDirectory() as tmp:
        prefix = ''
        if 'zangbundel.json' not in files:
            prefix = next(iter({n.split('/')[0] for n in files})) + '/'
        for fname, info in files.items():
            if not fname.startswith(prefix):
                continue
            rel = fname[len(prefix):]
            if not rel:
                continue
            full = os.path.join(tmp, *rel.split('/'))
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, 'wb') as fh:
                fh.write(zf.read(info))
        inner, lib_obj, songs, setlists = validate.run(tmp)
        report.findings.extend(inner.findings)
        if manifest is not None:
            for s in manifest.get('skipped', []) or []:
                if isinstance(s, dict):
                    report.info(s.get('path', '?'), None, s.get('code', 'S000'),
                                'skipped at build time: %s' % s.get('message', ''))
        for song in songs:
            status = 'SKIPPED' if song.skipped else 'OK'
            print('%s: %s hash=%s lines=%d' % (song.path, status, song.hash_hex or '-', len(song.lines)))
        for sl in setlists:
            status = 'SKIPPED' if sl.skipped else 'OK'
            print('%s: %s hash=%s entries=%d' % (sl.path, status, sl.hash_hex or '-', len(sl.entries)))
    return finish_verify(report, args)


def finish_verify(report, args):
    report.print(sys.stdout, args.info)
    errors = validate.library_errors(report)
    skipped = [f for f in report.findings if f[2] == 'error' and f[3].startswith('S')]
    warnings = report.count('warning')
    if errors:
        print('Archive refused: %d error(s).' % len(errors))
        return 1
    print('Archive accepted, %d warning(s)%s.' % (warnings, ', %d song(s) with errors' % len(skipped) if skipped else ''))
    if skipped:
        return 1
    return 1 if (args.strict and warnings) else 0


# ---------------------------------------------------------------------------
# index
# ---------------------------------------------------------------------------

def index(args):
    path = args.archive
    with open(path, 'rb') as fh:
        data = fh.read()
    zf = zipfile.ZipFile(io.BytesIO(data))
    manifest = json.loads(zf.read(MANIFEST_NAME).decode('utf-8'))
    file_name = os.path.basename(path)
    tag = args.tag or manifest['source']['ref']
    url = args.url
    if not url:
        repo = manifest['source']['repository'] or repository_url(args.repo)
        if not repo:
            raise ReleaseError('no repository URL known; give --url')
        url = '%s/releases/download/%s/%s' % (repo.rstrip('/'), tag, file_name)

    index_path = args.index
    if os.path.exists(index_path):
        with open(index_path, 'rb') as fh:
            doc = json.loads(fh.read().decode('utf-8'))
        if doc.get('format') != 'zangbundel-releases' or doc.get('library') != manifest['library']:
            raise ReleaseError('%s is not the release index of library "%s"' % (index_path, manifest['library']))
    else:
        doc = {'format': 'zangbundel-releases', 'library': manifest['library'], 'releases': []}

    entry = {
        'version': manifest['version'],
        'revision': manifest['revision'],
        'created': manifest['created'],
        'url': url,
        'size': len(data),
        'sha256': hashlib.sha256(data).hexdigest(),
    }
    releases = [r for r in doc.get('releases', []) if r.get('revision') != entry['revision']]
    releases.append(entry)
    releases.sort(key=lambda r: r.get('created', ''), reverse=True)
    doc = {'format': 'zangbundel-releases', 'library': manifest['library'], 'releases': releases}
    with open(index_path, 'wb') as fh:
        fh.write((json.dumps(doc, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print('%s: %d release(s), newest %s (%s)' % (index_path, len(releases), releases[0]['version'],
                                                 releases[0]['revision'][:12]))
    return 0


# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description='Build, verify and index Zangbundel release archives (.zbl).')
    sub = parser.add_subparsers(dest='command', required=True)

    b = sub.add_parser('build', help='build the archive of a tagged revision')
    b.add_argument('--tag', help='git tag to build (e.g. v2026.10.0)')
    b.add_argument('--version', help='release version; default: the tag without a leading "v"')
    b.add_argument('--allow-untagged', action='store_true',
                   help='build from HEAD when the tag does not exist yet (the tag must then be placed on HEAD)')
    b.add_argument('--repository', help='HTTPS URL of the repository for the manifest; default: from origin')
    b.add_argument('--previous', metavar='VERSION:REVISION', help='the release before this one')
    b.add_argument('--repo', default='.', help='repository directory (default: current directory)')
    b.add_argument('--out', default='dist', help='output directory (default: dist)')
    b.add_argument('--info', action='store_true', help='print informational validator findings')

    v = sub.add_parser('verify', help='check an archive as the app would')
    v.add_argument('archive')
    v.add_argument('--strict', action='store_true', help='exit non-zero on warnings too')
    v.add_argument('--info', action='store_true', help='print informational findings')

    i = sub.add_parser('index', help='add the archive to the release index')
    i.add_argument('archive')
    i.add_argument('--index', default='releases.json', help='release index file (default: releases.json)')
    i.add_argument('--tag', help='release tag used in the download URL; default: the manifest ref')
    i.add_argument('--url', help='archive URL; default: GitHub release asset URL from the manifest repository')
    i.add_argument('--repo', default='.', help='repository directory, for the origin URL (default: current directory)')

    args = parser.parse_args(argv)
    try:
        return {'build': build, 'verify': verify, 'index': index}[args.command](args)
    except ReleaseError as exc:
        print('error: %s' % exc, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
