"""
Motif Extraction Module

Identifies and extracts the most repeated melodic motif from MIDI files.
"""

import mido
from collections import Counter, defaultdict
from pathlib import Path
from typing import List, Tuple, Optional


class MotifExtractor:
    """Extracts the most repeated melodic motif from a MIDI file."""
    
    def __init__(self, min_motif_length: int = 3, max_motif_length: int = 12):
        """
        Initialize the motif extractor.
        
        Args:
            min_motif_length: Minimum number of notes in a motif
            max_motif_length: Maximum number of notes in a motif
        """
        self.min_motif_length = min_motif_length
        self.max_motif_length = max_motif_length
    
    def extract_note_sequence(self, midi_file: mido.MidiFile) -> List[Tuple[int, int, int]]:
        """
        Extract note sequence from MIDI file.
        
        Args:
            midi_file: Input MIDI file
            
        Returns:
            List of (note, velocity, duration_ticks) tuples
        """
        notes = []
        
        for track in midi_file.tracks:
            current_notes = {}  # note_number -> (start_time, velocity)
            absolute_time = 0
            
            for msg in track:
                absolute_time += msg.time
                
                if msg.type == 'note_on' and msg.velocity > 0:
                    current_notes[msg.note] = (absolute_time, msg.velocity)
                
                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    if msg.note in current_notes:
                        start_time, velocity = current_notes[msg.note]
                        duration = absolute_time - start_time
                        notes.append((msg.note, velocity, duration, start_time))
                        del current_notes[msg.note]
        
        # Sort by start time
        notes.sort(key=lambda x: x[3])
        
        # Return (note, velocity, duration) without start_time
        return [(n[0], n[1], n[2]) for n in notes]
    
    def find_melodic_patterns(self, note_sequence: List[Tuple[int, int, int]]) -> Counter:
        """
        Find all melodic patterns (sequences of note pitches) in the note sequence.
        
        Args:
            note_sequence: List of (note, velocity, duration) tuples
            
        Returns:
            Counter of pattern frequencies
        """
        patterns = Counter()
        
        # Extract just the pitch sequence for pattern matching
        pitches = [note[0] for note in note_sequence]
        
        # Find all patterns of varying lengths
        for length in range(self.min_motif_length, min(self.max_motif_length + 1, len(pitches))):
            for i in range(len(pitches) - length + 1):
                pattern = tuple(pitches[i:i + length])
                patterns[pattern] += 1
        
        return patterns
    
    def find_rhythmic_patterns(self, note_sequence: List[Tuple[int, int, int]]) -> Counter:
        """
        Find all rhythmic patterns (sequences of note durations) in the note sequence.
        
        Args:
            note_sequence: List of (note, velocity, duration) tuples
            
        Returns:
            Counter of rhythmic pattern frequencies
        """
        patterns = Counter()
        
        # Extract duration sequence, normalized to smallest duration
        durations = [note[2] for note in note_sequence]
        
        if not durations:
            return patterns
        
        # Normalize durations to ratios
        min_duration = min(d for d in durations if d > 0)
        if min_duration > 0:
            normalized_durations = [int(round(d / min_duration)) for d in durations]
        else:
            normalized_durations = durations
        
        # Find all rhythmic patterns
        for length in range(self.min_motif_length, min(self.max_motif_length + 1, len(normalized_durations))):
            for i in range(len(normalized_durations) - length + 1):
                pattern = tuple(normalized_durations[i:i + length])
                patterns[pattern] += 1
        
        return patterns
    
    def find_combined_patterns(self, note_sequence: List[Tuple[int, int, int]]) -> Counter:
        """
        Find combined melodic and rhythmic patterns.
        
        Args:
            note_sequence: List of (note, velocity, duration) tuples
            
        Returns:
            Counter of combined pattern frequencies
        """
        patterns = Counter()
        
        # Create combined patterns (pitch intervals + rhythm)
        for length in range(self.min_motif_length, min(self.max_motif_length + 1, len(note_sequence))):
            for i in range(len(note_sequence) - length + 1):
                segment = note_sequence[i:i + length]
                
                # Create pattern as (pitch_intervals, rhythm_pattern)
                pitches = [n[0] for n in segment]
                durations = [n[2] for n in segment]
                
                # Convert to intervals (relative pitch changes)
                intervals = tuple(pitches[j+1] - pitches[j] for j in range(len(pitches) - 1))
                
                # Normalize durations
                min_dur = min(d for d in durations if d > 0) if any(d > 0 for d in durations) else 1
                rhythm = tuple(int(round(d / min_dur)) for d in durations) if min_dur > 0 else tuple(durations)
                
                pattern = (intervals, rhythm, pitches[0])  # intervals, rhythm, starting pitch
                patterns[pattern] += 1
        
        return patterns
    
    def get_most_repeated_motif(self, midi_file: mido.MidiFile, 
                                 pattern_type: str = 'combined') -> Optional[Tuple]:
        """
        Get the most repeated motif from the MIDI file.
        
        Args:
            midi_file: Input MIDI file
            pattern_type: Type of pattern to find ('melodic', 'rhythmic', or 'combined')
            
        Returns:
            Tuple of (pattern, frequency, note_sequence) or None
        """
        note_sequence = self.extract_note_sequence(midi_file)
        
        if len(note_sequence) < self.min_motif_length:
            return None
        
        if pattern_type == 'melodic':
            patterns = self.find_melodic_patterns(note_sequence)
        elif pattern_type == 'rhythmic':
            patterns = self.find_rhythmic_patterns(note_sequence)
        else:  # combined
            patterns = self.find_combined_patterns(note_sequence)
        
        # Filter patterns that appear at least twice
        filtered_patterns = Counter({k: v for k, v in patterns.items() if v >= 2})
        
        if not filtered_patterns:
            return None
        
        # Get most common pattern
        most_common = filtered_patterns.most_common(1)[0]
        pattern, frequency = most_common
        
        # Find first occurrence in original sequence to get full note data
        if pattern_type == 'combined':
            intervals, rhythm, start_pitch = pattern
            motif_notes = self._reconstruct_motif_from_pattern(
                note_sequence, intervals, rhythm, start_pitch
            )
        else:
            motif_notes = self._find_motif_notes(note_sequence, pattern, pattern_type)
        
        return (pattern, frequency, motif_notes)
    
    def _reconstruct_motif_from_pattern(self, note_sequence: List[Tuple[int, int, int]],
                                        intervals: Tuple, rhythm: Tuple, 
                                        start_pitch: int) -> List[Tuple[int, int, int]]:
        """Reconstruct the motif notes from interval and rhythm pattern."""
        # Find first occurrence of this pattern
        for i in range(len(note_sequence) - len(intervals)):
            segment = note_sequence[i:i + len(intervals) + 1]
            pitches = [n[0] for n in segment]
            
            if pitches[0] == start_pitch:
                # Check if intervals match
                seg_intervals = tuple(pitches[j+1] - pitches[j] for j in range(len(pitches) - 1))
                if seg_intervals == intervals:
                    return segment
        
        # Fallback: reconstruct from pattern
        pitches = [start_pitch]
        for interval in intervals:
            pitches.append(pitches[-1] + interval)
        
        # Use rhythm to create note data
        notes = []
        for i, pitch in enumerate(pitches):
            velocity = 80  # Default velocity
            duration = rhythm[i] if i < len(rhythm) else rhythm[0]
            notes.append((pitch, velocity, duration * 100))  # Scale duration
        
        return notes
    
    def _find_motif_notes(self, note_sequence: List[Tuple[int, int, int]],
                          pattern: Tuple, pattern_type: str) -> List[Tuple[int, int, int]]:
        """Find the full note data for a pattern."""
        if pattern_type == 'melodic':
            # Pattern is a sequence of pitches
            for i in range(len(note_sequence) - len(pattern) + 1):
                pitches = tuple(n[0] for n in note_sequence[i:i + len(pattern)])
                if pitches == pattern:
                    return note_sequence[i:i + len(pattern)]
        
        return []
    
    def create_motif_midi(self, motif_notes: List[Tuple[int, int, int]], 
                         output_path: str, ticks_per_beat: int = 480):
        """
        Create a MIDI file containing only the motif.
        
        Args:
            motif_notes: List of (note, velocity, duration) tuples
            output_path: Path to save the MIDI file
            ticks_per_beat: MIDI ticks per beat
        """
        midi = mido.MidiFile(ticks_per_beat=ticks_per_beat)
        track = mido.MidiTrack()
        midi.tracks.append(track)
        
        # Add track name
        track.append(mido.MetaMessage('track_name', name='Motif', time=0))
        
        # Add tempo (120 BPM)
        track.append(mido.MetaMessage('set_tempo', tempo=500000, time=0))
        
        # Add notes
        time = 0
        for note, velocity, duration in motif_notes:
            # Note on
            track.append(mido.Message('note_on', note=note, velocity=velocity, time=time))
            # Note off
            track.append(mido.Message('note_off', note=note, velocity=0, time=duration))
            time = 0  # Time delta for next note
        
        # End of track
        track.append(mido.MetaMessage('end_of_track', time=0))
        
        midi.save(output_path)
    
    def extract(self, midi_file: mido.MidiFile, output_path: str, 
                verbose: bool = False) -> Optional[dict]:
        """
        Extract and save the most repeated motif.
        
        Args:
            midi_file: Input MIDI file
            output_path: Path to save the motif MIDI file
            verbose: Print detailed information
            
        Returns:
            Dictionary with motif info or None
        """
        result = self.get_most_repeated_motif(midi_file, pattern_type='combined')
        
        if result is None:
            if verbose:
                print("  No repeated motif found")
            return None
        
        pattern, frequency, motif_notes = result
        
        if verbose:
            intervals, rhythm, start_pitch = pattern
            print(f"\n  Most repeated motif:")
            print(f"    - Frequency: {frequency} times")
            print(f"    - Length: {len(motif_notes)} notes")
            print(f"    - Starting pitch: {start_pitch} (MIDI)")
            print(f"    - Pitch intervals: {intervals}")
            print(f"    - Rhythm pattern: {rhythm}")
            
            # Show note pitches
            pitches = [n[0] for n in motif_notes]
            pitch_names = [self._midi_to_note_name(p) for p in pitches]
            print(f"    - Notes: {' '.join(pitch_names)}")
        
        # Create MIDI file with motif
        self.create_motif_midi(motif_notes, output_path, midi_file.ticks_per_beat)
        
        if verbose:
            print(f"    - Saved to: {output_path}")
        
        return {
            'pattern': pattern,
            'frequency': frequency,
            'length': len(motif_notes),
            'notes': motif_notes
        }
    
    def _midi_to_note_name(self, midi_note: int) -> str:
        """Convert MIDI note number to note name."""
        notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        octave = (midi_note // 12) - 1
        note = notes[midi_note % 12]
        return f"{note}{octave}"

