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
                 min_note_duration_ms: float = 100.0,
                 min_velocity: int = 15,
                 min_note: int = MIN_PIANO_NOTE,
                 max_note: int = MAX_PIANO_NOTE,
                 quantize: bool = False,
                 quantize_resolution: int = 16,
                 merge_notes: bool = True,
                 merge_threshold_ms: float = 50.0):
        """
        Initialize the corrector.
        
        Args:
            min_note_duration_ms: Minimum note duration in milliseconds (default: 100ms)
            min_velocity: Minimum note velocity (default: 15)
            min_note: Minimum MIDI note number (default: 21 = A0)
            max_note: Maximum MIDI note number (default: 108 = C8)
            quantize: Apply rhythmic quantization (default: False)
            quantize_resolution: Quantization resolution in ticks (16 = 16th notes, default: 16)
            merge_notes: Merge consecutive notes of same pitch (default: True)
            merge_threshold_ms: Max gap between notes to merge in ms (default: 50ms)
        """
        self.min_note_duration_ms = min_note_duration_ms
        self.min_velocity = min_velocity
        self.min_note = min_note
        self.max_note = max_note
        self.quantize = quantize
        self.quantize_resolution = quantize_resolution
        self.merge_notes = merge_notes
        self.merge_threshold_ms = merge_threshold_ms
        
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
            'extended_notes': 0,
            'merged_notes': 0,
            'quantized_notes': 0,
            'out_of_key': 0,
            'detected_key': None,
            'detected_tempo': None
        }
        
        # Extract tempo from MIDI file
        tempo = self._extract_tempo(midi_file)
        self.stats['detected_tempo'] = round(60000000 / tempo) if tempo else 120
        
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
            print(f"  Detected tempo: {self.stats['detected_tempo']} BPM")
        
        # Filter and extend notes
        filtered_notes = self._filter_and_extend_notes(
            all_notes, 
            midi_file.ticks_per_beat, 
            tempo
        )
        
        # Merge consecutive notes of same pitch if requested
        if self.merge_notes:
            filtered_notes = self._merge_consecutive_notes(
                filtered_notes,
                midi_file.ticks_per_beat,
                tempo
            )
        
        # Apply quantization if requested
        if self.quantize:
            filtered_notes = self._quantize_notes(filtered_notes, midi_file.ticks_per_beat)
        
        # Flag out-of-key notes
        out_of_key_notes = self._flag_out_of_key(filtered_notes, key_root, key_mode)
        self.stats['out_of_key'] = len(out_of_key_notes)
        
        # Create corrected MIDI file
        corrected_midi = self._create_corrected_midi(midi_file, filtered_notes)
        
        if verbose:
            self._print_statistics()
        
        return corrected_midi
    
    def _extract_tempo(self, midi_file: mido.MidiFile) -> int:
        """
        Extract tempo from MIDI file.
        
        Returns:
            Tempo in microseconds per beat (default: 500000 = 120 BPM)
        """
        for track in midi_file.tracks:
            for msg in track:
                if msg.type == 'set_tempo':
                    return msg.tempo
        return 500000  # Default: 120 BPM
    
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
    
    def _filter_and_extend_notes(self, notes: List[Dict], ticks_per_beat: int, 
                                  tempo: int) -> List[Dict]:
        """
        Filter notes based on duration, velocity, range AND extend very short notes.
        
        Strategy:
        - Very short notes (<50ms): Remove (likely transcription errors)
        - Short notes (50-min_duration): Extend to minimum duration
        - Normal notes: Keep as is
        """
        filtered = []
        
        # Convert durations from ms to ticks using actual tempo
        ms_per_beat = tempo / 1000.0  # Convert microseconds to milliseconds
        ms_per_tick = ms_per_beat / ticks_per_beat
        
        min_duration_ticks = self.min_note_duration_ms / ms_per_tick
        # Very short threshold: notes shorter than 50ms are likely errors
        very_short_threshold_ticks = 50.0 / ms_per_tick
        
        # Sort notes by start time for better extension logic
        sorted_notes = sorted(notes, key=lambda n: n['start_time'])
        
        for i, note in enumerate(sorted_notes):
            # Check velocity first
            if note['velocity'] < self.min_velocity:
                self.stats['removed_quiet'] += 1
                continue
            
            # Check pitch range
            if note['note'] < self.min_note or note['note'] > self.max_note:
                self.stats['removed_range'] += 1
                continue
            
            # Handle duration
            if note['duration_ticks'] < very_short_threshold_ticks:
                # Remove very short notes (likely errors)
                self.stats['removed_short'] += 1
                continue
            elif note['duration_ticks'] < min_duration_ticks:
                # Extend short notes to minimum duration
                old_duration = note['duration_ticks']
                note['duration_ticks'] = min_duration_ticks
                note['end_time'] = note['start_time'] + min_duration_ticks
                self.stats['extended_notes'] += 1
            
            filtered.append(note)
        
        return filtered
    
    def _quantize_notes(self, notes: List[Dict], ticks_per_beat: int) -> List[Dict]:
        """
        Apply rhythmic quantization to notes.
        
        Quantizes start times to the nearest grid position based on quantize_resolution.
        Uses partial quantization (50%) to preserve some human feel.
        """
        quantized = []
        
        # Calculate quantization grid size
        # For 16th notes: ticks_per_beat / 4
        # For 8th notes: ticks_per_beat / 2
        grid_size = ticks_per_beat / (self.quantize_resolution / 4)
        
        for note in notes:
            # Quantize start time (50% quantization for natural feel)
            original_start = note['start_time']
            nearest_grid = round(original_start / grid_size) * grid_size
            quantized_start = original_start + 0.5 * (nearest_grid - original_start)
            
            # Update times
            duration = note['duration_ticks']
            note['start_time'] = int(quantized_start)
            note['end_time'] = int(quantized_start + duration)
            
            quantized.append(note)
            self.stats['quantized_notes'] += 1
        
        return quantized
    
    def _merge_consecutive_notes(self, notes: List[Dict], ticks_per_beat: int,
                                  tempo: int) -> List[Dict]:
        """
        Merge consecutive notes of the same pitch that are very close in time.
        This creates legato/tied notes instead of many short repeated notes.
        
        Args:
            notes: List of note dictionaries
            ticks_per_beat: MIDI ticks per beat
            tempo: Tempo in microseconds per beat
            
        Returns:
            List of notes with consecutive same-pitch notes merged
        """
        if not notes:
            return notes
        
        # Convert merge threshold from ms to ticks
        ms_per_beat = tempo / 1000.0
        ms_per_tick = ms_per_beat / ticks_per_beat
        merge_threshold_ticks = self.merge_threshold_ms / ms_per_tick
        
        # Sort notes by pitch, then by start time
        sorted_notes = sorted(notes, key=lambda n: (n['note'], n['start_time']))
        
        merged = []
        i = 0
        
        while i < len(sorted_notes):
            current_note = sorted_notes[i].copy()
            
            # Look ahead for consecutive notes of the same pitch
            j = i + 1
            while j < len(sorted_notes):
                next_note = sorted_notes[j]
                
                # Check if next note has same pitch
                if next_note['note'] != current_note['note']:
                    break
                
                # Check if notes are close enough to merge (gap < threshold)
                gap = next_note['start_time'] - current_note['end_time']
                
                if 0 <= gap <= merge_threshold_ticks:
                    # Merge: extend current note to cover next note
                    current_note['end_time'] = next_note['end_time']
                    current_note['duration_ticks'] = current_note['end_time'] - current_note['start_time']
                    # Use average velocity
                    current_note['velocity'] = int((current_note['velocity'] + next_note['velocity']) / 2)
                    self.stats['merged_notes'] += 1
                    j += 1
                else:
                    # Gap too large, stop merging
                    break
            
            merged.append(current_note)
            i = j if j > i + 1 else i + 1
        
        return merged
    
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
        print(f"    Removed (too short <50ms): {self.stats['removed_short']}")
        print(f"    Extended (50-{int(self.min_note_duration_ms)}ms): {self.stats['extended_notes']}")
        print(f"    Removed (too quiet): {self.stats['removed_quiet']}")
        print(f"    Removed (out of range): {self.stats['removed_range']}")
        
        if self.merge_notes and self.stats['merged_notes'] > 0:
            print(f"    Merged (legato): {self.stats['merged_notes']}")
        
        if self.quantize and self.stats['quantized_notes'] > 0:
            print(f"    Quantized: {self.stats['quantized_notes']}")
        
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

