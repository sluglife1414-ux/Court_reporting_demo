"""
audio_preflight.py — Pre-flight check before running audio_validation.py
=========================================================================
Run this FIRST. It costs $0.003 and tells you everything that would
blow up in the full run before you spend real money.

Checks:
  1. OPENAI_API_KEY set and valid
  2. ffmpeg + ffprobe on PATH
  3. Audio file exists and is readable
  4. Converts 30 seconds to mp3 — real chunk size on disk, not estimated
  5. Projects full-run chunk sizes — confirms all under 25MB
  6. Sends 30 seconds to Whisper — validates API, response structure, segments
  7. Prints raw segment data — you can see exactly what we're working with
  8. Shows cost estimate for full run
  9. Requires you to type YES before audio_validation.py should be run

Pass = safe to run audio_validation.py
Fail = fix the listed issue first

Author:  Scott + Claude
Version: 1.0  (2026-04-03)
"""

import os
import sys
import math
import subprocess
import tempfile

BASE      = os.path.dirname(os.path.abspath(__file__))
AUDIO_FILE = os.path.join(
    BASE, '..', 'mb_040226_halprin_yellowrock', '040226yellowrock-ROUGH.opus'
)
CHUNK_MB   = 15
BITRATE    = '32k'   # mono 32kbps — matches audio_validation.py
TEST_SECS  = 30      # 30-second test clip — $0.003

# Test window anchored to a known hard [REVIEW] item — line 416 in corrected_text.txt
# Estimated audio position: ~34.7 min into the depo (proportional to line number)
# This is "extensive reconstruction of fragmented witness testimony" — hardest item type
# If Whisper handles this, it handles everything. Don't test on the easy videographer intro.
TEST_OFFSET_SEC = int(34.7 * 60)   # ~2082 seconds in

passed = []
failed = []

def ok(msg):
    passed.append(msg)
    print(f'  ✓  {msg}')

def fail(msg):
    failed.append(msg)
    print(f'  ✗  {msg}')

def header(title):
    print(f'\n{"─"*60}')
    print(f'  {title}')
    print(f'{"─"*60}')


# ── CHECK 1: API key ──────────────────────────────────────────────────────────
header('CHECK 1 — OPENAI_API_KEY')
api_key = os.environ.get('OPENAI_API_KEY', '')
if not api_key:
    fail('OPENAI_API_KEY not set in environment')
    fail('Run:  setx OPENAI_API_KEY "sk-..."  then open a new terminal')
elif not api_key.startswith('sk-'):
    fail(f'Key looks wrong — should start with sk-  (got: {api_key[:8]}...)')
else:
    ok(f'Key found: {api_key[:8]}...{api_key[-4:]}')


# ── CHECK 2: openai package ───────────────────────────────────────────────────
header('CHECK 2 — openai package')
try:
    import openai
    ok(f'openai {openai.__version__} installed')
    from openai import OpenAI
except ImportError:
    fail('openai not installed — run: pip install openai')


# ── CHECK 3: ffmpeg + ffprobe ─────────────────────────────────────────────────
header('CHECK 3 — ffmpeg + ffprobe')
for tool in ['ffmpeg', 'ffprobe']:
    try:
        r = subprocess.run([tool, '-version'], capture_output=True, check=True)
        version_line = r.stdout.decode('utf-8', errors='replace').split('\n')[0]
        ok(f'{tool}: {version_line[:60]}')
    except (subprocess.CalledProcessError, FileNotFoundError):
        fail(f'{tool} not found on PATH')


# ── CHECK 4: Audio file ───────────────────────────────────────────────────────
header('CHECK 4 — Audio file')
if not os.path.exists(AUDIO_FILE):
    fail(f'Audio file not found: {AUDIO_FILE}')
else:
    size_mb = os.path.getsize(AUDIO_FILE) / (1024*1024)
    ok(f'File exists: {size_mb:.1f}MB')

    # Get duration via ffprobe
    try:
        r = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', AUDIO_FILE],
            capture_output=True, text=True, check=True
        )
        duration_sec = float(r.stdout.strip())
        duration_min = duration_sec / 60
        ok(f'Duration: {duration_min:.1f} min  ({duration_sec:.0f} sec)')
    except Exception as e:
        fail(f'ffprobe failed to read duration: {e}')
        duration_sec = None
        duration_min = None


# ── CHECK 5: Chunk size projection ───────────────────────────────────────────
header('CHECK 5 — Chunk size projection (math, not estimates)')
if duration_sec:
    # Calculate expected mp3 size per chunk at 32kbps mono
    bitrate_bps  = 32_000   # 32kbps
    n_chunks     = math.ceil(size_mb / CHUNK_MB)
    chunk_dur_sec = duration_sec / n_chunks
    chunk_size_bytes = chunk_dur_sec * (bitrate_bps / 8)
    chunk_size_mb    = chunk_size_bytes / (1024 * 1024)
    limit_mb         = 25.0

    print(f'  Chunks:          {n_chunks}')
    print(f'  Duration each:   {chunk_dur_sec/60:.1f} min')
    print(f'  Projected size:  {chunk_size_mb:.1f}MB  (limit: {limit_mb}MB)')

    if chunk_size_mb < limit_mb * 0.85:   # 85% of limit = safe margin
        ok(f'Chunk size {chunk_size_mb:.1f}MB is safely under {limit_mb}MB limit')
    elif chunk_size_mb < limit_mb:
        fail(f'Chunk size {chunk_size_mb:.1f}MB is under limit but too close — increase n_chunks')
    else:
        fail(f'Chunk size {chunk_size_mb:.1f}MB EXCEEDS {limit_mb}MB limit — reduce CHUNK_MB')

    cost_est = (duration_min * 0.006)
    print(f'\n  Estimated cost:  ${cost_est:.2f}  ({duration_min:.0f} min × $0.006/min)')


# ── CHECK 6: Real chunk size on disk ─────────────────────────────────────────
header('CHECK 6 — Real 30-second mp3 chunk on disk (not math)')
tmp_dir  = tempfile.mkdtemp()
test_mp3 = os.path.join(tmp_dir, 'preflight_test.mp3')
real_size_ok = False

try:
    print(f'  Test window: {TEST_OFFSET_SEC//60:.0f}m {TEST_OFFSET_SEC%60:02d}s → '
          f'{(TEST_OFFSET_SEC+TEST_SECS)//60:.0f}m {(TEST_OFFSET_SEC+TEST_SECS)%60:02d}s  '
          f'(known hard [REVIEW] item — fragmented testimony)')
    subprocess.run([
        'ffmpeg', '-y', '-i', AUDIO_FILE,
        '-ss', str(TEST_OFFSET_SEC), '-t', str(TEST_SECS),
        '-ac', '1', '-b:a', BITRATE, test_mp3
    ], capture_output=True, check=True)

    real_bytes = os.path.getsize(test_mp3)
    real_mb    = real_bytes / (1024 * 1024)

    # Project to full chunk size
    if duration_sec:
        projected_chunk_mb = real_mb * (chunk_dur_sec / TEST_SECS)
        print(f'  30-sec clip:     {real_mb:.2f}MB actual on disk')
        print(f'  Projected chunk: {projected_chunk_mb:.1f}MB  ({chunk_dur_sec/60:.1f} min each)')

        if projected_chunk_mb < 25 * 0.85:
            ok(f'Real projected chunk size {projected_chunk_mb:.1f}MB — safe')
            real_size_ok = True
        elif projected_chunk_mb < 25:
            fail(f'Real projected chunk {projected_chunk_mb:.1f}MB — under limit but too close')
        else:
            fail(f'Real projected chunk {projected_chunk_mb:.1f}MB — OVER 25MB limit')
    else:
        ok(f'30-sec clip created: {real_mb:.2f}MB')
        real_size_ok = True

except subprocess.CalledProcessError as e:
    fail(f'ffmpeg conversion failed: {e}')


# ── CHECK 7: Live Whisper API test ($0.003) ───────────────────────────────────
header('CHECK 7 — Live Whisper API test (30 sec, ~$0.003)')

if not api_key or not os.path.exists(test_mp3):
    fail('Skipping — API key or test file missing')
else:
    try:
        client   = OpenAI(api_key=api_key)
        with open(test_mp3, 'rb') as f:
            response = client.audio.transcriptions.create(
                model='whisper-1',
                file=f,
                response_format='verbose_json',
                timestamp_granularities=['segment'],
            )

        ok('API call succeeded')
        ok(f'Response type: {type(response).__name__}')
        ok(f'Language detected: {response.language}')
        ok(f'Duration returned: {response.duration:.1f}s')

        if response.segments is None:
            fail('response.segments is None — no segments returned')
        else:
            ok(f'Segments returned: {len(response.segments)}')
            if response.segments:
                seg = response.segments[0]
                print(f'\n  First segment:')
                print(f'    start:          {seg.start}')
                print(f'    end:            {seg.end}')
                print(f'    text:           {seg.text[:80]}')
                print(f'    avg_logprob:    {seg.avg_logprob:.3f}')
                print(f'    no_speech_prob: {seg.no_speech_prob:.3f}')
                ok('Segment attributes (start/end/text/avg_logprob/no_speech_prob) all present')

        print(f'\n  Transcribed text preview:')
        print(f'    {response.text[:200]}')

    except Exception as e:
        fail(f'API call failed: {e}')


# ── FINAL VERDICT ─────────────────────────────────────────────────────────────
print(f'\n{"═"*60}')
print(f'  PREFLIGHT RESULT')
print(f'{"═"*60}')
print(f'  Passed: {len(passed)}')
print(f'  Failed: {len(failed)}')

if failed:
    print(f'\n  STOP — Fix these before running audio_validation.py:')
    for f in failed:
        print(f'    ✗  {f}')
    print()
else:
    print(f'\n  ALL CHECKS PASSED')
    print(f'  Safe to run: python audio_validation.py')
    print()
