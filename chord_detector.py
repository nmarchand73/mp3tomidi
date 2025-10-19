"""
Chord Detection Module

Analyzes MIDI files to detect chord progressions.
Identifies chord types (major, minor, 7th, etc.) and timing.
"""

import mido
import numpy as np
from collections import defaultdict, Counter
from typing import List, Tuple, Dict, Optional


class ChordDetector:
    """Detects chord progressions from MIDI files."""

    # Chord templates: intervals from root (in semitones)
    CHORD_TEMPLATES = {
        # Triads
        'major': [0, 4, 7],
        'minor': [0, 3, 7],
        'diminished': [0, 3, 6],
        'augmented': [0, 4, 8],

        # Seventh chords
        'dominant7': [0, 4, 7, 10],      # G7
        'major7': [0, 4, 7, 11],         # Cmaj7
        'minor7': [0, 3, 7, 10],         # Cm7
        'minorMaj7': [0, 3, 7, 11],      # CmM7
        'diminished7': [0, 3, 6, 9],     # Cdim7
        'halfDiminished7': [0, 3, 6, 10], # Cm7b5

        # Extended chords (simplified)
        'dominant9': [0, 4, 7, 10, 14],  # G9
        'major9': [0, 4, 7, 11, 14],     # Cmaj9

        # Suspended chords
        'sus2': [0, 2, 7],
        'sus4': [0, 5, 7],
    }

    # Note names
    NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

    # Quality symbols for display
    QUALITY_SYMBOLS = {
        'major': '',
        'minor': 'm',
        'diminished': 'dim',
        'augmented': 'aug',
        'dominant7': '7',
        'major7': 'maj7',
        'minor7': 'm7',
        'minorMaj7': 'mM7',
        'diminished7': 'dim7',
        'halfDiminished7': 'm7b5',
        'dominant9': '9',
        'major9': 'maj9',
        'sus2': 'sus2',
        'sus4': 'sus4',
    }

    def __init__(self, quantize_beats: float = 1.0, min_notes: int = 2):
        """
        Initialize chord detector.

        Args:
            quantize_beats: Time quantization in beats (1.0 = quarter note grid)
            min_notes: Minimum notes required to consider as a chord
        """
        self.quantize_beats = quantize_beats
        self.min_notes = min_notes

    def detect_chords(self, midi_file: mido.MidiFile,
                     verbose: bool = False) -> List[Tuple[int, str, List[int]]]:
        """
        Detect chord progression from MIDI file.

        Args:
            midi_file: MIDI file object
            verbose: Print debug information

        Returns:
            List of (time_in_ticks, chord_name, note_list) tuples
        """
        # Extract notes with timing
        notes = self._extract_notes(midi_file)

        if verbose:
            print(f"  Extracted {len(notes)} notes")

        # Quantize notes to beat grid
        time_slices = self._quantize_notes(notes, midi_file.ticks_per_beat)

        if verbose:
            print(f"  Quantized into {len(time_slices)} time slices")

        # Detect chord at each time slice
        chords = []
        for time, notes_at_time in time_slices.items():
            if len(notes_at_time) >= self.min_notes:
                chord_name, chord_notes = self._identify_chord(notes_at_time)
                if chord_name:
                    chords.append((time, chord_name, chord_notes))

        if verbose:
            print(f"  Detected {len(chords)} chords")

        return chords

    def _extract_notes(self, midi_file: mido.MidiFile) -> List[Dict]:
        """Extract all notes with start time and pitch."""
        notes = []

        for track in midi_file.tracks:
            absolute_time = 0
            active_notes = {}  # note_number -> start_time

            for msg in track:
                absolute_time += msg.time

                if msg.type == 'note_on' and msg.velocity > 0:
                    active_notes[msg.note] = absolute_time
                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    if msg.note in active_notes:
                        start_time = active_notes[msg.note]
                        notes.append({
                            'note': msg.note,
                            'start': start_time,
                            'end': absolute_time,
                            'duration': absolute_time - start_time
                        })
                        del active_notes[msg.note]

        # Sort by start time
        notes.sort(key=lambda n: n['start'])
        return notes

    def _quantize_notes(self, notes: List[Dict],
                       ticks_per_beat: int) -> Dict[int, List[int]]:
        """
        Quantize notes to beat grid and group simultaneous notes.

        Returns:
            Dictionary of {quantized_time: [note_numbers]}
        """
        quantize_ticks = int(ticks_per_beat * self.quantize_beats)
        time_slices = defaultdict(list)

        for note in notes:
            # Quantize start time to grid
            quantized_time = (note['start'] // quantize_ticks) * quantize_ticks
            time_slices[quantized_time].append(note['note'])

        # Remove duplicates in each slice
        for time in time_slices:
            time_slices[time] = sorted(set(time_slices[time]))

        return time_slices

    def _identify_chord(self, notes: List[int]) -> Tuple[Optional[str], List[int]]:
        """
        Identify chord from list of MIDI note numbers.

        Returns:
            (chord_name, notes) or (None, notes) if no match
        """
        # Get unique pitch classes
        pitch_classes = sorted(set(note % 12 for note in notes))

        if len(pitch_classes) < 2:
            return None, notes

        # Try to match chord templates
        best_match = None
        best_score = 0

        # Try each possible root
        for root in range(12):
            for quality, intervals in self.CHORD_TEMPLATES.items():
                # Build expected pitch classes for this chord
                expected_pcs = [(root + interval) % 12 for interval in intervals]

                # Calculate match score
                matched = len(set(pitch_classes) & set(expected_pcs))
                total = len(set(pitch_classes) | set(expected_pcs))
                score = matched / total if total > 0 else 0

                # Bonus for exact match
                if set(pitch_classes) == set(expected_pcs):
                    score += 0.5

                if score > best_score:
                    best_score = score
                    best_match = (root, quality)

        # Require at least 60% match
        if best_score >= 0.6 and best_match:
            root, quality = best_match
            chord_name = self._format_chord_name(root, quality)
            return chord_name, notes
        else:
            # Unknown chord - just show notes
            note_names = [self.NOTE_NAMES[n % 12] for n in pitch_classes]
            return f"[{'+'.join(note_names)}]", notes

    def _format_chord_name(self, root: int, quality: str) -> str:
        """Format chord name for display."""
        root_name = self.NOTE_NAMES[root]
        quality_symbol = self.QUALITY_SYMBOLS.get(quality, quality)
        return f"{root_name}{quality_symbol}"

    def get_progression_summary(self, chords: List[Tuple[int, str, List[int]]],
                               ticks_per_beat: int,
                               tempo: int = 500000) -> str:
        """
        Generate a readable summary of the chord progression.

        Args:
            chords: List of detected chords
            ticks_per_beat: MIDI ticks per beat
            tempo: Tempo in microseconds per beat

        Returns:
            Formatted string summary
        """
        if not chords:
            return "No chords detected"

        lines = []
        lines.append("Chord Progression Detected:")
        lines.append("─" * 60)

        # Convert time to measures (assuming 4/4 time)
        beats_per_measure = 4

        current_measure = -1
        for time_ticks, chord_name, notes in chords:
            # Calculate measure number
            beat = time_ticks / ticks_per_beat
            measure = int(beat / beats_per_measure) + 1

            # Show measure breaks
            if measure != current_measure:
                current_measure = measure
                lines.append(f"\nMeasure {measure}:")

            # Format chord entry
            notes_str = ', '.join(self.NOTE_NAMES[n % 12] for n in sorted(set(notes)))
            lines.append(f"  {chord_name:12s} ({notes_str})")

        lines.append("─" * 60)

        # Analyze progression
        chord_names = [chord_name for _, chord_name, _ in chords]
        lines.append(f"Total chords: {len(chord_names)}")
        lines.append(f"Unique chords: {len(set(chord_names))}")

        # Most common chords
        most_common = Counter(chord_names).most_common(3)
        if most_common:
            lines.append(f"Most frequent: {', '.join(f'{c}({n}x)' for c, n in most_common)}")

        return '\n'.join(lines)

    def analyze_key(self, chords: List[Tuple[int, str, List[int]]]) -> str:
        """
        Attempt to identify the key from chord progression.

        Simple heuristic: most common root note is likely the tonic.
        """
        if not chords:
            return "Unknown"

        # Extract root notes from chord names
        roots = []
        for _, chord_name, _ in chords:
            # Parse root from chord name (first 1-2 chars)
            if '#' in chord_name:
                root_str = chord_name[:2]
            else:
                root_str = chord_name[0]

            if root_str in self.NOTE_NAMES:
                roots.append(root_str)

        if not roots:
            return "Unknown"

        # Find most common root
        most_common_root = Counter(roots).most_common(1)[0][0]

        # Check if mostly major or minor chords
        minor_count = sum(1 for _, chord_name, _ in chords if 'm' in chord_name and 'maj' not in chord_name)
        major_count = len(chords) - minor_count

        if minor_count > major_count:
            return f"{most_common_root} minor (likely)"
        else:
            return f"{most_common_root} major (likely)"
