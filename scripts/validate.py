#!/usr/bin/env python3
"""Validate a Zangbundel song library against the song-format specification 1.0.

Usage:
    python scripts/validate.py [options] <library root>

Applies the library-level, song-level, warning and info rules of section 11.3
of design/song-format.md (Zangbundel app repository), the canonicalisation of
section 8 and the canonical line list of section 9. Prints one line per finding
as

    path:line LEVEL CODE message

(line omitted when not applicable), then one status line per song with its
content hash and canonical line count, then the summary line. Exit status is 1
when any library or song error was found (or any warning with --strict), 2 on a
usage error, 0 otherwise.

Standard library only. Python 3.8 or newer.

Copyright 2026 Remko Welling, PE1MEW.
Licensed under the Apache License 2.0 with the Commons Clause condition; see
scripts/LICENSE and license.md.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import unicodedata

FORMAT_MAJOR_SUPPORTED = 1

ID_RE = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')
LANG_RE = re.compile(r'^[a-zA-Z]{2,3}(-[a-zA-Z0-9]{1,8})*$')
SEMVER_RE = re.compile(r'^(\d+)\.(\d+)\.(\d+)$')
FORMAT_VERSION_RE = re.compile(r'^(\d+)\.(\d+)$')
DIRECTIVE_NAME_RE = re.compile(r'^[a-z_]+$')
TIME_RE = re.compile(r'^\d+(\.\d{1,3})?$')
SYLLABLE_RE = re.compile(r'^\d+(\.\d{1,3})?@\d+$')
CHORD_RE = re.compile(r'\[[^\]]*\]')

MAX_FILE_BYTES = 64 * 1024
RECOMMENDED_FILE_BYTES = 8 * 1024
MAX_TITLE = 60
MAX_LINE = 120
MAX_CANONICAL_LINES = 254

# Setlists (section 13, format 1.1)
SETLIST_MAX_ENTRIES = 200
SETLIST_ENTRY_RE = re.compile(r'^([a-z0-9]+(?:-[a-z0-9]+)*)/([a-z0-9]+(?:-[a-z0-9]+)*)(?:\s+#.*)?$')
SETLIST_TITLE_ENTRY_RE = re.compile(r'^\?\s+(\S.*)$')

# Short forms accepted by the profile (section 5.3, 6, 7).
ALIASES = {
    't': 'title', 'st': 'subtitle',
    'sov': 'start_of_verse', 'eov': 'end_of_verse',
    'soc': 'start_of_chorus', 'eoc': 'end_of_chorus',
    'sob': 'start_of_bridge', 'eob': 'end_of_bridge',
    'sot': 'start_of_tab', 'eot': 'end_of_tab',
    'sog': 'start_of_grid', 'eog': 'end_of_grid',
    'c': 'comment', 'ci': 'comment_italic', 'cb': 'comment_box',
    'ns': 'new_song', 'np': 'new_page',
}

# Standard meta names: {meta: title X} equals {title: X} (section 5.3).
STANDARD_META = {
    'title', 'subtitle', 'artist', 'composer', 'lyricist', 'copyright', 'album',
    'year', 'key', 'time', 'tempo', 'duration', 'capo', 'sorttitle',
}

# Section 6.2: at most once.
SINGLE_VALUED = {
    'id', 'title', 'language', 'subtitle', 'sorttitle', 'copyright', 'license',
    'source', 'melody', 'variant-group', 'redistribute', 'key', 'capo', 'tempo',
    'time', 'duration', 'year', 'album', 'notation',
}
MULTI_VALUED = {'lyricist', 'composer', 'artist', 'tag'}

# Directives that are known and ignored (section 7.4, 7.5, 10.2, 10.3).
KNOWN_IGNORED = {
    'comment', 'comment_italic', 'comment_box',
    'new_page', 'column_break', 'columns', 'titles', 'image',
    'textfont', 'textsize', 'textcolour', 'textcolor',
    'chordfont', 'chordsize', 'chordcolour', 'chordcolor',
    'tabfont', 'tabsize', 'tabcolour', 'tabcolor',
    'transpose', 'define', 'chord',
    'x_zb_time', 'x_zb_syllables',
}

SHOWN_ENVIRONMENTS = {'verse', 'chorus', 'bridge'}
KNOWN_HIDDEN_ENVIRONMENTS = {'tab', 'grid', 'abc'}

# Licence identifiers accepted without W010 (section 6.1, 11.3). SPDX
# identifiers commonly used for song texts, plus the two profile values.
# Any SPDX "LicenseRef-" identifier is accepted too.
KNOWN_LICENSES = {
    'public-domain', 'proprietary',
    'CC0-1.0', 'CC-PDDC',
    'CC-BY-1.0', 'CC-BY-2.0', 'CC-BY-2.5', 'CC-BY-3.0', 'CC-BY-4.0',
    'CC-BY-SA-1.0', 'CC-BY-SA-2.0', 'CC-BY-SA-2.5', 'CC-BY-SA-3.0', 'CC-BY-SA-4.0',
    'CC-BY-NC-1.0', 'CC-BY-NC-2.0', 'CC-BY-NC-2.5', 'CC-BY-NC-3.0', 'CC-BY-NC-4.0',
    'CC-BY-NC-SA-1.0', 'CC-BY-NC-SA-2.0', 'CC-BY-NC-SA-2.5', 'CC-BY-NC-SA-3.0', 'CC-BY-NC-SA-4.0',
    'CC-BY-ND-1.0', 'CC-BY-ND-2.0', 'CC-BY-ND-2.5', 'CC-BY-ND-3.0', 'CC-BY-ND-4.0',
    'CC-BY-NC-ND-1.0', 'CC-BY-NC-ND-2.0', 'CC-BY-NC-ND-2.5', 'CC-BY-NC-ND-3.0', 'CC-BY-NC-ND-4.0',
    'GFDL-1.1', 'GFDL-1.2', 'GFDL-1.3', 'GFDL-1.3-only', 'GFDL-1.3-or-later',
    'MIT', 'Apache-2.0', 'OFL-1.1', 'Unlicense', 'FAL-1.3',
}
LICENSE_REF_RE = re.compile(r'^LicenseRef-[A-Za-z0-9.-]+$')


class Report:
    """Collects findings and prints them in spec order."""

    def __init__(self):
        self.findings = []  # (path, line, level, code, message)

    def add(self, path, line, level, code, message):
        self.findings.append((path, line, level, code, message))

    def error(self, path, line, code, message):
        self.add(path, line, 'error', code, message)

    def warning(self, path, line, code, message):
        self.add(path, line, 'warning', code, message)

    def info(self, path, line, code, message):
        self.add(path, line, 'info', code, message)

    def count(self, level):
        return sum(1 for f in self.findings if f[2] == level)

    def print(self, out, show_info):
        ordered = sorted(self.findings, key=lambda f: (f[0], f[1] or 0))
        for path, line, level, code, message in ordered:
            if level == 'info' and not show_info:
                continue
            where = '%s:%d' % (path, line) if line else path
            out.write('%s %s %s %s\n' % (where, level.upper(), code, message))


def parse_semver(text):
    m = SEMVER_RE.match(text or '')
    return tuple(int(g) for g in m.groups()) if m else None


# ---------------------------------------------------------------------------
# Library level (section 4, codes L001-L008)
# ---------------------------------------------------------------------------

def validate_library_json(root, report, app_version):
    """Returns the parsed zangbundel.json, or None when the library is refused."""
    path = 'zangbundel.json'
    full = os.path.join(root, path)
    if not os.path.isfile(full):
        report.error(path, None, 'L001', 'zangbundel.json missing at the repository root')
        return None
    try:
        with open(full, 'rb') as fh:
            raw = fh.read()
        lib = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, ValueError) as exc:
        report.error(path, None, 'L002', 'not valid JSON: %s' % exc)
        return None
    if not isinstance(lib, dict):
        report.error(path, None, 'L002', 'top level is not a JSON object')
        return None

    ok = True

    def need(name, typ):
        nonlocal ok
        if name not in lib:
            report.error(path, None, 'L002', 'required field "%s" is missing' % name)
            ok = False
            return None
        if not isinstance(lib[name], typ):
            report.error(path, None, 'L002', 'field "%s" has the wrong type' % name)
            ok = False
            return None
        return lib[name]

    fmt = need('format', str)
    fmt_version = need('format_version', str)
    lib_id = need('id', str)
    name = need('name', str)
    need('description', str)
    maintainer = need('maintainer', dict)
    license_ = need('license', dict)
    min_app = need('min_app_version', str)

    if maintainer is not None:
        if not isinstance(maintainer.get('name'), str) or not maintainer['name']:
            report.error(path, None, 'L002', 'maintainer.name is missing')
            ok = False
        if not (isinstance(maintainer.get('email'), str) and maintainer['email']) and \
                not (isinstance(maintainer.get('url'), str) and maintainer['url']):
            report.error(path, None, 'L002', 'maintainer needs at least one of email or url')
            ok = False
    if license_ is not None:
        for key in ('id', 'file', 'summary'):
            if not isinstance(license_.get(key), str) or not license_[key]:
                report.error(path, None, 'L002', 'license.%s is missing' % key)
                ok = False

    if fmt is not None and fmt != 'zangbundel-library':
        report.error(path, None, 'L003', 'format is "%s", expected "zangbundel-library"' % fmt)
        ok = False
    if fmt_version is not None:
        m = FORMAT_VERSION_RE.match(fmt_version)
        if not m:
            report.error(path, None, 'L002', 'format_version "%s" is not "<major>.<minor>"' % fmt_version)
            ok = False
        elif int(m.group(1)) != FORMAT_MAJOR_SUPPORTED:
            report.error(path, None, 'L004', 'format_version %s is not supported by this validator '
                         '(major %d); update the validator' % (fmt_version, FORMAT_MAJOR_SUPPORTED))
            ok = False
    if min_app is not None:
        minv = parse_semver(min_app)
        if minv is None:
            report.error(path, None, 'L002', 'min_app_version "%s" is not major.minor.patch' % min_app)
            ok = False
        elif app_version is not None and minv > app_version:
            report.error(path, None, 'L005', 'min_app_version %s is newer than the app version %s; '
                         'update the app' % (min_app, '.'.join(map(str, app_version))))
            ok = False
    if lib_id is not None and (not ID_RE.match(lib_id) or len(lib_id) > 64):
        report.error(path, None, 'L006', 'id "%s" is not a valid library id '
                     '(lower-case letters, digits, single hyphens, at most 64 characters)' % lib_id)
        ok = False
    if name is not None and len(name) > 80:
        report.error(path, None, 'L002', 'name is longer than 80 characters')
        ok = False
    if license_ is not None and isinstance(license_.get('file'), str):
        if not os.path.isfile(os.path.join(root, license_['file'])):
            report.error(path, None, 'L007', 'licence file "%s" is missing' % license_['file'])
            ok = False

    # Optional fields: shape only.
    if 'languages' in lib and not (isinstance(lib['languages'], list) and
                                   all(isinstance(x, str) for x in lib['languages'])):
        report.warning(path, None, 'L002', 'languages should be an array of strings')
    if 'release_index' in lib and not (isinstance(lib['release_index'], str) and
                                       lib['release_index'].startswith('https://')):
        report.warning(path, None, 'L002', 'release_index should be an HTTPS URL')
    if 'tags' in lib:
        tags = lib['tags']
        if not isinstance(tags, dict):
            report.warning(path, None, 'L002', 'tags should be an object')
        else:
            for tag, labels in tags.items():
                if not ID_RE.match(tag):
                    report.warning(path, None, 'S012', 'tag "%s" in zangbundel.json is not in id syntax' % tag)
                if not isinstance(labels, dict) or not all(isinstance(v, str) for v in labels.values()):
                    report.warning(path, None, 'L002', 'labels of tag "%s" should be an object of strings' % tag)

    return lib if ok else None


# ---------------------------------------------------------------------------
# Song level (sections 5 to 9, codes S001-S012, W001-W010, I001-I002)
# ---------------------------------------------------------------------------

def canonicalise(raw):
    """Section 8.1. Returns (canonical bytes, list of deviation names) or raises UnicodeDecodeError."""
    text = raw.decode('utf-8')
    deviations = []
    if text.startswith('﻿'):
        deviations.append('BOM')
        text = text[1:]
    nfc = unicodedata.normalize('NFC', text)
    if nfc != text:
        deviations.append('NFD')
        text = nfc
    if '\r' in text:
        deviations.append('CRLF')
        text = text.replace('\r\n', '\n').replace('\r', '\n')
    lines = text.split('\n')
    stripped = [ln.rstrip(' \t') for ln in lines]
    if stripped != lines:
        deviations.append('trailing whitespace')
    text = '\n'.join(stripped)
    body = text.rstrip('\n')
    canonical = body + '\n'
    if canonical != text:
        deviations.append('missing final newline' if not text.endswith('\n') else 'multiple final newlines')
    return canonical.encode('utf-8'), deviations


def display_text(line):
    """Section 9.1 step 5: remove [...] tokens, resolve escapes, tabs to spaces, trim right."""
    out = []
    i = 0
    n = len(line)
    while i < n:
        c = line[i]
        if c == '\\' and i + 1 < n and line[i + 1] in '[]{}\\':
            out.append(line[i + 1])
            i += 2
        elif c == '[':
            j = line.find(']', i + 1)
            if j == -1:
                out.append(c)
                i += 1
            else:
                i = j + 1
        else:
            out.append(c)
            i += 1
    return ''.join(out).replace('\t', ' ').rstrip()


class Song:
    def __init__(self, path):
        self.path = path
        self.meta = {}        # single-valued: name -> (value, line)
        self.multi = {}       # multi-valued: name -> [value]
        self.lines = []       # canonical line list (display text)
        self.hash_hex = None
        self.skipped = False


def validate_song(root, rel_path, report, lib):
    """Validates one song file. Returns a Song (with .skipped set when it would be skipped)."""
    song = Song(rel_path)
    full = os.path.join(root, rel_path)
    file_name = os.path.basename(rel_path)
    expected_id = file_name[:-4]

    def err(line, code, msg):
        report.error(rel_path, line, code, msg)
        song.skipped = True

    with open(full, 'rb') as fh:
        raw = fh.read()

    if len(raw) > MAX_FILE_BYTES:
        err(None, 'S002', 'file is %d bytes, larger than 64 KiB' % len(raw))
        return song
    if len(raw) > RECOMMENDED_FILE_BYTES:
        report.warning(rel_path, None, 'W008', 'file is %d bytes, larger than the recommended 8 KiB' % len(raw))

    bad = sorted({b for b in raw if b < 0x20 and b not in (0x09, 0x0A, 0x0D)} | ({0x7F} if 0x7F in raw else set()))
    if bad:
        err(None, 'S001', 'control characters other than LF, CR and tab: %s' %
            ', '.join('0x%02X' % b for b in bad))
        return song
    try:
        canonical, deviations = canonicalise(raw)
    except UnicodeDecodeError as exc:
        err(None, 'S001', 'file is not valid UTF-8 (%s)' % exc)
        return song
    if deviations:
        report.warning(rel_path, None, 'W001', 'file is not in canonical form: %s; '
                       'hash computed over the canonical form' % ', '.join(deviations))
    song.hash_hex = hashlib.sha256(canonical).digest()[:16].hex()

    source_lines = canonical.decode('utf-8').split('\n')[:-1]

    env = None            # None, 'verse', 'chorus', 'bridge', 'other'
    env_name = None
    env_line = None
    choruses = []         # (label, [lines])
    chorus_lines = None
    chorus_label = None
    in_implicit_verse = False
    unknown_reported = set()
    timing = []           # (line_no, kind, n, start)

    def set_single(name, value, line_no):
        if name in song.meta:
            err(line_no, 'S006', 'directive "%s" occurs more than once (first at line %d)' %
                (name, song.meta[name][1]))
        else:
            song.meta[name] = (value, line_no)

    for line_no, line in enumerate(source_lines, 1):
        if line.strip() == '':
            in_implicit_verse = False
            continue
        if line[0] == '#':
            continue
        starts = line[0] == '{'
        ends = line[-1] == '}'
        if starts or ends:
            if not (starts and ends):
                err(line_no, 'S011', 'malformed directive line: %s' %
                    ('"{" without closing "}"' if starts else '"}" without opening "{"'))
                continue
            body = line[1:-1]
            if '{' in body or '}' in body:
                err(line_no, 'S011', 'malformed directive line: stray brace inside the directive')
                continue
            name, sep, value = body.partition(':')
            name = name.strip()
            value = value.strip()
            if name != name.lower():
                report.warning(rel_path, line_no, 'W006', 'directive name "%s" is not lower case' % name)
                name = name.lower()
            if not DIRECTIVE_NAME_RE.match(name):
                err(line_no, 'S011', 'malformed directive name "%s"' % name)
                continue
            name = ALIASES.get(name, name)
            is_meta = False
            if name == 'meta':
                parts = value.split(None, 1)
                if not parts:
                    err(line_no, 'S011', '{meta} without a name')
                    continue
                name = parts[0].lower()
                value = parts[1] if len(parts) > 1 else ''
                is_meta = True

            # --- structure -------------------------------------------------
            if name == 'new_song':
                err(line_no, 'S009', '{new_song} is not allowed: one song per file')
            elif name.startswith('start_of_'):
                kind = name[len('start_of_'):]
                if env is not None:
                    err(line_no, 'S007', 'environment "%s" started inside "%s" (opened at line %d); '
                        'environments do not nest' % (kind, env_name, env_line))
                env_name, env_line = kind, line_no
                if kind in SHOWN_ENVIRONMENTS:
                    env = kind
                    if kind == 'chorus':
                        chorus_lines, chorus_label = [], value
                else:
                    env = 'other'
                    if kind not in KNOWN_HIDDEN_ENVIRONMENTS:
                        report.info(rel_path, line_no, 'I002', 'unknown environment "%s" skipped' % kind)
                in_implicit_verse = False
            elif name.startswith('end_of_'):
                kind = name[len('end_of_'):]
                if env is None:
                    err(line_no, 'S007', 'end_of_%s without an open environment' % kind)
                elif kind != env_name:
                    err(line_no, 'S007', 'end_of_%s closes environment "%s" opened at line %d' %
                        (kind, env_name, env_line))
                if env == 'chorus' and chorus_lines is not None:
                    choruses.append((chorus_label, chorus_lines))
                env, env_name, env_line, chorus_lines = None, None, None, None
            elif name == 'chorus':
                if not choruses:
                    err(line_no, 'S008', '{chorus} before any chorus has been defined')
                else:
                    selected = choruses[-1]
                    if value:
                        for label, lines in choruses:
                            if label == value:
                                selected = (label, lines)
                                break
                    song.lines.extend(selected[1])
            # --- metadata --------------------------------------------------
            elif name in SINGLE_VALUED:
                set_single(name, value, line_no)
            elif name in MULTI_VALUED:
                song.multi.setdefault(name, []).append(value)
            # --- timing (section 10.2), shape only -----------------------------
            elif name == 'x_zb_time':
                parts = value.split()
                if len(parts) not in (2, 3) or not parts[0].isdigit() or \
                        not all(TIME_RE.match(p) for p in parts[1:]):
                    report.warning(rel_path, line_no, 'W009', 'malformed x_zb_time "%s"' % value)
                else:
                    timing.append((line_no, 'time', int(parts[0]), float(parts[1])))
                if 'x_zb_time' not in unknown_reported:
                    unknown_reported.add('x_zb_time')
                    report.info(rel_path, line_no, 'I001', 'directive "x_zb_time" (phase 2 timing) '
                                'is ignored by a phase 1 app')
            elif name == 'x_zb_syllables':
                parts = value.split()
                if len(parts) < 2 or not parts[0].isdigit() or not all(SYLLABLE_RE.match(p) for p in parts[1:]):
                    report.warning(rel_path, line_no, 'W009', 'malformed x_zb_syllables "%s"' % value)
                else:
                    timing.append((line_no, 'syllables', int(parts[0]), None))
                if 'x_zb_syllables' not in unknown_reported:
                    unknown_reported.add('x_zb_syllables')
                    report.info(rel_path, line_no, 'I001', 'directive "x_zb_syllables" (phase 2 timing) '
                                'is ignored by a phase 1 app')
            elif name in KNOWN_IGNORED:
                pass
            else:
                key = ('meta ' if is_meta else '') + name
                if key not in unknown_reported:
                    unknown_reported.add(key)
                    report.info(rel_path, line_no, 'I001', 'unknown %s "%s" ignored' %
                                ('meta name' if is_meta else 'directive', name))
            continue

        # --- content line ---------------------------------------------------
        if env == 'other':
            continue
        text = display_text(line)
        if not text:
            continue
        if '\t' in line:
            report.warning(rel_path, line_no, 'W007', 'tab character in a content line; shown as a space')
        if len(text) > MAX_LINE:
            report.warning(rel_path, line_no, 'W005', 'lyric line is %d characters, longer than %d' %
                           (len(text), MAX_LINE))
        if env is None:
            in_implicit_verse = True
        song.lines.append(text)
        if env == 'chorus':
            chorus_lines.append(text)

    if env is not None:
        err(None, 'S007', 'environment "%s" opened at line %d is not closed at the end of the file' %
            (env_name, env_line))

    # --- required metadata (section 6.1) -------------------------------------
    song_id = song.meta.get('id', (None, None))[0]
    title = song.meta.get('title', (None, None))[0]
    language = song.meta.get('language', (None, None))[0]
    if not song_id:
        err(None, 'S003', 'required {meta: id ...} is missing')
    elif not ID_RE.match(song_id) or len(song_id) > 64:
        err(song.meta['id'][1], 'S003', 'id "%s" is not in id syntax' % song_id)
    elif song_id != expected_id:
        err(song.meta['id'][1], 'S004', 'id "%s" does not equal the file name "%s"' % (song_id, expected_id))
    if not ID_RE.match(expected_id) or len(expected_id) > 64:
        err(None, 'S004', 'file name "%s" is not in song id syntax' % file_name)
    if not title:
        err(None, 'S003', 'required {title: ...} is missing')
    elif len(title) > MAX_TITLE:
        report.warning(rel_path, song.meta['title'][1], 'W003',
                       'title is %d characters, longer than %d' % (len(title), MAX_TITLE))
    if not language:
        err(None, 'S003', 'required {meta: language ...} is missing')
    elif not LANG_RE.match(language):
        err(song.meta['language'][1], 'S003', 'language "%s" is not a well-formed BCP 47 tag' % language)

    # --- value checks (S012, W010) ----------------------------------------------
    if 'redistribute' in song.meta:
        value, line_no = song.meta['redistribute']
        if value not in ('yes', 'no'):
            err(line_no, 'S012', 'redistribute is "%s", expected "yes" or "no"' % value)
    if 'year' in song.meta:
        value, line_no = song.meta['year']
        if not re.match(r'^\d{4}$', value):
            err(line_no, 'S012', 'year "%s" is not four digits' % value)
    if 'variant-group' in song.meta:
        value, line_no = song.meta['variant-group']
        if not ID_RE.match(value) or len(value) > 64:
            err(line_no, 'S012', 'variant-group "%s" is not in id syntax' % value)
    for tag in song.multi.get('tag', []):
        if not ID_RE.match(tag) or len(tag) > 64:
            err(None, 'S012', 'tag "%s" is not in id syntax' % tag)
    if 'license' in song.meta:
        value, line_no = song.meta['license']
        if value not in KNOWN_LICENSES and not LICENSE_REF_RE.match(value):
            report.warning(rel_path, line_no, 'W010', 'license "%s" is not a known SPDX identifier, '
                           '"public-domain" or "proprietary"' % value)
    if 'notation' in song.meta:
        value, line_no = song.meta['notation']
        if not os.path.isfile(os.path.join(root, value)):
            report.warning(rel_path, line_no, 'W012', 'notation file "%s" does not exist in the repository' % value)

    # --- recommended metadata (W002) ----------------------------------------------
    missing = []
    if not song.multi.get('lyricist') and not song.multi.get('composer'):
        missing.append('lyricist/composer')
    for key in ('copyright', 'license', 'source'):
        if key not in song.meta:
            missing.append(key)
    if not song.multi.get('tag'):
        missing.append('tag')
    if missing:
        report.warning(rel_path, None, 'W002', 'recommended metadata missing: %s' % ', '.join(missing))

    # --- canonical line list (section 9) --------------------------------------------
    if not song.lines:
        err(None, 'S010', 'no lyric lines (empty canonical line list)')
    elif len(song.lines) > MAX_CANONICAL_LINES:
        report.warning(rel_path, None, 'W004', 'canonical line list has %d lines, more than %d' %
                       (len(song.lines), MAX_CANONICAL_LINES))

    # --- timing shape (W009) --------------------------------------------------------
    seen_n = set()
    last_n, last_start = 0, -1.0
    for line_no, kind, n, start in timing:
        if n < 1 or n > len(song.lines):
            report.warning(rel_path, line_no, 'W009', '%s refers to line %d, but the song has %d lines' %
                           (kind, n, len(song.lines)))
        if kind == 'time':
            if n in seen_n:
                report.warning(rel_path, line_no, 'W009', 'duplicate x_zb_time for line %d' % n)
            elif n <= last_n:
                report.warning(rel_path, line_no, 'W009', 'x_zb_time for line %d is out of order' % n)
            if start <= last_start:
                report.warning(rel_path, line_no, 'W009', 'x_zb_time start %.3f is not increasing' % start)
            seen_n.add(n)
            last_n, last_start = max(last_n, n), max(last_start, start)

    return song


# ---------------------------------------------------------------------------
# Setlists (section 13, codes SL001-SL104, I004, I005)
# ---------------------------------------------------------------------------

class Setlist:
    def __init__(self, path):
        self.path = path
        self.meta = {}        # name -> (value, line)
        self.entries = []     # dicts: kind 'song' (lib, song) or 'title' (title), line
        self.hash_hex = None
        self.canonical = b''
        self.skipped = False


def find_setlist_files(root):
    base = os.path.join(root, 'setlists')
    if not os.path.isdir(base):
        return []
    found = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames.sort()
        for fn in sorted(filenames):
            if fn.endswith('.zbs'):
                found.append(os.path.relpath(os.path.join(dirpath, fn), root).replace(os.sep, '/'))
    found.sort()
    return found


def validate_setlist(root, rel_path, report, lib, song_ids):
    """Validates one setlist file. song_ids: set of song ids of this library that passed validation."""
    sl = Setlist(rel_path)
    file_name = os.path.basename(rel_path)
    expected_id = file_name[:-4]
    lib_id = lib.get('id', '')

    def err(line, code, msg):
        report.error(rel_path, line, code, msg)
        sl.skipped = True

    with open(os.path.join(root, rel_path), 'rb') as fh:
        raw = fh.read()
    if len(raw) > MAX_FILE_BYTES:
        err(None, 'SL001', 'file is %d bytes, larger than 64 KiB' % len(raw))
        return sl
    bad = sorted({b for b in raw if b < 0x20 and b not in (0x09, 0x0A, 0x0D)} | ({0x7F} if 0x7F in raw else set()))
    if bad:
        err(None, 'SL001', 'control characters other than LF, CR and tab: %s' % ', '.join('0x%02X' % b for b in bad))
        return sl
    try:
        canonical, deviations = canonicalise(raw)
    except UnicodeDecodeError as exc:
        err(None, 'SL001', 'file is not valid UTF-8 (%s)' % exc)
        return sl
    if deviations:
        report.warning(rel_path, None, 'SL102', 'file is not in canonical form: %s' % ', '.join(deviations))
    sl.canonical = canonical
    sl.hash_hex = hashlib.sha256(canonical).digest()[:16].hex()

    unknown_reported = set()
    for line_no, line in enumerate(canonical.decode('utf-8').split('\n')[:-1], 1):
        if line.strip() == '' or line[0] == '#':
            continue
        if line[0] == '{' or line[-1] == '}':
            if not (line[0] == '{' and line[-1] == '}') or '{' in line[1:-1] or '}' in line[1:-1]:
                err(line_no, 'SL004', 'malformed directive line')
                continue
            name, _, value = line[1:-1].partition(':')
            name = name.strip().lower()
            value = value.strip()
            if name == 'meta':
                parts = value.split(None, 1)
                if not parts:
                    err(line_no, 'SL004', '{meta} without a name')
                    continue
                name, value = parts[0].lower(), (parts[1] if len(parts) > 1 else '')
            if name == 'title':
                if sl.entries:
                    err(line_no, 'SL002', '{title} after the first entry')
                if 'title' in sl.meta:
                    err(line_no, 'SL002', '{title} occurs more than once')
                sl.meta['title'] = (value, line_no)
            elif name in ('id', 'description', 'language'):
                if name in sl.meta:
                    err(line_no, 'SL002' if name == 'id' else 'SL004', '{meta: %s} occurs more than once' % name)
                sl.meta[name] = (value, line_no)
            else:
                if name not in unknown_reported:
                    unknown_reported.add(name)
                    report.info(rel_path, line_no, 'I001', 'unknown directive "%s" ignored' % name)
            continue
        m = SETLIST_ENTRY_RE.match(line)
        if m:
            entry_lib, entry_song = m.group(1), m.group(2)
            sl.entries.append({'kind': 'song', 'lib': entry_lib, 'song': entry_song, 'line': line_no})
            if entry_lib == lib_id:
                if entry_song not in song_ids:
                    report.warning(rel_path, line_no, 'SL101', 'song "%s" does not exist in this library' % entry_song)
            else:
                report.info(rel_path, line_no, 'I004', 'entry names another library "%s"; resolved only when it is '
                            'installed' % entry_lib)
            continue
        m = SETLIST_TITLE_ENTRY_RE.match(line)
        if m:
            sl.entries.append({'kind': 'title', 'title': m.group(1).strip(), 'line': line_no})
            report.info(rel_path, line_no, 'I005', 'title-only entry "%s"' % m.group(1).strip())
            continue
        err(line_no, 'SL004', 'malformed entry line')

    title = sl.meta.get('title', ('', None))[0]
    sl_id = sl.meta.get('id', ('', None))[0]
    if not title:
        err(None, 'SL002', 'required {title: ...} is missing or empty')
    elif len(title) > MAX_TITLE:
        report.warning(rel_path, sl.meta['title'][1], 'SL104', 'title is %d characters, longer than %d' %
                       (len(title), MAX_TITLE))
    if not sl_id:
        err(None, 'SL002', 'required {meta: id ...} is missing or empty')
    elif not ID_RE.match(sl_id) or sl_id != expected_id:
        err(sl.meta['id'][1], 'SL003', 'id "%s" does not equal the file name "%s"' % (sl_id, expected_id))
    if not sl.entries:
        err(None, 'SL005', 'no entries')
    elif len(sl.entries) > SETLIST_MAX_ENTRIES:
        report.warning(rel_path, None, 'SL103', '%d entries, more than %d' % (len(sl.entries), SETLIST_MAX_ENTRIES))
    return sl


# ---------------------------------------------------------------------------
# Library walk (codes S005, L008, W011, I003)
# ---------------------------------------------------------------------------

def find_song_files(root, report):
    songs_dir = os.path.join(root, 'songs')
    if not os.path.isdir(songs_dir):
        return None, 0
    cho, other = [], 0
    for dirpath, dirnames, filenames in os.walk(songs_dir):
        dirnames.sort()
        for fn in sorted(filenames):
            rel = os.path.relpath(os.path.join(dirpath, fn), root).replace(os.sep, '/')
            if fn.endswith('.cho'):
                cho.append(rel)
            else:
                other += 1
    cho.sort()
    if other:
        report.info('songs', None, 'I003', '%d non-.cho file(s) under songs/ ignored' % other)
    return cho, other


def run(root, app_version=None, allow_empty=False):
    """Validates the library at root. Returns (report, lib, songs, setlists); lib is None when refused."""
    report = Report()

    lib = validate_library_json(root, report, app_version)
    song_files, _ = find_song_files(root, report)
    if song_files is None or not song_files:
        if allow_empty:
            report.warning('songs', None, 'L008', 'songs/ directory missing or contains no .cho file')
        else:
            report.error('songs', None, 'L008', 'songs/ directory missing or contains no .cho file')

    songs = []
    if lib is not None and song_files:
        for rel in song_files:
            songs.append(validate_song(root, rel, report, lib))

        # S005: duplicate ids; the first in path order is imported.
        by_id = {}
        for song in songs:
            song_id = song.meta.get('id', (None, None))[0]
            if not song_id:
                continue
            if song_id in by_id:
                first = by_id[song_id]
                report.error(song.path, None, 'S005', 'id "%s" duplicates %s' % (song_id, first.path))
                report.error(first.path, None, 'S005', 'id "%s" is also used by %s (this file is imported)' %
                             (song_id, song.path))
                song.skipped = True
            else:
                by_id[song_id] = song

        # W011: variant group with a single member.
        groups = {}
        for song in songs:
            if song.skipped or 'variant-group' not in song.meta:
                continue
            groups.setdefault(song.meta['variant-group'][0], []).append(song)
        for group, members in groups.items():
            if len(members) == 1:
                song = members[0]
                report.warning(song.path, song.meta['variant-group'][1], 'W011',
                               'variant-group "%s" has only one member in this library' % group)

        # Tags without a label: informational, not a spec code.
        labels = lib.get('tags') if isinstance(lib.get('tags'), dict) else {}
        for song in songs:
            for tag in sorted(set(song.multi.get('tag', []))):
                if tag not in labels:
                    report.info(song.path, None, 'I001', 'tag "%s" has no label in zangbundel.json; '
                                'shown as is' % tag)

    # Setlists (section 13): validated against the songs that passed.
    setlists = []
    if lib is not None:
        setlist_files = find_setlist_files(root)
        if setlist_files:
            m = FORMAT_VERSION_RE.match(lib.get('format_version', '') or '')
            if m and (int(m.group(1)), int(m.group(2))) < (1, 1):
                report.warning('zangbundel.json', None, 'L002', 'setlists/ needs format_version 1.1 or later '
                               '(found %s)' % lib.get('format_version'))
        song_ids = {s.meta['id'][0] for s in songs if not s.skipped and 'id' in s.meta}
        seen_ids = {}
        for rel in setlist_files:
            sl = validate_setlist(root, rel, report, lib, song_ids)
            sl_id = sl.meta.get('id', ('', None))[0]
            if sl_id and not sl.skipped:
                if sl_id in seen_ids:
                    report.error(sl.path, None, 'SL003', 'id "%s" duplicates %s' % (sl_id, seen_ids[sl_id]))
                    sl.skipped = True
                else:
                    seen_ids[sl_id] = sl.path
            setlists.append(sl)

    return report, lib, songs, setlists


def library_errors(report):
    return [f for f in report.findings if f[2] == 'error' and f[3][0] in 'LA']


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Validate a Zangbundel song library (song-format specification 1.0).')
    parser.add_argument('root', nargs='?', default='.', help='library root (default: current directory)')
    parser.add_argument('--app-version', metavar='X.Y.Z',
                        help='check min_app_version against this app version (L005)')
    parser.add_argument('--allow-empty', action='store_true',
                        help='an empty songs/ directory is a warning instead of an error (L008)')
    parser.add_argument('--strict', action='store_true', help='exit non-zero on warnings too')
    parser.add_argument('--info', action='store_true', help='also print informational findings')
    parser.add_argument('--quiet', action='store_true', help='print findings and summary only, no per-song lines')
    args = parser.parse_args(argv)

    root = args.root
    if not os.path.isdir(root):
        parser.error('"%s" is not a directory' % root)
    app_version = None
    if args.app_version:
        app_version = parse_semver(args.app_version)
        if app_version is None:
            parser.error('--app-version must be major.minor.patch')

    out = sys.stdout
    report, lib, songs, setlists = run(root, app_version, args.allow_empty)
    report.print(out, args.info)

    if not args.quiet:
        for song in songs:
            status = 'SKIPPED' if song.skipped else 'OK'
            out.write('%s: %s hash=%s lines=%d\n' % (song.path, status, song.hash_hex or '-', len(song.lines)))
        for sl in setlists:
            status = 'SKIPPED' if sl.skipped else 'OK'
            out.write('%s: %s hash=%s entries=%d\n' % (sl.path, status, sl.hash_hex or '-', len(sl.entries)))

    lib_errors = library_errors(report)
    imported = sum(1 for s in songs if not s.skipped)
    skipped = sum(1 for s in songs if s.skipped)
    sl_imported = sum(1 for s in setlists if not s.skipped)
    sl_skipped = sum(1 for s in setlists if s.skipped)
    warnings = report.count('warning')
    if lib_errors or lib is None:
        out.write('Library refused: %d library error(s).\n' % len(lib_errors))
        return 1
    extra = ', %d setlist(s) imported, %d skipped' % (sl_imported, sl_skipped) if setlists else ''
    out.write('%d song(s) imported, %d skipped%s, %d warning(s).\n' % (imported, skipped, extra, warnings))
    if skipped or sl_skipped or lib_errors:
        return 1
    if args.strict and warnings:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
