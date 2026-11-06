#!/usr/bin/env python3
"""Interactive console menu for maintaining this Zangbundel library.

Double-click this file in the library folder, or run it from anywhere:
    python release-menu.py

Every step of the release process is a menu item of its own. Each item runs at
most one git command that changes something (add, commit, tag, push, pull);
that command is shown first and runs only after the user confirms it.
Read-only git queries (status, fetch, rev-list, ls-remote, ...) run without a
question; with the explanations switched on they are printed as well.

Before steps that would conflict with newer commits on GitHub, the menu fetches
from GitHub and offers to pull first. Before a tag is set, the tagged commit is
built and verified exactly as the release workflow on GitHub will do it, so a
pushed tag does not start a release that fails.

All dialogs are available in Dutch, English and German; the language is chosen
at start. Menu item 1 shows or hides the explanations; they are hidden at start.

Based on menu-with-tutorial-for-release-process.py by Pepe
(https://github.com/pepe-hb9evt/Zangbundel-bibliotheek-van-Pepe), dedicated to
the public domain under CC0 1.0, and adapted for this repository: Dutch added,
only the library's own files are staged, a pre-flight build before tagging,
pull as fast-forward only, and errors that keep the window open.

Needs Python 3.8+ (standard library only) and git on the PATH.

Copyright 2026 Remko Welling, PE1MEW.
Licensed under the Apache License 2.0 with the Commons Clause condition; see
scripts/LICENSE and license.md.
"""

import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import traceback

# The menu lies in the root folder of the library; the tools are in scripts/.
REPO_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = 'dist'
MAIN_BRANCH = 'main'
REMOTE = 'origin'
TEST_TAG = 'v0.0.0-test'
TAG_PATTERN = re.compile(r'^v(\d{4})\.(\d{1,2})\.(\d+)$')
# The files that make up the library. Menu item 4 stages changes to these only;
# anything else (notes, source material, editor files) is left for the user.
LIBRARY_PATHS = ('songs', 'setlists', 'notation', 'zangbundel.json', 'LICENSE', 'license.md',
                 'README.md', 'changelog.md')
LINE = '-' * 66
MAX_WIDTH = 75
# A git command inside a text, e.g. "git push origin main"; it is never split across lines.
GIT_COMMAND = re.compile(r'git(?: [^\s"(),]*[^\s"(),.])+')
NO_BREAK_SPACE = '\x00'
NO_BREAK_HYPHEN = '\x01'
LANGUAGES = ('nl', 'en', 'de')
DEFAULT_LANGUAGE = 'nl'

# Language of the dialogs, chosen at start.
language = DEFAULT_LANGUAGE

# Explanations on or off; off at start, toggled by menu item 1.
tutorial = False

# Tag chosen in this session (set by "set tag", offered as default later).
session_tag = None


class StopMenu(Exception):
    """Raised to end the program after a message the user must act on."""


# ---------------------------------------------------------------------------
# Language, output and input helpers
# ---------------------------------------------------------------------------

def tr(nl, en, de):
    """Return the text in the chosen language."""
    return {'nl': nl, 'en': en, 'de': de}[language]


def setup_console():
    """Make sure accented letters are printed correctly, also when output is redirected."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass


def choose_language():
    """Ask for the dialog language until Dutch, English or German is chosen."""
    global language
    while True:
        answer = input('Taal / Language / Sprache (nl/en/de) (Enter=nl): ').strip().lower()
        answer = answer or DEFAULT_LANGUAGE
        if answer in LANGUAGES:
            language = answer
            return
        say()
        say("nl: Typ 'nl', 'en' of 'de'.")
        say("en: Please enter 'nl', 'en' or 'de'.")
        say("de: Bitte 'nl', 'en' oder 'de' eingeben.")
        say()


def wrap_text(text):
    """Wrap text at MAX_WIDTH, at the last space or hyphen before the limit.

    Git commands inside the text are kept on one line; if one does not fit, the
    line break is made before it.
    """
    lines = []
    for line in text.split('\n'):
        if len(line) <= MAX_WIDTH:
            lines.append(line)
            continue
        protected = GIT_COMMAND.sub(
            lambda m: m.group(0).replace(' ', NO_BREAK_SPACE).replace('-', NO_BREAK_HYPHEN), line)
        indent = ' ' * (len(line) - len(line.lstrip(' ')))
        wrapped = textwrap.wrap(protected, width=MAX_WIDTH, break_long_words=False,
                                break_on_hyphens=True, subsequent_indent=indent)
        lines.extend(part.replace(NO_BREAK_SPACE, ' ').replace(NO_BREAK_HYPHEN, '-')
                     for part in wrapped)
    return '\n'.join(lines)


def say(text='', wrap=True):
    """Print a message; long texts are wrapped. wrap=False for commands, URLs and git output."""
    print(wrap_text(text) if wrap else text, flush=True)


def teach(text='', wrap=True):
    """Print an explanation; shown only when the explanations are switched on."""
    if tutorial:
        say(text, wrap)


def explain(title, text):
    """Print a step title; the explanation of what happens now only with the explanations on."""
    say()
    say(LINE)
    say(title)
    say(LINE)
    if tutorial:
        for paragraph in text.strip().split('\n'):
            say(paragraph.strip())
    say()


def ask(prompt, default=None):
    """Ask for a line of text; Enter returns the default."""
    suffix = ' (Enter = %s)' % default if default else ''
    answer = input('%s%s: ' % (prompt, suffix)).strip()
    return answer or (default or '')


def confirm(prompt):
    """Ask a yes/no question; j, ja, y or yes counts as yes, anything else as no."""
    answer = input('%s %s: ' % (prompt, tr('[j/N]', '[y/N]', '[j/N]'))).strip().lower()
    return answer in ('j', 'ja', 'y', 'yes')


def pause():
    try:
        input(tr('\nVerder met Enter ...', '\nPress Enter to continue ...', '\nWeiter mit Enter ...'))
    except EOFError:
        pass


# ---------------------------------------------------------------------------
# git and tool calls
# ---------------------------------------------------------------------------

def show_command(args):
    return subprocess.list2cmdline(args)


def git_query(*args):
    """Run a read-only git command and return (exit code, output). It is shown, not confirmed."""
    cmd = ['git'] + list(args)
    teach('  %s: %s' % (tr('Opvraging', 'Query', 'Abfrage'), show_command(cmd)), wrap=False)
    result = subprocess.run(cmd, cwd=REPO_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            universal_newlines=True, encoding='utf-8', errors='replace')
    return result.returncode, result.stdout.strip()


def git_change(args, what):
    """Show a git command that changes something, ask, then run it. Returns True on success."""
    cmd = ['git'] + list(args)
    say(tr('Dit git-commando wordt nu uitgevoerd:', 'This git command will be run now:',
           'Dieser Git-Befehl wird jetzt ausgeführt:'))
    say()
    say('    %s' % show_command(cmd), wrap=False)
    say()
    if tutorial:
        say(what)
        say()
    if not confirm(tr('Commando uitvoeren?', 'Run the command?', 'Befehl ausführen?')):
        say(tr('Afgebroken – er is niets veranderd.', 'Cancelled – nothing was changed.',
               'Abgebrochen – es wurde nichts geändert.'))
        return False
    say()
    result = subprocess.run(cmd, cwd=REPO_DIR)
    say()
    if result.returncode != 0:
        say(tr('FOUT: het git-commando is mislukt (exitcode %d), zie de meldingen hierboven.',
               'ERROR: The git command failed (exit code %d), see the messages above.',
               'FEHLER: Der Git-Befehl ist fehlgeschlagen (Exit-Code %d), siehe Meldungen oben.')
            % result.returncode)
        return False
    say(tr('OK: commando uitgevoerd.', 'OK: Command completed successfully.',
           'OK: Befehl erfolgreich ausgeführt.'))
    return True


def run_tool(script, *args):
    """Run one of the library tools with the current Python. Returns its exit code."""
    cmd = [sys.executable, os.path.join('scripts', script)] + list(args)
    teach('  %s: %s' % (tr('Aanroep', 'Call', 'Aufruf'), show_command(['python'] + cmd[1:])),
          wrap=False)
    teach()
    result = subprocess.run(cmd, cwd=REPO_DIR)
    say()
    if result.returncode == 0:
        say(tr('Resultaat: OK', 'Result: OK', 'Ergebnis: OK'))
    else:
        say(tr('Resultaat: FOUT (exitcode %d), zie de meldingen hierboven',
               'Result: ERROR (exit code %d), see the messages above',
               'Ergebnis: FEHLER (Exit-Code %d), siehe Meldungen oben') % result.returncode)
    return result.returncode


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_git_available():
    try:
        subprocess.run(['git', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError:
        raise StopMenu(tr(
            'Git is niet gevonden. Zet de map van git.exe in het PATH (bijvoorbeeld '
            'C:\\Program Files\\Git\\cmd) en start het menu opnieuw.',
            'Git was not found. Please add the folder of git.exe to the PATH '
            '(e.g. C:\\Program Files\\Git\\cmd) and restart the menu.',
            'Git wurde nicht gefunden. Bitte den Ordner von git.exe in den PATH eintragen '
            '(z. B. C:\\Program Files\\Git\\cmd) und das Menü neu starten.'))
    code, _ = git_query('rev-parse', '--is-inside-work-tree')
    if code != 0:
        raise StopMenu(tr('De map %s is geen git-repository.',
                          'The folder %s is not a git repository.',
                          'Der Ordner %s ist kein Git-Repository.') % REPO_DIR)


def current_branch():
    code, out = git_query('symbolic-ref', '--short', 'HEAD')
    return out if code == 0 else None


def fetch_and_count_incoming():
    """Fetch from GitHub and return the number of commits on GitHub missing locally, or None."""
    code, _ = git_query('fetch', '--quiet', REMOTE)
    if code != 0:
        say(tr('WAARSCHUWING: GitHub is niet bereikbaar (git fetch mislukt).',
               'WARNING: GitHub cannot be reached (git fetch failed).',
               'WARNUNG: GitHub ist nicht erreichbar (git fetch fehlgeschlagen).'))
        return None
    code, out = git_query('rev-list', '--count', 'HEAD..%s/%s' % (REMOTE, MAIN_BRANCH))
    if code != 0:
        say(tr('WAARSCHUWING: de stand van %s/%s kon niet worden vergeleken.',
               'WARNING: The state of %s/%s could not be compared.',
               'WARNUNG: Der Stand von %s/%s konnte nicht verglichen werden.')
            % (REMOTE, MAIN_BRANCH))
        return None
    return int(out or 0)


def pull_fast_forward():
    """Pull from GitHub without merge commits. Returns True on success."""
    ok = git_change(['pull', '--ff-only', REMOTE, MAIN_BRANCH],
                    tr('Daarna is de lokale stand gelijk aan die op GitHub.',
                       'Afterwards the local state is the same as on GitHub.',
                       'Danach ist der lokale Stand gleich wie auf GitHub.'))
    if not ok:
        say(tr('Lukt "git pull --ff-only" niet, dan zijn er hier én op GitHub nieuwe commits. '
               'Los dat op met GitHub Desktop of vraag hulp; het menu maakt geen merge.',
               'If "git pull --ff-only" fails, there are new commits both here and on GitHub. '
               'Resolve that with GitHub Desktop or ask for help; the menu does not merge.',
               'Schlägt "git pull --ff-only" fehl, gibt es hier und auf GitHub neue Commits. '
               'Das bitte mit GitHub Desktop lösen oder um Hilfe bitten; das Menü macht keinen '
               'Merge.'))
    return ok


def require_nothing_to_pull():
    """Make sure GitHub has no commits that are missing here; offer to pull them. False: stop."""
    teach(tr('Controleren of er op GitHub iets nieuws is dat eerst opgehaald moet worden ...',
             'Checking whether GitHub has new commits that must be pulled first ...',
             'Prüfe, ob es auf GitHub Neues gibt, das zuerst geholt werden muss ...'))
    incoming = fetch_and_count_incoming()
    if incoming is None:
        say(tr('Deze stap wordt afgebroken, omdat niet gecontroleerd kon worden of er iets op te '
               'halen is.',
               'This step is cancelled because it could not be checked whether there is something '
               'to pull.',
               'Dieser Schritt wird abgebrochen, weil nicht geprüft werden konnte, ob etwas zu '
               'holen ist.'))
        return False
    if incoming:
        code, out = git_query('log', '--oneline', 'HEAD..%s/%s' % (REMOTE, MAIN_BRANCH))
        say(tr('Op GitHub staan %d commit(s) die hier nog ontbreken (bijvoorbeeld de nieuwe '
               'releases.json na een release):',
               'GitHub has %d commit(s) that are missing here (e.g. the new releases.json after a '
               'release):',
               'Auf GitHub gibt es %d Commit(s), die hier noch fehlen (z. B. die neue releases.json '
               'nach einem Release):') % incoming)
        say(out, wrap=False)
        say()
        if not pull_fast_forward():
            return False
    teach(tr('OK: op GitHub is niets nieuws.', 'OK: There is nothing new on GitHub.',
             'OK: Auf GitHub gibt es nichts Neues.'))
    return True


def library_is_valid():
    teach(tr('De bibliotheek controleren (validate.py --strict) ...',
             'Validating the library (validate.py --strict) ...',
             'Prüfe die Bibliothek (validate.py --strict) ...'))
    return run_tool('validate.py', '--strict', '.') == 0


def existing_library_paths():
    """The library paths that exist on disk or are tracked by git (deleted files count too)."""
    found = []
    for path in LIBRARY_PATHS:
        if os.path.exists(os.path.join(REPO_DIR, path)):
            found.append(path)
        else:
            code, out = git_query('ls-files', '--', path)
            if out:
                found.append(path)
    return found


def unstaged_library_changes():
    """Changes to library files that are not staged: lines of git status --porcelain."""
    paths = existing_library_paths()
    if not paths:
        return []
    code, out = git_query('status', '--porcelain', '--', *paths)
    return [line for line in out.splitlines() if line[1:2] != ' ']


def library_id():
    with open(os.path.join(REPO_DIR, 'zangbundel.json'), encoding='utf-8') as fh:
        return json.load(fh)['id']


def preflight(tag):
    """Build and verify HEAD as the release workflow will for this tag. True when it passes."""
    teach(tr('Proefbouw: de laatste commit wordt gebouwd en gecontroleerd zoals GitHub dat '
             'straks doet ...',
             'Pre-flight: the last commit is built and verified as GitHub will do it ...',
             'Probelauf: der letzte Commit wird gebaut und geprüft, wie GitHub es später tut ...'))
    with tempfile.TemporaryDirectory() as out:
        if run_tool('release.py', 'build', '--tag', tag, '--allow-untagged', '--out', out) != 0:
            return False
        archive = os.path.join(out, '%s-%s.zbl' % (library_id(), tag[1:]))
        return run_tool('release.py', 'verify', '--strict', archive) == 0


def local_tags():
    code, out = git_query('tag', '--list')
    return out.splitlines() if code == 0 and out else []


def tag_exists_locally(tag):
    code, _ = git_query('rev-parse', '-q', '--verify', 'refs/tags/%s' % tag)
    return code == 0


def tag_on_github(tag):
    """True / False, or None when GitHub cannot be reached."""
    code, _ = git_query('ls-remote', '--exit-code', '--tags', REMOTE, 'refs/tags/%s' % tag)
    if code == 0:
        return True
    if code == 2:
        return False
    say(tr('WAARSCHUWING: GitHub is niet bereikbaar (git ls-remote mislukt).',
           'WARNING: GitHub cannot be reached (git ls-remote failed).',
           'WARNUNG: GitHub ist nicht erreichbar (git ls-remote fehlgeschlagen).'))
    return None


def release_tags(tags):
    """Release tags sorted by version, newest last."""
    found = []
    for tag in tags:
        match = TAG_PATTERN.match(tag)
        if match:
            found.append((tuple(int(x) for x in match.groups()), tag))
    return [tag for _, tag in sorted(found)]


def suggest_next_tag():
    today = datetime.date.today()
    numbers = []
    for tag in local_tags():
        match = TAG_PATTERN.match(tag)
        if match and int(match.group(1)) == today.year and int(match.group(2)) == today.month:
            numbers.append(int(match.group(3)))
    return 'v%d.%d.%d' % (today.year, today.month, max(numbers) + 1 if numbers else 0)


def default_tag():
    if session_tag:
        return session_tag
    tags = release_tags(local_tags())
    return tags[-1] if tags else None


def actions_url():
    code, url = git_query('remote', 'get-url', REMOTE)
    if code != 0:
        return None
    match = re.match(r'^(?:https://github\.com/|git@github\.com:)(.+?)(?:\.git)?/?$', url)
    return 'https://github.com/%s/actions' % match.group(1) if match else None


# ---------------------------------------------------------------------------
# Menu items
# ---------------------------------------------------------------------------

def item_validate():
    explain(tr('2  Bibliotheek controleren', '2  Validate library', '2  Bibliothek prüfen'),
            tr('validate.py controleert zangbundel.json en alle liedjes onder songs/ volgens de regels '
               'van het Zangbundel-formaat.\nFouten en waarschuwingen moeten opgelost zijn voordat '
               'er een release komt. Er wordt niets veranderd.',
               'validate.py checks zangbundel.json and all songs under songs/ against the rules of '
               'the Zangbundel format.\nErrors and warnings must be fixed before a release is made. '
               'Nothing is changed.',
               'validate.py prüft zangbundel.json und alle Lieder unter songs/ nach den Regeln des '
               'Zangbundel-Formats.\nFehler und Warnungen müssen behoben werden, bevor ein Release '
               'gemacht wird. Es wird nichts verändert.'))
    run_tool('validate.py', '--strict', '--info', '.')


def item_status():
    explain(tr('3  Status tonen', '3  Show status', '3  Status anzeigen'),
            tr('Toont de stand van de repository: branch, gewijzigde bestanden, tags en de '
               'vergelijking met GitHub.\nEr worden alleen opvragingen gedaan; er wordt niets '
               'veranderd.',
               'Shows the state of the repository: branch, changed files, tags and the comparison '
               'with GitHub.\nOnly queries are run; nothing is changed.',
               'Zeigt den Stand des Repositorys: Branch, geänderte Dateien, Tags und den Vergleich '
               'mit GitHub.\nEs werden nur Abfragen ausgeführt; es wird nichts verändert.'))
    branch = current_branch()
    say('Branch: %s' % (branch or tr('(geen branch)', '(no branch)', '(kein Branch)')))
    code, out = git_query('status', '--short')
    if out:
        say(tr('Gewijzigde bestanden:', 'Changed files:', 'Geänderte Dateien:'))
        say(out, wrap=False)
    else:
        say(tr('Gewijzigde bestanden: geen', 'Changed files: none', 'Geänderte Dateien: keine'))
    tags = release_tags(local_tags())
    say(tr('Release-tags lokaal: %s', 'Local release tags: %s', 'Release-Tags lokal: %s')
        % (', '.join(tags) if tags else tr('geen', 'none', 'keine')))
    incoming = fetch_and_count_incoming()
    code, ahead = git_query('rev-list', '--count', '%s/%s..HEAD' % (REMOTE, MAIN_BRANCH))
    if incoming is not None:
        say(tr('Nieuw op GitHub (op te halen): %d commit(s)',
               'New on GitHub (to pull): %d commit(s)',
               'Auf GitHub neu (zu pullen): %d Commit(s)') % incoming)
    if code == 0:
        say(tr('Lokaal nieuw (te pushen): %s commit(s)', 'New locally (to push): %s commit(s)',
               'Lokal neu (zu pushen): %s Commit(s)') % ahead)
    if incoming:
        say(tr('Tip: voer eerst menupunt 12 (git pull) uit, vóór een commit of push.',
               'Note: run menu item 12 (git pull) before committing or pushing.',
               'Hinweis: Vor Commit oder Push zuerst Menüpunkt 12 (git pull) ausführen.'))


def item_add():
    explain(tr('4  Wijzigingen klaarzetten (git add)', '4  Stage changes (git add)',
               '4  Änderungen vormerken (git add)'),
            tr('Alle gewijzigde en nieuwe bestanden van de bibliotheek (songs/, setlists/, '
               'zangbundel.json, licentie, README en changelog) worden klaargezet voor de volgende '
               'commit.\nAndere wijzigingen blijven staan; die zet u zelf klaar als ze erbij horen.',
               'All changed and new files of the library (songs/, setlists/, zangbundel.json, '
               'licence, README and changelog) are staged for the next commit.\nOther changes are '
               'left alone; stage them yourself if they belong in the commit.',
               'Alle geänderten und neuen Dateien der Bibliothek (songs/, setlists/, '
               'zangbundel.json, Lizenz, README und Changelog) werden für den nächsten Commit '
               'vorgemerkt.\nAndere Änderungen bleiben liegen; die bitte selbst vormerken, wenn sie '
               'dazugehören.'))
    paths = existing_library_paths()
    code, mine = git_query('status', '--short', '--', *paths) if paths else (0, '')
    code, everything = git_query('status', '--short')
    others = [line for line in everything.splitlines() if line not in mine.splitlines()]
    if others:
        say(tr('Andere wijzigingen (worden NIET klaargezet):',
               'Other changes (NOT staged by the menu):',
               'Andere Änderungen (werden NICHT vorgemerkt):'))
        say('\n'.join(others), wrap=False)
        say()
    if not mine:
        say(tr('Er zijn geen wijzigingen in de bibliotheek – niets te doen.',
               'There are no changes in the library – nothing to do.',
               'Es gibt keine Änderungen in der Bibliothek – nichts zu tun.'))
        return
    say(tr('Deze wijzigingen in de bibliotheek worden klaargezet:',
           'These changes in the library will be staged:',
           'Diese Änderungen in der Bibliothek werden vorgemerkt:'))
    say(mine, wrap=False)
    say()
    git_change(['add', '-A', '--'] + paths,
               tr('Daarna zijn de wijzigingen klaargezet, maar nog niet gecommit (volgende stap: '
                  'menupunt 5).',
                  'Afterwards the changes are staged but not yet committed (next step: menu '
                  'item 5).',
                  'Danach sind die Änderungen vorgemerkt, aber noch nicht committet (nächster '
                  'Schritt: Menüpunkt 5).'))


def item_commit():
    explain(tr('5  Commit maken (git commit)', '5  Create commit (git commit)',
               '5  Commit erstellen (git commit)'),
            tr('De klaargezette wijzigingen worden als nieuwe stand (commit) opgeslagen.\n'
               'Eerst wordt gecontroleerd of er op GitHub iets nieuws is, en wordt de bibliotheek '
               'gecontroleerd.',
               'The staged changes are saved as a new state (commit).\n'
               'First the menu checks whether there is something new on GitHub, and the library is '
               'validated.',
               'Die vorgemerkten Änderungen werden als neuer Stand (Commit) gespeichert.\n'
               'Vorher wird geprüft, ob auf GitHub etwas Neues liegt, und die Bibliothek wird '
               'geprüft.'))
    if not require_nothing_to_pull():
        return
    code, _ = git_query('diff', '--cached', '--quiet')
    if code == 0:
        say(tr('Er is niets klaargezet. Voer eerst menupunt 4 (git add) uit.',
               'Nothing is staged. Run menu item 4 (git add) first.',
               'Es ist nichts vorgemerkt. Zuerst Menüpunkt 4 (git add) ausführen.'))
        return
    unstaged = unstaged_library_changes()
    if unstaged:
        # The check below reads the files on disk; it only matches the commit when every
        # change to the library is staged.
        say(tr('Deze wijzigingen in de bibliotheek zijn nog niet klaargezet. De controle zou ze '
               'meenemen, de commit niet. Voer eerst menupunt 4 uit.',
               'These changes in the library are not staged. The check would include them, the '
               'commit would not. Run menu item 4 first.',
               'Diese Änderungen in der Bibliothek sind nicht vorgemerkt. Die Prüfung würde sie '
               'einschließen, der Commit nicht. Zuerst Menüpunkt 4 ausführen.'))
        say('\n'.join(unstaged), wrap=False)
        return
    code, out = git_query('diff', '--cached', '--stat')
    say(out, wrap=False)
    if not library_is_valid():
        say(tr('De bibliotheek heeft fouten of waarschuwingen – er wordt niet gecommit.',
               'The library has errors or warnings – nothing is committed.',
               'Die Bibliothek hat Fehler oder Warnungen – es wird nicht committet.'))
        return
    say()
    message = ask(tr('Commitbericht', 'Commit message', 'Commit-Nachricht'), 'Update library')
    git_change(['commit', '-m', message],
               tr('Daarna is de commit lokaal opgeslagen, maar nog niet op GitHub (dat doet later '
                  'menupunt 10).',
                  'Afterwards the commit is saved locally but not yet on GitHub (menu item 10 does '
                  'that later).',
                  'Danach ist der Commit lokal gespeichert, aber noch nicht auf GitHub (dafür '
                  'später Menüpunkt 10).'))


def item_tag():
    global session_tag
    explain(tr('6  Tag zetten (git tag)', '6  Set tag (git tag)', '6  Tag setzen (git tag)'),
            tr('Een tag geeft de laatste commit een releasenaam, bijvoorbeeld v2026.11.0 '
               '(v<jaar>.<maand>.<volgnummer>, kleine v).\nVan deze tag wordt de release gebouwd; '
               'op GitHub start het pushen van de tag (menupunt 11) de release.\nVoordat de tag '
               'gezet wordt, bouwt en controleert het menu de commit precies zoals GitHub dat doet.',
               'A tag gives the last commit a release name, e.g. v2026.11.0 '
               '(v<year>.<month>.<sequence>, lower-case v).\nThe release is built from this tag; on '
               'GitHub, pushing the tag (menu item 11) starts the release.\nBefore setting the '
               'tag, the menu builds and verifies the commit exactly as GitHub will.',
               'Ein Tag gibt dem letzten Commit einen Release-Namen, z. B. v2026.11.0 '
               '(v<Jahr>.<Monat>.<Nummer>, kleines v).\nAus diesem Tag wird das Release gebaut; auf '
               'GitHub startet der Push des Tags (Menüpunkt 11) die Release-Erstellung.\nBevor der '
               'Tag gesetzt wird, baut und prüft das Menü den Commit genau so, wie GitHub es tut.'))
    code, out = git_query('status', '--porcelain')
    if out:
        say(tr('LET OP: er zijn wijzigingen die nog niet gecommit zijn. Die zitten NIET in de tag.',
               'ATTENTION: There are changes that are not committed yet. They are NOT part of the '
               'tag.',
               'ACHTUNG: Es gibt Änderungen, die noch nicht committet sind. Sie sind NICHT im Tag '
               'enthalten.'))
        say(out, wrap=False)
        if not confirm(tr('Toch de tag op de laatste commit zetten?',
                          'Set the tag on the last commit anyway?',
                          'Trotzdem den Tag auf den letzten Commit setzen?')):
            say(tr('Afgebroken. Voer eerst menupunten 4 en 5 uit.',
                   'Cancelled. Run menu items 4 and 5 first.',
                   'Abgebrochen. Zuerst Menüpunkte 4 und 5 ausführen.'))
            return
    tag = ask(tr('Naam van de tag', 'Tag name', 'Name des Tags'), suggest_next_tag())
    if not TAG_PATTERN.match(tag):
        say(tr('"%s" is geen geldige releasetag. Vorm: v<jaar>.<maand>.<volgnummer>, '
               'bijvoorbeeld v2026.11.0.',
               '"%s" is not a valid release tag. Format: v<year>.<month>.<sequence>, '
               'e.g. v2026.11.0.',
               '"%s" ist kein gültiger Release-Tag. Format: v<Jahr>.<Monat>.<Nummer>, '
               'z. B. v2026.11.0.') % tag)
        return
    if tag_exists_locally(tag):
        say(tr('De tag %s bestaat al. Kies een nieuwe naam (volgend nummer).',
               'The tag %s already exists. Please choose a new name (next sequence number).',
               'Der Tag %s existiert schon. Bitte einen neuen Namen wählen (nächste Nummer).') % tag)
        return
    if not preflight(tag):
        say(tr('De proefbouw is mislukt – er wordt geen tag gezet. Los de meldingen hierboven op, '
               'commit opnieuw en probeer het dan weer.',
               'The pre-flight failed – no tag is set. Fix the findings above, commit again and '
               'try again.',
               'Der Probelauf ist fehlgeschlagen – es wird kein Tag gesetzt. Die Meldungen oben '
               'beheben, erneut committen und es dann wieder versuchen.'))
        return
    say()
    if git_change(['tag', '-a', tag, '-m', 'Release %s' % tag],
                  tr('Daarna draagt de laatste commit lokaal de tag %s (volgende stap: menupunt '
                     '10).',
                     'Afterwards the last commit carries the tag %s locally (next step: menu '
                     'item 10).',
                     'Danach trägt der letzte Commit lokal den Tag %s (nächster Schritt: '
                     'Menüpunkt 10).') % tag):
        session_tag = tag


def item_build_test():
    explain(tr('7  Testarchief bouwen (zonder tag)', '7  Build test archive (no tag)',
               '7  Test-Archiv bauen (ohne Tag)'),
            tr('release.py bouwt een archief van de laatste commit, zonder dat er een tag nodig '
               'is.\nNiet-gecommitte wijzigingen zitten er NIET in. Het archief komt in dist/ en is '
               'alleen om te testen. Er verandert niets in git.',
               'release.py builds an archive from the last commit, without needing a tag.\n'
               'Uncommitted changes are NOT included. The archive goes to dist/ and is for '
               'testing only. Nothing is changed in git.',
               'release.py baut ein Archiv aus dem letzten Commit, ohne dass ein Tag nötig ist.\n'
               'Nicht committete Änderungen sind NICHT enthalten. Das Archiv landet in dist/ und '
               'dient nur zum Testen. Es wird nichts in Git verändert.'))
    run_tool('release.py', 'build', '--tag', TEST_TAG, '--allow-untagged', '--out', DIST_DIR)


def item_build_release():
    explain(tr('8  Releasearchief van tag bouwen', '8  Build release archive from tag',
               '8  Release-Archiv aus Tag bauen'),
            tr('release.py bouwt het archief van de commit met de tag – precies zoals het later op '
               'GitHub gebouwd wordt.\nHet archief komt in dist/. Er verandert niets in git.',
               'release.py builds the archive from the commit that carries the tag – exactly as it '
               'will be built on GitHub later.\nThe archive goes to dist/. Nothing is changed in '
               'git.',
               'release.py baut das Archiv aus dem Commit, der den Tag trägt – genau so, wie es '
               'später auf GitHub gebaut wird.\nDas Archiv landet in dist/. Es wird nichts in Git '
               'verändert.'))
    tag = ask('Tag', default_tag())
    if not tag:
        return
    if not tag_exists_locally(tag):
        say(tr('De tag %s bestaat niet (let op hoofdletters). Voer eerst menupunt 6 uit.',
               'The tag %s does not exist (tags are case-sensitive). Run menu item 6 first.',
               'Der Tag %s existiert nicht (Groß-/Kleinschreibung beachten). Zuerst Menüpunkt 6.')
            % tag)
        return
    run_tool('release.py', 'build', '--tag', tag, '--out', DIST_DIR)


def item_verify():
    explain(tr('9  Archief controleren', '9  Verify archive', '9  Archiv prüfen'),
            tr('release.py controleert het nieuwste archief in dist/ zoals de app dat bij het '
               'importeren doet.\nEr wordt niets veranderd.',
               'release.py checks the newest archive in dist/ the way the app does on import.\n'
               'Nothing is changed.',
               'release.py prüft das neueste Archiv in dist/ so, wie es die App beim Import tut.\n'
               'Es wird nichts verändert.'))
    folder = os.path.join(REPO_DIR, DIST_DIR)
    archives = []
    if os.path.isdir(folder):
        archives = [os.path.join(folder, name) for name in os.listdir(folder) if name.endswith('.zbl')]
    if not archives:
        say(tr('In dist/ staat geen archief. Voer eerst menupunt 7 of 8 uit.',
               'There is no archive in dist/. Run menu item 7 or 8 first.',
               'In dist/ liegt kein Archiv. Zuerst Menüpunkt 7 oder 8.'))
        return
    newest = max(archives, key=os.path.getmtime)
    say(tr('Nieuwste archief: %s', 'Newest archive: %s', 'Neuestes Archiv: %s')
        % os.path.relpath(newest, REPO_DIR))
    run_tool('release.py', 'verify', '--strict', os.path.relpath(newest, REPO_DIR))


def item_push_main():
    explain(tr('10  Commits naar GitHub pushen (git push origin main)',
               '10  Push commits to GitHub (git push origin main)',
               '10  Commits zu GitHub pushen (git push origin main)'),
            tr('De lokale commits worden naar GitHub geüpload.\nOp GitHub controleert de workflow '
               '"Validate library" daarna de bibliotheek automatisch.',
               'The local commits are uploaded to GitHub.\nOn GitHub the workflow "Validate '
               'library" then checks the library automatically.',
               'Die lokalen Commits werden auf GitHub hochgeladen.\nAuf GitHub prüft danach der '
               'Workflow "Validate library" die Bibliothek automatisch.'))
    branch = current_branch()
    if branch != MAIN_BRANCH:
        say(tr('De huidige branch is "%s", niet "%s". Schakel eerst over naar %s.',
               'The current branch is "%s", not "%s". Please switch to %s first.',
               'Aktueller Branch ist "%s", nicht "%s". Bitte zuerst auf %s wechseln.')
            % (branch, MAIN_BRANCH, MAIN_BRANCH))
        return
    if not require_nothing_to_pull():
        return
    code, ahead = git_query('rev-list', '--count', '%s/%s..HEAD' % (REMOTE, MAIN_BRANCH))
    if code == 0 and ahead == '0':
        say(tr('Er zijn geen lokale commits die op GitHub ontbreken – niets te pushen.',
               'There are no local commits missing on GitHub – nothing to push.',
               'Es gibt keine lokalen Commits, die auf GitHub fehlen – nichts zu pushen.'))
        return
    code, out = git_query('log', '--oneline', '%s/%s..HEAD' % (REMOTE, MAIN_BRANCH))
    say(out, wrap=False)
    git_change(['push', REMOTE, MAIN_BRANCH],
               tr('Daarna staan de commits op GitHub.', 'Afterwards the commits are on GitHub.',
                  'Danach sind die Commits auf GitHub.'))


def item_push_tag():
    explain(tr('11  Tag naar GitHub pushen (git push origin <tag>)',
               '11  Push tag to GitHub (git push origin <tag>)',
               '11  Tag zu GitHub pushen (git push origin <Tag>)'),
            tr('De tag wordt naar GitHub geüpload. Dat start daar de workflow "Release": die bouwt '
               'het archief, publiceert het onder "Releases" en werkt releases.json bij.',
               'The tag is uploaded to GitHub. This starts the workflow "Release" there: it builds '
               'the archive, publishes it under "Releases" and updates releases.json.',
               'Der Tag wird auf GitHub hochgeladen. Das startet dort den Workflow "Release": er '
               'baut das Archiv, veröffentlicht es unter "Releases" und aktualisiert releases.json.'))
    tag = ask('Tag', default_tag())
    if not tag:
        return
    if not tag_exists_locally(tag):
        say(tr('De tag %s bestaat lokaal niet. Voer eerst menupunt 6 uit.',
               'The tag %s does not exist locally. Run menu item 6 first.',
               'Der Tag %s existiert lokal nicht. Zuerst Menüpunkt 6.') % tag)
        return
    on_github = tag_on_github(tag)
    if on_github is None:
        return
    if on_github:
        say(tr('De tag %s staat al op GitHub – niets te pushen. Zet voor een nieuwe release een '
               'nieuwe tag (menupunt 6).',
               'The tag %s is already on GitHub – nothing to push. For a new release, set a new '
               'tag (menu item 6).',
               'Der Tag %s ist schon auf GitHub – nichts zu pushen. Für ein neues Release einen '
               'neuen Tag setzen (Menüpunkt 6).') % tag)
        return
    if not require_nothing_to_pull():
        return
    code, _ = git_query('merge-base', '--is-ancestor', tag, '%s/%s' % (REMOTE, MAIN_BRANCH))
    if code != 0:
        say(tr('De commit met de tag %s staat nog niet op GitHub. Voer eerst menupunt 10 '
               '(git push origin main) uit.',
               'The commit with the tag %s is not on GitHub yet. Run menu item 10 '
               '(git push origin main) first.',
               'Der Commit mit dem Tag %s ist noch nicht auf GitHub. Zuerst Menüpunkt 10 '
               '(git push origin main) ausführen.') % tag)
        return
    if git_change(['push', REMOTE, tag],
                  tr('Daarna start op GitHub de release.', 'Afterwards the release starts on GitHub.',
                     'Danach startet auf GitHub die Release-Erstellung.')):
        url = actions_url()
        say()
        say(LINE)
        say(tr('Wacht op het groene vinkje onder "Actions" en voer dan menupunt 12 uit '
               '(releases.json staat dan in een nieuwe versie op GitHub). Een cirkel betekent dat '
               'de release nog loopt; een rood kruis dat hij mislukt is: de samenvatting van die '
               'run noemt de oorzaak.',
               'Wait for the green tick under "Actions", then run menu item 12 (releases.json on '
               'GitHub is then in a new version). A circle means the release is still running; a '
               'red cross means it failed: the summary of that run names the cause.',
               'Grünen Haken unter "Actions" abwarten, dann Menüpunkt 12 ausführen (releases.json '
               'liegt dann auf GitHub in neuer Version vor). Ein Kreis heißt, dass das Release noch '
               'läuft; ein rotes Kreuz, dass es fehlgeschlagen ist: die Zusammenfassung dieses '
               'Laufs nennt die Ursache.'))
        if url:
            say('    %s' % url, wrap=False)
        say(LINE)


def item_pull():
    explain(tr('12  Na het groene vinkje: wijzigingen ophalen (git pull)',
               '12  After the green tick: fetch changes (git pull)',
               '12  Nach dem grünen Haken: Änderungen holen (git pull)'),
            tr('Haalt de commits op die nieuw zijn op GitHub – na een release vooral de nieuwe '
               'releases.json.\nPas uitvoeren als onder "Actions" het groene vinkje staat.',
               'Fetches the commits that are new on GitHub – after a release mainly the new '
               'releases.json.\nRun it only when the green tick is shown under "Actions".',
               'Holt die Commits, die auf GitHub neu sind – nach einem Release vor allem die neue '
               'releases.json.\nErst ausführen, wenn unter "Actions" der grüne Haken da ist.'))
    incoming = fetch_and_count_incoming()
    if incoming is None:
        return
    if incoming == 0:
        say(tr('Op GitHub is niets nieuws. Loopt de release nog (cirkel onder "Actions")? '
               'Probeer het dan later opnieuw.',
               'There is nothing new on GitHub. Is the release run still in progress (circle symbol '
               'under "Actions")? Then try again later.',
               'Auf GitHub gibt es nichts Neues. Läuft die Release-Erstellung noch (Kreis-Symbol '
               'unter "Actions")? Dann später nochmals versuchen.'))
        return
    say(tr('Nieuw op GitHub (%d commit(s)):', 'New on GitHub (%d commit(s)):',
           'Auf GitHub neu (%d Commit(s)):') % incoming)
    code, out = git_query('log', '--oneline', 'HEAD..%s/%s' % (REMOTE, MAIN_BRANCH))
    say(out, wrap=False)
    say()
    pull_fast_forward()


def item_toggle_tutorial():
    """Switch the explanations on or off."""
    global tutorial
    tutorial = not tutorial
    say()
    if tutorial:
        say(tr('Uitleg wordt nu getoond.', 'Explanations are now shown.',
               'Erläuterungstexte sind jetzt eingeblendet.'))
    else:
        say(tr('Uitleg wordt nu verborgen.', 'Explanations are now hidden.',
               'Erläuterungstexte sind jetzt ausgeblendet.'))


def toggle_label():
    """Label of menu item 1, depending on the current state."""
    if tutorial:
        return tr('Uitleg verbergen', 'Hide explanations', 'Erläuterungstexte ausblenden')
    return tr('Uitleg tonen', 'Show explanations', 'Erläuterungstexte einblenden')


# Menu entries: key, labels (nl, en, de), git command shown in brackets, function.
# The label of item 1 is set by toggle_label(); items without a pause return to the menu at once.
MENU = [
    ('1', None, '', item_toggle_tutorial),
    ('2', ('Bibliotheek controleren', 'Validate library', 'Bibliothek prüfen'), '', item_validate),
    ('3', ('Status tonen (vergelijking met GitHub)', 'Show status (comparison with GitHub)',
           'Status anzeigen (Vergleich mit GitHub)'), '', item_status),
    ('4', ('Wijzigingen klaarzetten', 'Stage changes', 'Änderungen vormerken'), 'git add',
     item_add),
    ('5', ('Commit maken', 'Create commit', 'Commit erstellen'), 'git commit', item_commit),
    ('6', ('Tag zetten (met proefbouw)', 'Set tag (with pre-flight)',
           'Tag setzen (mit Probelauf)'), 'git tag', item_tag),
    ('7', ('Testarchief bouwen (zonder tag)', 'Build test archive (no tag)',
           'Test-Archiv bauen (ohne Tag)'), '', item_build_test),
    ('8', ('Releasearchief van tag bouwen', 'Build release archive from tag',
           'Release-Archiv aus Tag bauen'), '', item_build_release),
    ('9', ('Nieuwste archief in dist/ controleren', 'Verify newest archive in dist/',
           'Neuestes Archiv in dist/ prüfen'), '', item_verify),
    ('10', ('Commits naar GitHub pushen', 'Push commits to GitHub', 'Commits zu GitHub pushen'),
     'git push origin main', item_push_main),
    ('11', ('Tag naar GitHub pushen (start release)', 'Push tag to GitHub (starts release)',
            'Tag zu GitHub pushen (startet Release)'), 'git push origin <tag>', item_push_tag),
    ('12', ('Na groen vinkje: wijzigingen ophalen', 'After green tick: fetch changes',
            'Nach grünem Haken: Änderungen holen'), 'git pull', item_pull),
]
NO_PAUSE = (item_toggle_tutorial,)


def show_menu():
    say()
    say('=' * 66)
    say(tr('  Zangbundel-bibliotheek – hulpmiddelen', '  Zangbundel library – tools',
           '  Zangbundel-Bibliothek – Werkzeuge'))
    say('=' * 66)
    for key, labels, command, func in MENU:
        label = toggle_label() if func is item_toggle_tutorial else tr(*labels)
        say(('  %2s  %-40s %s' % (key, label, '[%s]' % command if command else '')).rstrip(),
            wrap=False)
    say(tr('   0  Afsluiten', '   0  Exit', '   0  Beenden'))
    say()
    say(tr('  Volgorde release: 2 > 4 > 5 > 6 > 10 > 11 > groen vinkje > 12',
           '  Release sequence: 2 > 4 > 5 > 6 > 10 > 11 > green tick > 12',
           '  Ablauf Release: 2 > 4 > 5 > 6 > 10 > 11 > grüner Haken > 12'))
    if session_tag:
        say(tr('  Tag in deze sessie: %s', '  Tag in this session: %s',
               '  Tag in dieser Sitzung: %s') % session_tag)
    say()


def main():
    setup_console()
    os.chdir(REPO_DIR)
    try:
        choose_language()
        check_git_available()
        actions = {entry[0]: entry[-1] for entry in MENU}
        while True:
            show_menu()
            choice = input(tr('Keuze: ', 'Choice: ', 'Auswahl: ')).strip()
            if choice == '0':
                return 0
            func = actions.get(choice)
            if func is None:
                say(tr('Onbekende keuze.', 'Unknown choice.', 'Unbekannte Auswahl.'))
                continue
            func()
            if func not in NO_PAUSE:
                pause()
    except StopMenu as stop:
        say()
        say(LINE)
        say(str(stop))
        say(LINE)
        pause()
        return 1
    except (EOFError, KeyboardInterrupt):
        say()
        return 0
    except Exception:  # noqa: BLE001 - keep a double-clicked window open on any error
        say()
        say(LINE)
        say(tr('Onverwachte fout in het menu; er is daarna niets meer uitgevoerd:',
               'Unexpected error in the menu; nothing further was run:',
               'Unerwarteter Fehler im Menü; danach wurde nichts mehr ausgeführt:'))
        say(traceback.format_exc(), wrap=False)
        say(LINE)
        pause()
        return 1


if __name__ == '__main__':
    sys.exit(main())
