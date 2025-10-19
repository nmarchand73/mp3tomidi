"""
MIDI Error Correction Module

Filters and corrects common errors in transcribed MIDI files:
1. Duration filtering - removes very short notes
2. Velocity filtering - removes very quiet notes  
3. Pitch range filtering - removes extreme outliers
4. Key detection - identifies the musical key
5. Out-of-key note flagging - identifies suspicious notes
"""

import mido
import numpy as np
from collections import Counter
from typing import List, Dict, Tuple, Set


class MidiCorrector:
    """Corrects common errors in transcribed MIDI files."""
    
    # Piano range: A0 (21) to C8 (108)
    MIN_PIANO_NOTE = 21
    MAX_PIANO_NOTE = 108
    
    # Major and minor scale patterns (semitones from root)
    MAJOR_SCALE = [0, 2, 4, 5, 7, 9, 11]
    MINOR_SCALE = [0, 2, 3, 5, 7, 8, 10]
    
    # Note names for display
    NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    
    def __init__(self, 
                 min_note_duration_ms: float = 50.0,
                 min_velocity: int = 15,
                 min_note: int = MIN_PIANO_NOTE,
                 max_note: int = MAX_PIANO_NOTE):
        """
        Initialize the corrector.
        
        Args:
            min_note_duration_ms: Minimum note duration in milliseconds (default: 50ms)
            min_velocity: Minimum note velocity (default: 15)
            min_note: Minimum MIDI note number (default: 21 = A0)
            max_note: Maximum MIDI note number (default: 108 = C8)
        """
        self.min_note_duration_ms = min_note_duration_ms
        self.min_velocity = min_velocity
        self.min_note = min_note
        self.max_note = max_note
        
        self.stats = {
            'total_notes': 0,
            'removed_short': 0,
            'removed_quiet': 0,
            'removed_range': 0,
            'out_of_key': 0,
            'detected_key': None
        }
    
    def correct(self, midi_file: mido.MidiFile, verbose: bool = False) -> mido.MidiFile:
        """
        Apply corrections to a MIDI file.
        
        Args:
            midi_file: Input MIDI file
            verbose: Print detailed statistics
            
        Returns:
            Corrected MIDI file
        """
        # Reset statistics
        self.stats = {
            'total_notes': 0,
            'removed_short': 0,
            'removed_quiet': 0,
            'removed_range': 0,
            'out_of_key': 0,
            'detected_key': None
        }
        
        # Extract notes from all tracks
        all_notes = self._extract_notes(midi_file)
        self.stats['total_notes'] = len(all_notes)
        
        if len(all_notes) == 0:
            if verbose:
                print("Warning: No notes found in MIDI file")
            return midi_file
        
        # Detect musical key
        key_root, key_mode = self._detect_key(all_notes)
        self.stats['detected_key'] = f"{self.NOTE_NAMES[key_root]} {key_mode}"
        
        if verbose:
            print(f"\n  Detected key: {self.stats['detected_key']}")
        
        # Filter notes
        filtered_notes = self._filter_notes(all_notes, midi_file.ticks_per_beat)
        
        # Flag out-of-key notes
        out_of_key_notes = self._flag_out_of_key(filtered_notes, key_root, key_mode)
        self.stats['out_of_key'] = len(out_of_key_notes)
        
        # Create corrected MIDI file
        corrected_midi = self._create_corrected_midi(midi_file, filtered_notes)
        
        if verbose:
            self._print_statistics()
        
        return corrected_midi
    
    def _extract_notes(self, midi_file: mido.MidiFile) -> List[Dict]:
        """Extract all notes with timing information."""
        notes = []
        
        for track_idx, track in enumerate(midi_file.tracks):
            track_time = 0
            active_notes = {}  # note_number -> (start_time, velocity, channel)
            
            for msg in track:
                track_time += msg.time
                
                if msg.type == 'note_on' and msg.velocity > 0:
                    active_notes[msg.note] = (track_time, msg.velocity, 
                                              msg.channel if hasattr(msg, 'channel') else 0)
                    
                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    if msg.note in active_notes:
                        start_time, velocity, channel = active_notes[msg.note]
                        notes.append({
                            'note': msg.note,
                            'start_time': start_time,
                            'end_time': track_time,
                            'duration_ticks': track_time - start_time,
                            'velocity': velocity,
                            'channel': channel,
                            'track': track_idx
                        })
                        del active_notes[msg.note]
        
        return notes
    
    def _filter_notes(self, notes: List[Dict], ticks_per_beat: int) -> List[Dict]:
        """Filter out notes based on duration, velocity, and range."""
        filtered = []
        
        # Convert minimum duration from ms to ticks
        # Assuming 120 BPM (500ms per beat)
        ms_per_tick = 500.0 / ticks_per_beat
        min_duration_ticks = self.min_note_duration_ms / ms_per_tick
        
        for note in notes:
            # Check duration
            if note['duration_ticks'] < min_duration_ticks:
                self.stats['removed_short'] += 1
                continue
            
            # Check velocity
            if note['velocity'] < self.min_velocity:
                self.stats['removed_quiet'] += 1
                continue
            
            # Check pitch range
            if note['note'] < self.min_note or note['note'] > self.max_note:
                self.stats['removed_range'] += 1
                continue
            
            filtered.append(note)
        
        return filtered
    
    def _detect_key(self, notes: List[Dict]) -> Tuple[int, str]:
        """
        Detect the musical key using Krumhansl-Schmuckler algorithm.
        
        Returns:
            Tuple of (root_note, mode) where root_note is 0-11 (C-B) and mode is 'major' or 'minor'
        """
        # Count pitch class occurrences
        pitch_classes = [note['note'] % 12 for note in notes]
        pitch_counts = Counter(pitch_classes)
        
        # Create distribution vector
        distribution = [pitch_counts.get(i, 0) for i in range(12)]
        total = sum(distribution)
        
        if total == 0:
            return 0, 'major'  # Default to C major
        
        # Normalize
        distribution = [count / total for count in distribution]
        
        # Krumhansl-Kessler key profiles (simplified)
        major_profile = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
        minor_profile = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
        
        # Calculate correlation for each key
        best_correlation = -1
        best_key = (0, 'major')
        
        for root in range(12):
            # Test major key
            rotated_major = major_profile[root:] + major_profile[:root]
            correlation = self._correlation(distribution, rotated_major)
            if correlation > best_correlation:
                best_correlation = correlation
                best_key = (root, 'major')
            
            # Test minor key
            rotated_minor = minor_profile[root:] + minor_profile[:root]
            correlation = self._correlation(distribution, rotated_minor)
            if correlation > best_correlation:
                best_correlation = correlation
                best_key = (root, 'minor')
        
        return best_key
    
    def _correlation(self, x: List[float], y: List[float]) -> float:
        """Calculate Pearson correlation coefficient."""
        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x2 = sum(xi ** 2 for xi in x)
        sum_y2 = sum(yi ** 2 for yi in y)
        
        numerator = n * sum_xy - sum_x * sum_y
        denominator = ((n * sum_x2 - sum_x ** 2) * (n * sum_y2 - sum_y ** 2)) ** 0.5
        
        if denominator == 0:
            return 0
        
        return numerator / denominator
    
    def _flag_out_of_key(self, notes: List[Dict], key_root: int, key_mode: str) -> Set[int]:
        """
        Flag notes that are outside the detected key.
        
        Returns:
            Set of note indices that are out of key
        """
        scale = self.MAJOR_SCALE if key_mode == 'major' else self.MINOR_SCALE
        key_notes = {(key_root + interval) % 12 for interval in scale}
        
        out_of_key = set()
        for idx, note in enumerate(notes):
            pitch_class = note['note'] % 12
            if pitch_class not in key_notes:
                out_of_key.add(idx)
        
        return out_of_key
    
    def _create_corrected_midi(self, original_midi: mido.MidiFile, 
                               filtered_notes: List[Dict]) -> mido.MidiFile:
        """Create a new MIDI file with filtered notes."""
        # Group notes by track
        notes_by_track = {}
        for note in filtered_notes:
            track_idx = note['track']
            if track_idx not in notes_by_track:
                notes_by_track[track_idx] = []
            notes_by_track[track_idx].append(note)
        
        # Create new MIDI file
        corrected = mido.MidiFile(ticks_per_beat=original_midi.ticks_per_beat)
        
        # Process each track
        for track_idx, track in enumerate(original_midi.tracks):
            new_track = mido.MidiTrack()
            
            # Copy meta messages
            for msg in track:
                if msg.type in ['track_name', 'set_tempo', 'time_signature', 'key_signature']:
                    new_track.append(msg.copy(time=0))
            
            # Add filtered notes for this track
            if track_idx in notes_by_track:
                self._add_notes_to_track(new_track, notes_by_track[track_idx])
            
            # Add end of track
            new_track.append(mido.MetaMessage('end_of_track', time=0))
            corrected.tracks.append(new_track)
        
        return corrected
    
    def _add_notes_to_track(self, track: mido.MidiTrack, notes: List[Dict]):
        """Add notes to a track with proper timing."""
        if not notes:
            return
        
        # Create note events
        events = []
        for note in notes:
            events.append({
                'time': note['start_time'],
                'type': 'note_on',
                'note': note['note'],
                'velocity': note['velocity'],
                'channel': note['channel']
            })
            events.append({
                'time': note['end_time'],
                'type': 'note_off',
                'note': note['note'],
                'velocity': 0,
                'channel': note['channel']
            })
        
        # Sort by time
        events.sort(key=lambda x: (x['time'], x['type'] == 'note_off'))
        
        # Convert to delta times
        prev_time = 0
        for event in events:
            delta_time = event['time'] - prev_time
            
            if event['type'] == 'note_on':
                track.append(mido.Message('note_on',
                                        note=event['note'],
                                        velocity=event['velocity'],
                                        time=delta_time,
                                        channel=event['channel']))
            else:
                track.append(mido.Message('note_off',
                                        note=event['note'],
                                        velocity=0,
                                        time=delta_time,
                                        channel=event['channel']))
            
            prev_time = event['time']
    
    def _print_statistics(self):
        """Print correction statistics."""
        print("\n  Correction Statistics:")
        print(f"    Total notes: {self.stats['total_notes']}")
        print(f"    Removed (too short): {self.stats['removed_short']}")
        print(f"    Removed (too quiet): {self.stats['removed_quiet']}")
        print(f"    Removed (out of range): {self.stats['removed_range']}")
        
        total_removed = (self.stats['removed_short'] + 
                        self.stats['removed_quiet'] + 
                        self.stats['removed_range'])
        remaining = self.stats['total_notes'] - total_removed
        
        print(f"    Remaining notes: {remaining}")
        
        if self.stats['out_of_key'] > 0:
            percentage = (self.stats['out_of_key'] / remaining * 100) if remaining > 0 else 0
            print(f"    Out-of-key notes: {self.stats['out_of_key']} ({percentage:.1f}%)")
    
    def get_statistics(self) -> Dict:
        """Get correction statistics."""
        return self.stats.copy()

