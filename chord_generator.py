"""
Chord MIDI Generator Module

Generates simplified chord-only MIDI files from detected chord progressions.
"""

import mido
from mido import Message, MidiFile, MidiTrack, MetaMessage
from typing import List, Tuple


class ChordGenerator:
    """Generates chord MIDI files from chord progressions."""

    # Middle C octave for reference
    MIDDLE_C_OCTAVE = 5

    def __init__(self):
        """Initialize the chord generator."""
        pass

    def generate_chord_midi(self,
                           chords: List[Tuple[int, str, List[int]]],
                           output_path: str,
                           voicing: str = 'block',
                           octave: int = 4,
                           velocity: int = 80,
                           tempo_bpm: int = 120,
                           ticks_per_beat: int = 480) -> None:
        """
        Generate a MIDI file from detected chord progression.

        Args:
            chords: List of (time_ticks, chord_name, note_list) tuples
            output_path: Path to save MIDI file
            voicing: Chord voicing style ('block', 'arpeggio', 'broken')
            octave: Base octave for chords (4 = middle C octave)
            velocity: Note velocity (0-127)
            tempo_bpm: Tempo in beats per minute
            ticks_per_beat: MIDI ticks per beat
        """
        if not chords:
            print("  Warning: No chords to generate")
            return

        # Create MIDI file
        midi = MidiFile(ticks_per_beat=ticks_per_beat)
        track = MidiTrack()
        midi.tracks.append(track)

        # Set tempo
        microseconds_per_beat = mido.bpm2tempo(tempo_bpm)
        track.append(MetaMessage('set_tempo', tempo=microseconds_per_beat, time=0))

        # Set time signature (4/4)
        track.append(MetaMessage('time_signature', numerator=4, denominator=4, time=0))

        # Add track name
        track.append(MetaMessage('track_name', name='Chord Progression', time=0))

        # Generate notes based on voicing
        if voicing == 'block':
            self._generate_block_chords(track, chords, octave, velocity, ticks_per_beat)
        elif voicing == 'arpeggio':
            self._generate_arpeggio(track, chords, octave, velocity, ticks_per_beat)
        elif voicing == 'broken':
            self._generate_broken_chords(track, chords, octave, velocity, ticks_per_beat)
        else:
            raise ValueError(f"Unknown voicing style: {voicing}")

        # End of track
        track.append(MetaMessage('end_of_track', time=0))

        # Save MIDI file
        midi.save(output_path)
        print(f"  ✓ Generated chord MIDI: {output_path}")
        print(f"    Style: {voicing}, Octave: {octave}, Tempo: {tempo_bpm} BPM")

    def _generate_block_chords(self, track: MidiTrack,
                               chords: List[Tuple[int, str, List[int]]],
                               octave: int, velocity: int,
                               ticks_per_beat: int) -> None:
        """Generate block chord voicing (all notes played simultaneously)."""
        current_time = 0

        for i, (chord_time, chord_name, notes) in enumerate(chords):
            # Calculate duration until next chord (or 4 beats if last chord)
            if i + 1 < len(chords):
                next_chord_time = chords[i + 1][0]
                duration = next_chord_time - chord_time
            else:
                duration = ticks_per_beat * 4  # Default to 4 beats

            # Ensure minimum duration
            duration = max(duration, ticks_per_beat)

            # Time delta from current position
            delta_time = chord_time - current_time

            # Normalize notes to target octave
            normalized_notes = self._normalize_to_octave(notes, octave)

            # Note on messages (first note has time delta, rest are simultaneous)
            for j, note in enumerate(normalized_notes):
                time = delta_time if j == 0 else 0
                track.append(Message('note_on', note=note, velocity=velocity, time=time))

            # Note off messages (first note has duration delta)
            for j, note in enumerate(normalized_notes):
                time = duration if j == 0 else 0
                track.append(Message('note_off', note=note, velocity=0, time=time))

            # Update current time
            current_time = chord_time + duration

    def _generate_arpeggio(self, track: MidiTrack,
                          chords: List[Tuple[int, str, List[int]]],
                          octave: int, velocity: int,
                          ticks_per_beat: int) -> None:
        """Generate arpeggiated chord voicing (notes played sequentially ascending)."""
        current_time = 0

        for i, (chord_time, chord_name, notes) in enumerate(chords):
            # Calculate total duration for this chord
            if i + 1 < len(chords):
                next_chord_time = chords[i + 1][0]
                total_duration = next_chord_time - chord_time
            else:
                total_duration = ticks_per_beat * 4

            # Normalize notes
            normalized_notes = sorted(self._normalize_to_octave(notes, octave))

            # Divide duration among notes
            note_duration = total_duration // len(normalized_notes)

            # Time delta to start of this chord
            delta_time = chord_time - current_time

            # Play each note in sequence
            for j, note in enumerate(normalized_notes):
                # Note on
                time = delta_time if j == 0 else 0
                track.append(Message('note_on', note=note, velocity=velocity, time=time))

                # Note off after note_duration
                track.append(Message('note_off', note=note, velocity=0, time=note_duration))

                # Next delta is 0 (notes are consecutive)
                delta_time = 0

            # Update current time
            current_time = chord_time + total_duration

    def _generate_broken_chords(self, track: MidiTrack,
                               chords: List[Tuple[int, str, List[int]]],
                               octave: int, velocity: int,
                               ticks_per_beat: int) -> None:
        """Generate broken chord voicing (notes played as short staccato sequence)."""
        current_time = 0

        for i, (chord_time, chord_name, notes) in enumerate(chords):
            # Calculate total duration
            if i + 1 < len(chords):
                next_chord_time = chords[i + 1][0]
                total_duration = next_chord_time - chord_time
            else:
                total_duration = ticks_per_beat * 4

            # Normalize notes
            normalized_notes = sorted(self._normalize_to_octave(notes, octave))

            # Short staccato notes (1/8 note each)
            note_duration = ticks_per_beat // 2
            note_gap = ticks_per_beat // 4

            # Time delta to start
            delta_time = chord_time - current_time

            # Play each note with gap
            for j, note in enumerate(normalized_notes):
                # Note on
                time = delta_time if j == 0 else note_gap
                track.append(Message('note_on', note=note, velocity=velocity, time=time))

                # Note off
                track.append(Message('note_off', note=note, velocity=0, time=note_duration))

                delta_time = 0

            # Update current time
            current_time = chord_time + total_duration

    def _normalize_to_octave(self, notes: List[int], target_octave: int) -> List[int]:
        """
        Normalize MIDI notes to specific octave while preserving intervals.

        Args:
            notes: List of MIDI note numbers
            target_octave: Target octave (4 = middle C octave)

        Returns:
            List of normalized MIDI note numbers
        """
        if not notes:
            return []

        # Get unique pitch classes
        pitch_classes = sorted(set(note % 12 for note in notes))

        # Calculate base MIDI note for target octave
        # Octave 4 starts at C4 (MIDI 60)
        # Octave 5 starts at C5 (MIDI 72), etc.
        base_midi = 12 * (target_octave + 1)  # C of target octave

        # Build chord notes in target octave
        normalized = []
        for pc in pitch_classes:
            midi_note = base_midi + pc
            # Ensure within piano range
            while midi_note < 21:  # A0
                midi_note += 12
            while midi_note > 108:  # C8
                midi_note -= 12
            normalized.append(midi_note)

        return sorted(normalized)

    def generate_text_chord_chart(self,
                                  chords: List[Tuple[int, str, List[int]]],
                                  output_path: str,
                                  ticks_per_beat: int) -> None:
        """
        Generate a text chord chart file.

        Args:
            chords: List of detected chords
            output_path: Path to save text file
            ticks_per_beat: MIDI ticks per beat
        """
        if not chords:
            return

        lines = []
        lines.append("CHORD CHART")
        lines.append("=" * 60)
        lines.append("")

        # Assuming 4/4 time
        beats_per_measure = 4

        current_measure = -1
        measure_chords = []

        for time_ticks, chord_name, notes in chords:
            beat = time_ticks / ticks_per_beat
            measure = int(beat / beats_per_measure) + 1

            if measure != current_measure:
                # Print previous measure if any
                if current_measure > 0 and measure_chords:
                    lines.append(f"Measure {current_measure:3d}: | {' | '.join(measure_chords)} |")

                current_measure = measure
                measure_chords = []

            measure_chords.append(chord_name)

        # Print last measure
        if measure_chords:
            lines.append(f"Measure {current_measure:3d}: | {' | '.join(measure_chords)} |")

        lines.append("")
        lines.append("=" * 60)
        lines.append(f"Total chords: {len(chords)}")

        # Write to file
        with open(output_path, 'w') as f:
            f.write('\n'.join(lines))

        print(f"  ✓ Generated chord chart: {output_path}")
