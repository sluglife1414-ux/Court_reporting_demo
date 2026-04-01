"""
status.py -- Pipeline gas gauge. Run in a separate terminal.
Refreshes every 5 min. Press Enter to force refresh. Ctrl+C to quit.

  python status.py
"""

import io, os, sys, time, subprocess, glob, threading
from datetime import datetime

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SESSION_START = time.time()

FINAL_DELIVERY = 'FINAL_DELIVERY'
KEY_FILES = [
    ('corrected_text.txt',    'AI output (PRECIOUS)'),
    ('cleaned_text_FULL.txt', 'Full cleaned text'),
]
DELIVERY_EXPECTED = [
    ('*_FINAL_FORMATTED.txt',    'Formatted transcript'),
    ('*_FINAL.pdf',              'PDF'),
    ('*_FINAL_TRANSCRIPT.txt',   'Transcript'),
    ('*_CONDENSED.txt',          'Condensed'),
    ('*_DEPOSITION_SUMMARY.txt', 'Summary'),
    ('DELIVERY_CHECKLIST.txt',   'Checklist'),
    ('EXHIBIT_INDEX.txt',        'Exhibit index'),
    ('MEDICAL_TERMS_LOG.txt',    'Medical terms'),
    ('PROOF_OF_WORK.txt',        'Proof of work'),
    ('QA_FLAGS.txt',             'QA flags'),
]


def bar(filled, total, width=20):
    n = round(filled / total * width)
    return '[' + '#' * n + '-' * (width - n) + ']'


def fmt_size(path):
    try:
        kb = os.path.getsize(path) / 1024
        if kb >= 1024:
            return f'{kb/1024:.1f} MB'
        return f'{kb:.0f} KB'
    except FileNotFoundError:
        return 'MISSING'


def git_info():
    try:
        dirty = subprocess.check_output(
            ['git', 'status', '--porcelain'], stderr=subprocess.DEVNULL
        ).decode().strip()
        last = subprocess.check_output(
            ['git', 'log', '--oneline', '-1'], stderr=subprocess.DEVNULL
        ).decode().strip()
        return dirty, last
    except Exception:
        return None, '(git unavailable)'


def context_gauge(elapsed_sec):
    # Proxy: session time. 90 min = full tank.
    minutes = elapsed_sec / 60
    total = 90
    pct = min(minutes / total, 1.0)
    gauge = bar(min(minutes, total), total)
    if pct < 0.33:
        label = 'GREEN'
    elif pct < 0.66:
        label = 'YELLOW'
    elif pct < 0.90:
        label = '*** ORANGE - heads up ***'
    else:
        label = '!!! RED - tell Claude: context check !!!'
    return f'{gauge}  {label} ({minutes:.0f} min)'


def delivery_check():
    lines, found = [], 0
    for pattern, label in DELIVERY_EXPECTED:
        matches = glob.glob(os.path.join(FINAL_DELIVERY, pattern))
        if matches:
            size = fmt_size(matches[0])
            lines.append(f'  OK  {label:<28} {size}')
            found += 1
        else:
            lines.append(f'  --  {label}')
    return lines, found


def render():
    os.system('cls' if os.name == 'nt' else 'clear')
    now = datetime.now().strftime('%H:%M:%S')
    elapsed = time.time() - SESSION_START

    print('=' * 58)
    print(f'  PIPELINE GAS GAUGE                   {now}')
    print('=' * 58)

    print('\nCONTEXT WINDOW (session timer proxy):')
    print(f'  {context_gauge(elapsed)}')
    print('  If ORANGE/RED --> tell Claude: "context check"')

    print('\nGIT:')
    dirty, last = git_info()
    if dirty is None:
        print('  (git unavailable)')
    elif dirty:
        changed = dirty.splitlines()
        print(f'  *** DIRTY -- {len(changed)} uncommitted change(s) ***')
        for l in changed[:5]:
            print(f'     {l}')
        if len(changed) > 5:
            print(f'     ...and {len(changed)-5} more')
    else:
        print('  Clean')
    print(f'  Last commit: {last}')

    print('\nKEY FILES:')
    for fname, label in KEY_FILES:
        size = fmt_size(fname)
        status = 'OK  ' if size != 'MISSING' else 'MISS'
        print(f'  {status}  {label:<32} {size}')

    print(f'\nFINAL_DELIVERY/ (10 expected):')
    lines, found = delivery_check()
    for l in lines:
        print(l)
    gauge = bar(found, 10)
    print(f'\n  {gauge}  {found}/10 files present')

    print('\n' + '=' * 58)
    print('  Press Enter to refresh now.  Ctrl+C to quit.')
    print(f'  Auto-refresh in 5 min.')
    print('=' * 58)
    sys.stdout.flush()


def main():
    print('Starting gas gauge... (Ctrl+C to quit)')
    time.sleep(0.5)

    while True:
        render()
        refresh_event = threading.Event()

        def wait_enter():
            try:
                input()
                refresh_event.set()
            except Exception:
                pass

        t = threading.Thread(target=wait_enter, daemon=True)
        t.start()

        start = time.time()
        while time.time() - start < 300:  # 5 min
            if refresh_event.is_set():
                break
            time.sleep(1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nGauge stopped.')
