"""
Rule 190 8-second MIDI renderer.

- Toroidal boundary for music
- Fixed-zero boundary for validation
- Birth: note_on at step boundary; Death: note_off at step boundary
- Optional staccato gate: also send note_off for any cell that remains on
- Exact 8 seconds by BPM/PPQ/ticks-per-step

Requires: mido (pip install mido)
"""

from dataclasses import dataclass
from typing import Optional, Iterable, Union, List, Tuple, Set
import math

try:
    import mido
except ImportError as e:
    raise SystemExit(
        "This script requires the mido package.\n"
        "Install it via: pip install mido"
    )

# Cellular automaton (Rule 190)

RULE190 = {
    0b111: 1, 0b110: 0, 0b101: 1, 0b100: 1,
    0b011: 1, 0b010: 1, 0b001: 1, 0b000: 0,
}

def next_rule190_toroidal(row: List[int]) -> List[int]:
    """Toroidal boundary (for music rendering)."""
    W = len(row)
    nxt = [0] * W
    for i in range(W):
        l = row[(i - 1) % W]
        c = row[i]
        r = row[(i + 1) % W]
        nxt[i] = RULE190[(l << 2) | (c << 1) | r]
    return nxt

def next_rule190_fixed0(row: List[int]) -> List[int]:
    """Fixed-zero boundary (for validation)."""
    W = len(row)
    nxt = [0] * W
    for i in range(W):
        l = row[i - 1] if i > 0     else 0
        c = row[i]
        r = row[i + 1] if i < W - 1 else 0
        nxt[i] = RULE190[(l << 2) | (c << 1) | r]
    return nxt

# Useful math for validation

def row_to_int_anchor_rightmost(row: List[int]) -> int:
    """
    Interpret the finite 0/1 row by anchoring the RIGHTMOST 1 to bit 0
    and packing bits leftward.
    """
    # find rightmost 1
    idx = -1
    for i in range(len(row) - 1, -1, -1):
        if row[i]:
            idx = i
            break
    if idx == -1:
        return 0
    x = 0
    bit = 0
    for k in range(idx, -1, -1):
        if row[k]:
            x |= 1 << bit
        bit += 1
    return x


def rule190_single_one_sequence(n: int) -> List[int]:
    """
    a_t = 4 a_{t-1} + a_{t-2} - 4 a_{t-3},  with a0=1, a1=7, a2=29
    """
    if n <= 0:
        return []
    if n == 1:
        return [1]
    if n == 2:
        return [1, 7]
    a = [1, 7, 29]
    for _ in range(3, n):
        a.append(4*a[-1] + a[-2] - 4*a[-3])
    return a[:n]

# Scale / pitch mapping helpers

NAT_MINOR_STEPS = [0, 2, 3, 5, 7, 8, 10]  # Scale degrees in semitones

def build_scale_across_width(width: int, root: int = 60,
                             steps: Iterable[int] = NAT_MINOR_STEPS,
                             span_octaves: int = 3) -> List[int]:
    pool: List[int] = []
    octv = 0
    # Keep stacking until we have enough
    while len(pool) < width:
        for d in steps:
            pool.append(root + 12 * octv + d)
            if len(pool) == width:
                break
        octv += 1
    return pool

# MIDI rendering

@dataclass
class RenderConfig:
    bpm: int = 120
    ppq: int = 480
    q:   int = 240
    gate: Optional[float] = None  # None=sustain; else 0<gate<1 (fraction of step)
    filename: str = "rule190_8s.mid"

def seconds_per_step(cfg: RenderConfig) -> float:
    return 60.0 / cfg.bpm * (cfg.q / cfg.ppq)

def steps_for_8_seconds(cfg: RenderConfig) -> int:
    return math.floor(8.0 / seconds_per_step(cfg))

def schedule_events(row0: List[int], scale: List[int], cfg: RenderConfig):
    """
    Build (abs_tick, mido.Message/MetaMessage) for either:
      - sustain mode (gate is None): note_on at births, note_off at deaths + final flush
      - staccato mode (gate is set): per-step note_on for every '1' and gate note_off

    Same-tick ordering:
      1) meta (tempo)
      2) note_off
      3) note_on
    """
    W = len(row0)
    steps = steps_for_8_seconds(cfg)
    row = row0[:]
    age = [0] * W
    events: List[Tuple[int, Union[mido.Message, mido.MetaMessage]]] = []

    def add(tick: int, msg):
        events.append((tick, msg))

    # Put tempo first at tick 0
    tempo_us_per_beat = mido.bpm2tempo(cfg.bpm)
    add(0, mido.MetaMessage('set_tempo', tempo=tempo_us_per_beat, time=0))

    staccato = (cfg.gate is not None) and (cfg.gate > 0.0)
    gate_frac = None if cfg.gate is None else max(0.0, min(0.9999, float(cfg.gate)))  # keep inside step

    # Track which notes are currently on (for sustain mode + final flush)
    active_notes: Set[int] = set()

    for s in range(steps):
        base_tick = s * cfg.q
        nxt = next_rule190_toroidal(row)

        if not staccato:
            # Sustain-until-death mode
            births, deaths = [], []
            for i in range(W):
                was = (row[i] == 1)
                now = (nxt[i] == 1)
                note = scale[i]
                if now and not was:
                    age[i] = 1
                    births.append((note, i))
                elif now and was:
                    age[i] += 1
                elif was and not now:
                    age[i] = 0
                    deaths.append((note, i))

            # deaths before births on the same tick
            for note, _ in deaths:
                if note in active_notes:
                    add(base_tick, mido.Message('note_off', channel=0, note=note, velocity=0, time=0))
                    active_notes.discard(note)
            for note, idx in births:
                vel = min(30 + 10 * age[idx], 110)
                add(base_tick, mido.Message('note_on', channel=0, note=note, velocity=vel, time=0))
                active_notes.add(note)

        else:
            # Staccato mode: re-trigger every step for all '1' cells in nxt
            off_tick = base_tick + int(cfg.q * gate_frac)
            for i in range(W):
                if nxt[i] == 1:
                    age[i] = (age[i] + 1) if (row[i] == 1) else 1
                    note = scale[i]
                    vel = min(30 + 10 * age[i], 110)
                    add(base_tick, mido.Message('note_on', channel=0, note=note, velocity=vel, time=0))
                    add(off_tick, mido.Message('note_off', channel=0, note=note, velocity=0, time=0))
                else:
                    age[i] = 0

        row = nxt

    # Final flush at the exact 8s boundary for sustain mode
    if not staccato:
        end_tick = steps * cfg.q
        for note in sorted(active_notes):
            add(end_tick, mido.Message('note_off', channel=0, note=note, velocity=0, time=0))
        active_notes.clear()

    # sort & pack (meta first, then off, then on)
    def sort_key(item):
        tick, msg = item
        if isinstance(msg, mido.MetaMessage):
            pri = -1
        elif isinstance(msg, mido.Message):
            pri = 0 if msg.type == 'note_off' else (1 if msg.type == 'note_on' else 2)
        else:
            pri = 2
        return (tick, pri)

    events.sort(key=sort_key)

    mid = mido.MidiFile(ticks_per_beat=cfg.ppq)
    track = mido.MidiTrack()
    mid.tracks.append(track)

    last_tick = 0
    for abs_tick, msg in events:
        delta = abs_tick - last_tick
        msg.time = max(0, delta)
        track.append(msg)
        last_tick = abs_tick

    mid.save(cfg.filename)
    return cfg.filename

# Example usage

def main():
    W_music = 32
    row0_music = [0] * W_music
    row0_music[W_music // 2] = 1  # centered for symmetry in audio

    scale = build_scale_across_width(W_music, root=60, steps=NAT_MINOR_STEPS, span_octaves=3)

    cfg = RenderConfig(
        bpm=120,
        ppq=480,
        q=240,
        gate=None,
        filename="rule190_8s.mid"
    )

    # Validation (fixed-zero, wide enough, single 1)
    steps = steps_for_8_seconds(cfg)
    max_check = min(steps, 20)  # check first 20 rows

    # Choose a width that safely contains the light cone: 1 + 2*max_check
    W_val = 1 + 2 * max_check
    row_val = [0] * W_val
    # Seed at the center so both sides can grow without hitting boundaries
    center = max_check
    row_val[center] = 1

    seq_expected = rule190_single_one_sequence(max_check)
    ok = True
    for t in range(max_check):
        as_int = row_to_int_anchor_rightmost(row_val)
        if as_int != seq_expected[t]:
            ok = False
            print(f"[warn] t={t}: got={as_int} != expected={seq_expected[t]}")
        row_val = next_rule190_fixed0(row_val)

    if ok:
        print("[ok] First rows match the Rule 190 sequence (fixed-zero, anchored).")

    # Render MIDI
    out = schedule_events(row0_music, scale, cfg)
    print(f"Wrote {out} (ca 8.00 s).")

if __name__ == "__main__":
    main()
