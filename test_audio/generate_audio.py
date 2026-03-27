"""
generate_audio.py — Synthetic deposition audio for audio-resolve testing.

Generates sample_depo.mp3 to match sample_depo.rtf timestamps.

The key ambiguity: witness says "Bright Spot" but with a thick Texas drawl
the long-i vowel collapses to a short-a -> sounds like "Brat Spot".
The steno machine writes: Brat Spot (phonetically correct to what it heard).
The correct transcript should read: Bright Spot (industry term).

This is the exact scenario the audio-resolve feature is designed to catch.

Timestamps (from RTF, wall-clock):
  10:02:44  ->  witness says "Brat [Bright] Spot"   ← AMBIGUOUS LINE
  10:03:06  ->  examiner repeats "that Brat Spot"   ← second occurrence
  10:03:53  ->  examiner asks about "the Brat Spot"  ← third occurrence
  10:04:47  ->  witness says "Brat Spot feature"    ← fourth occurrence

Ground truth: all four should be "Bright Spot".

Usage:
  pip install edge-tts
  python generate_audio.py
  (writes sample_depo.mp3 and sample_depo_timestamps.json)
"""

import asyncio
import json
import edge_tts

# ─────────────────────────────────────────────────────────────────────────────
# SCRIPT — what gets spoken and by whom
#
# Each entry: (voice_key, text, timecode_in_rtf)
# timecode_in_rtf matches {\*\cxt H:M:S:0} in sample_depo.rtf
# ─────────────────────────────────────────────────────────────────────────────

# Voices:
#   VIDEOGRAPHER / COURT REPORTER / EXAMINER -> standard US male (Christopher)
#   WITNESS (Earl Ray, 60, Texan) -> Guy with rate slowed, pitch lowered
#   DEFENSE COUNSEL -> standard US female (Jenny)

LINES = [
    # (speaker, ssml_text, rtf_timecode)

    ("reporter",
     "We are on the record. The time is 10:00 a.m. "
     "This is the videotaped deposition of Earl Ray Thibodaux.",
     "10:0:3:0"),

    ("reporter",
     "Mr. Thibodaux, do you solemnly swear that the testimony you are about to give "
     "will be the truth, the whole truth, and nothing but the truth, so help you God?",
     "10:0:22:0"),

    ("witness",
     "I do.",
     "10:0:36:0"),

    ("examiner",
     "Please state your name for the record.",
     "10:0:45:0"),

    # Witness — normal speech
    ("witness",
     "Earl Ray Thibodaux.",
     "10:0:52:0"),

    ("examiner",
     "Where are you currently employed?",
     "10:0:59:0"),

    ("witness",
     "I am a senior petroleum engineer with Lone Star Reservoir Consulting "
     "out of Midland, Texas.",
     "10:1:8:0"),

    ("examiner",
     "How long have you been in the petroleum engineering field?",
     "10:1:20:0"),

    ("witness",
     "Going on 35 years now. Started right out of Texas A and M back in 1991.",
     "10:1:29:0"),

    ("examiner",
     "Are you familiar with seismic interpretation methods used in reservoir analysis?",
     "10:1:44:0"),

    ("witness",
     "Oh yes, sir. That has been the core of my work for the last 20 years. "
     "We use seismic amplitude analysis to identify hydrocarbon-bearing formations.",
     "10:1:55:0"),

    ("examiner",
     "Can you explain what you observed in the seismic data for the Yellowrock formation?",
     "10:2:18:0"),

    # ── KEY LINE ── witness says "Bright Spot" but drawl makes it "Brat Spot"
    # We spell it "Brat" in the SSML — that's what the mic hears, what Whisper
    # will transcribe, and what the steno machine wrote.
    # Ground truth = "Bright Spot". That's what the audio resolver must find.
    ("witness_drawl",
     "Yes, sir. So when we ran the 3-D seismic survey over that area, "
     "we identified what we call a Brat Spot in the amplitude data. "
     "That high-amplitude anomaly right there told us there was gas-charged sand at that depth.",
     "10:2:30:0"),

    ("examiner",
     "What does that Brat Spot indicate specifically?",
     "10:3:5:0"),

    ("witness_drawl",
     "Well, in seismic interpretation, a high-amplitude anomaly like that -- "
     "and that is industry standard terminology -- "
     "it tells us that the acoustic impedance contrast between the reservoir rock "
     "and the overlying shale is very strong. "
     "That is a direct hydrocarbon indicator.",
     "10:3:14:0"),

    ("examiner",
     "Are you saying that the Brat Spot is what led to the recommendation to drill at that location?",
     "10:3:53:0"),

    ("witness_drawl",
     "That is correct. Without that anomaly in the seismic, "
     "we would not have had the confidence to recommend that well location.",
     "10:3:59:0"),

    ("defense",
     "Objection. Leading.",
     "10:4:19:0"),

    ("examiner",
     "I'll rephrase.",
     "10:4:26:0"),

    ("examiner",
     "What was the basis for the well location recommendation in your report?",
     "10:4:30:0"),

    ("witness_drawl",
     "The primary basis was the seismic amplitude anomaly -- "
     "this Brat Spot feature -- "
     "combined with the structural closure we mapped on the formation top.",
     "10:4:40:0"),
]

# ─────────────────────────────────────────────────────────────────────────────
# VOICE CONFIG
# ─────────────────────────────────────────────────────────────────────────────

VOICES = {
    "reporter":     {"voice": "en-US-ChristopherNeural", "rate": "+0%",  "pitch": "+0Hz"},
    "examiner":     {"voice": "en-US-EricNeural",        "rate": "+0%",  "pitch": "+0Hz"},
    "defense":      {"voice": "en-US-JennyNeural",       "rate": "+0%",  "pitch": "+0Hz"},
    # Earl Ray: older, slower, deeper — the drawl is achieved by slowing rate
    # and using "Brat" spelling so the neural voice pronounces it that way
    "witness":      {"voice": "en-US-GuyNeural",         "rate": "-15%", "pitch": "-5Hz"},
    "witness_drawl":{"voice": "en-US-GuyNeural",         "rate": "-22%", "pitch": "-8Hz"},
}


async def speak_line(text, voice, rate, pitch, output_file):
    """Generate one line of speech to an mp3 file."""
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await communicate.save(output_file)


async def generate_all():
    import os, subprocess, tempfile

    out_dir = os.path.dirname(os.path.abspath(__file__))
    segments = []
    timestamps_out = []

    print("Generating speech segments...")
    for idx, (speaker, text, timecode) in enumerate(LINES):
        cfg = VOICES[speaker]
        seg_file = os.path.join(out_dir, f"_seg_{idx:03d}.mp3")

        print(f"  [{idx+1:2d}/{len(LINES)}]  {timecode}  {speaker:<14}  {text[:55]}...")
        await speak_line(text, cfg["voice"], cfg["rate"], cfg["pitch"], seg_file)
        segments.append(seg_file)

        timestamps_out.append({
            "rtf_timecode": timecode,
            "speaker": speaker,
            "text_spoken": text,
            "segment_file": os.path.basename(seg_file),
        })

    # Concatenate all segments into one mp3 using ffmpeg if available,
    # otherwise fall back to just leaving segments for manual join.
    final_mp3 = os.path.join(out_dir, "sample_depo.mp3")
    list_file = os.path.join(out_dir, "_concat_list.txt")

    with open(list_file, "w") as f:
        for seg in segments:
            f.write(f"file '{seg}'\n")

    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", list_file, "-c", "copy", final_mp3],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"\nConcatenated -> {final_mp3}")
            # Clean up segments
            for seg in segments:
                os.remove(seg)
            os.remove(list_file)
        else:
            print(f"\nffmpeg not found or failed — segments left in place.")
            print(f"  Install ffmpeg and re-run, or manually join the _seg_*.mp3 files.")
            print(f"  ffmpeg error: {result.stderr[:200]}")
    except FileNotFoundError:
        print(f"\nffmpeg not found - segments left in place.")
        print(f"  Install ffmpeg (winget install ffmpeg) then re-run to get single mp3.")

    # Write ground truth / timestamp map
    ground_truth = {
        "description": "Synthetic deposition audio — Texas drawl 'Bright Spot' sounds like 'Brat Spot'",
        "ambiguous_term": {
            "steno_wrote": "Brat Spot",
            "correct_term": "Bright Spot",
            "reason": "60-year-old Texas petroleum engineer. Long-i vowel collapses to short-a under drawl. 'Bright' -> 'Braht' -> steno hears 'Brat'.",
            "occurrences": [
                {"rtf_timecode": "10:2:44:0", "line_approx": 35},
                {"rtf_timecode": "10:3:6:0",  "line_approx": 39},
                {"rtf_timecode": "10:3:54:0", "line_approx": 45},
                {"rtf_timecode": "10:4:47:0", "line_approx": 51},
            ]
        },
        "lines": timestamps_out,
        "audio_file": "sample_depo.mp3",
        "rtf_file": "sample_depo.rtf",
    }

    gt_file = os.path.join(out_dir, "sample_depo_ground_truth.json")
    with open(gt_file, "w", encoding="utf-8") as f:
        json.dump(ground_truth, f, indent=2, ensure_ascii=False)

    print(f"Ground truth -> {gt_file}")
    print("\nDone. Key ambiguity at RTF timecode 10:2:44:0")
    print("  Steno wrote: 'Brat Spot'")
    print("  Correct term: 'Bright Spot'")
    print("  Audio resolver should catch this via Whisper on the 10-sec clip.")


if __name__ == "__main__":
    asyncio.run(generate_all())
