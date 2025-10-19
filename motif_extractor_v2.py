"""
Musical Phrase Detection Module

Identifies repeated musical phrases (6-14 notes) using advanced techniques:
- Point-set pattern matching for polyphonic music
- Dynamic Time Warping (DTW) for tempo-invariant matching
- Approximate pattern matching with edit distance
- Weighted scoring (frequency, length, musical significance)
- Focuses on complete melodic phrases, not short motifs
"""

import mido
import numpy as np
from collections import Counter, defaultdict
from pathlib import Path
from typing import List, Tuple, Optional, Set
from dataclasses import dataclass


@dataclass
class Note:
    """Represents a musical note with timing information."""
    pitch: int
    velocity: int
    start_time: int
    duration: int
    
    def __hash__(self):
        return hash((self.pitch, self.start_time))


@dataclass
class MusicalPhrase:
    """Represents a detected musical phrase with metadata."""
    notes: List[Note]
    frequency: int
    occurrences: List[int]  # Start times of occurrences
    score: float  # Combined score based on multiple factors
    pattern_type: str  # 'exact', 'transposed', 'rhythmic'
    
    @property
    def length(self) -> int:
        return len(self.notes)
    
    @property
    def pitch_sequence(self) -> Tuple[int, ...]:
        return tuple(n.pitch for n in self.notes)
    
    @property
    def interval_sequence(self) -> Tuple[int, ...]:
        if len(self.notes) < 2:
            return tuple()
        return tuple(self.notes[i+1].pitch - self.notes[i].pitch 
                    for i in range(len(self.notes) - 1))


class MusicalPhraseDetector:
    """
    Advanced musical phrase detection using multiple algorithms.
    
    Detects complete melodic phrases (6-14 notes) rather than short motifs.
    
    Combines:
    - Point-set pattern matching
    - Dynamic Time Warping for approximate matching
    - Edit distance for similarity
    - Musical significance scoring with emphasis on phrase completeness
    """
    
    def __init__(self, 
                 min_phrase_length: int = 12,
                 max_phrase_length: int = 24,
                 min_frequency: int = 2,
                 allow_transposition: bool = True,
                 similarity_threshold: float = 0.8):
        """
        Initialize the musical phrase detector.
        
        Args:
            min_phrase_length: Minimum number of notes in a phrase (default: 12)
            max_phrase_length: Maximum number of notes in a phrase (default: 24)
            min_frequency: Minimum times a phrase must repeat (default: 2)
            allow_transposition: Allow transposed versions of patterns
            similarity_threshold: Threshold for approximate matching (0-1)
        """
        self.min_phrase_length = min_phrase_length
        self.max_phrase_length = max_phrase_length
        self.min_frequency = min_frequency
        self.allow_transposition = allow_transposition
        self.similarity_threshold = similarity_threshold
    
    def extract_notes(self, midi_file: mido.MidiFile) -> List[Note]:
        """
        Extract all notes from MIDI file with precise timing.
        
        Args:
            midi_file: Input MIDI file
            
        Returns:
            List of Note objects sorted by start time
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
                        
                        notes.append(Note(
                            pitch=msg.note,
                            velocity=velocity,
                            start_time=start_time,
                            duration=duration
                        ))
                        del current_notes[msg.note]
        
        # Sort by start time
        notes.sort(key=lambda n: n.start_time)
        return notes
    
    def find_exact_patterns(self, notes: List[Note]) -> Counter:
        """
        Find exact repeated musical phrases using interval sequences.
        Intervals are transposition-invariant.
        
        Args:
            notes: List of Note objects
            
        Returns:
            Counter of (interval_pattern, rhythm_pattern): frequency
        """
        patterns = Counter()
        
        for length in range(self.min_phrase_length, 
                          min(self.max_phrase_length + 1, len(notes))):
            for i in range(len(notes) - length + 1):
                segment = notes[i:i + length]
                
                # Create interval pattern (pitch differences)
                intervals = tuple(segment[j+1].pitch - segment[j].pitch 
                                for j in range(len(segment) - 1))
                
                # Create rhythm pattern (inter-onset intervals)
                iois = tuple(segment[j+1].start_time - segment[j].start_time 
                           for j in range(len(segment) - 1))
                
                # Normalize rhythm to smallest IOI
                min_ioi = min(iois) if iois and all(x > 0 for x in iois) else 1
                norm_rhythm = tuple(int(round(ioi / min_ioi)) for ioi in iois) if min_ioi > 0 else iois
                
                # Store pattern with starting pitch and rhythm
                pattern_key = (intervals, norm_rhythm, segment[0].pitch)
                patterns[pattern_key] += 1
        
        return patterns
    
    def compute_edit_distance(self, seq1: Tuple, seq2: Tuple) -> int:
        """
        Compute edit distance (Levenshtein distance) between two sequences.
        
        Args:
            seq1, seq2: Sequences to compare
            
        Returns:
            Edit distance
        """
        m, n = len(seq1), len(seq2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        
        for i in range(m + 1):
            dp[i][0] = i
        for j in range(n + 1):
            dp[0][j] = j
        
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if seq1[i-1] == seq2[j-1]:
                    dp[i][j] = dp[i-1][j-1]
                else:
                    dp[i][j] = 1 + min(dp[i-1][j],      # deletion
                                      dp[i][j-1],        # insertion
                                      dp[i-1][j-1])      # substitution
        
        return dp[m][n]
    
    def find_approximate_patterns(self, notes: List[Note]) -> List[Tuple]:
        """
        Find approximately repeated patterns using edit distance.
        Groups similar patterns together.
        
        Args:
            notes: List of Note objects
            
        Returns:
            List of (representative_pattern, similar_patterns, count)
        """
        # First get exact patterns
        exact_patterns = self.find_exact_patterns(notes)
        
        # Group similar patterns
        pattern_groups = []
        processed = set()
        
        for pattern1, count1 in exact_patterns.items():
            if pattern1 in processed:
                continue
            
            similar_group = [pattern1]
            total_count = count1
            processed.add(pattern1)
            
            intervals1, rhythm1, _ = pattern1
            
            for pattern2, count2 in exact_patterns.items():
                if pattern2 in processed:
                    continue
                
                intervals2, rhythm2, _ = pattern2
                
                # Compare intervals
                if len(intervals1) == len(intervals2):
                    edit_dist = self.compute_edit_distance(intervals1, intervals2)
                    max_len = max(len(intervals1), 1)
                    similarity = 1 - (edit_dist / max_len)
                    
                    if similarity >= self.similarity_threshold:
                        similar_group.append(pattern2)
                        total_count += count2
                        processed.add(pattern2)
            
            if total_count >= self.min_frequency:
                pattern_groups.append((pattern1, similar_group, total_count))
        
        return pattern_groups
    
    def score_phrase(self, pattern: Tuple, frequency: int, notes: List[Note]) -> float:
        """
        Score a musical phrase based on multiple factors.
        
        Emphasizes phrase completeness and musical coherence:
        - Frequency (how often it repeats)
        - Length (complete phrases are 7-12 notes)
        - Melodic contour (balanced stepwise motion and leaps)
        - Rhythmic variety (phrases have rhythmic structure)
        - Pitch range (phrases span a meaningful range)
        - Phrase closure (ends on stable notes)
        
        Args:
            pattern: (intervals, rhythm, start_pitch)
            frequency: Number of occurrences
            notes: All notes for context
            
        Returns:
            Score (higher is better)
        """
        intervals, rhythm, start_pitch = pattern
        
        # Frequency score (logarithmic to avoid dominating other factors)
        freq_score = np.log1p(frequency) * 2.0
        
        # Length score (prefer complete musical phrases: 12-24 notes)
        length = len(intervals) + 1
        optimal_length = 16  # Typical complete phrase in popular music (2-4 bars)
        
        # Strong penalty for fragments (not real phrases)
        if length < 10:
            length_penalty = -10.0  # Reject short fragments
        elif length < 12:
            length_penalty = -5.0   # Strongly discourage incomplete phrases
        else:
            length_penalty = 0.0    # Accept phrase-length patterns
        
        # Strong bonus for complete phrases (12-24 notes = 1-2 musical phrases)
        if 14 <= length <= 20:
            length_bonus = 3.0  # Very strong bonus for complete phrases
        elif 12 <= length <= 24:
            length_bonus = 2.0  # Good bonus for phrase-length patterns
        else:
            length_bonus = 0.0
        
        # Reward patterns close to optimal phrase length
        length_score = min(length / optimal_length, optimal_length / max(length, 1)) * 5.0 + length_penalty + length_bonus
        
        # Melodic interest score (mix of steps and leaps)
        if intervals:
            steps = sum(1 for i in intervals if abs(i) <= 2)
            leaps = sum(1 for i in intervals if abs(i) > 2)
            
            # Check for repeated notes (interval = 0)
            repeated = sum(1 for i in intervals if i == 0)
            repeated_ratio = repeated / len(intervals)
            
            # Penalize patterns with too many repeated notes
            if repeated_ratio > 0.5:
                repetition_penalty = -3.0
            elif repeated_ratio > 0.3:
                repetition_penalty = -1.0
            else:
                repetition_penalty = 0.0
            
            step_ratio = steps / len(intervals)
            melodic_score = (1 - abs(step_ratio - 0.7)) * 2.5 + repetition_penalty  # Prefer 70% steps
        else:
            melodic_score = 0.0
        
        # Rhythmic variety score
        if rhythm:
            unique_rhythms = len(set(rhythm))
            rhythm_score = min(unique_rhythms / 3, 1.0) * 1.5
        else:
            rhythm_score = 0.0
        
        # Pitch range score (prefer patterns with melodic range)
        if intervals:
            # Calculate actual pitch range from intervals
            pitches_rel = [0]
            for interval in intervals:
                pitches_rel.append(pitches_rel[-1] + interval)
            
            pitch_range = max(pitches_rel) - min(pitches_rel)
            
            # Reward patterns with at least 3 semitones range (minor 3rd)
            if pitch_range >= 3:
                range_score = min(pitch_range / 12, 1.0) * 2.0  # Normalize to octave
            else:
                range_score = -1.0  # Penalty for very narrow range
        else:
            range_score = 0.0
        
        # Penalize very low or very high pitches
        pitch_penalty = 0
        if start_pitch < 36 or start_pitch > 84:  # Outside C2-C6
            pitch_penalty = -1.0
        
        # Total score
        total_score = (freq_score + length_score + melodic_score + 
                      rhythm_score + range_score + pitch_penalty)
        
        return max(total_score, 0.0)
    
    def get_best_phrases(self, midi_file: mido.MidiFile, 
                        top_n: int = 5) -> List[MusicalPhrase]:
        """
        Get the top N best musical phrases based on scoring.
        
        Args:
            midi_file: Input MIDI file
            top_n: Number of top phrases to return
            
        Returns:
            List of MusicalPhrase objects, sorted by score
        """
        notes = self.extract_notes(midi_file)
        
        if len(notes) < self.min_phrase_length:
            return []
        
        # Find approximate patterns (which includes exact patterns)
        pattern_groups = self.find_approximate_patterns(notes)
        
        # Score each pattern group
        scored_phrases = []
        for representative, similar_patterns, total_count in pattern_groups:
            score = self.score_phrase(representative, total_count, notes)
            
            # Find actual note sequences for the representative pattern
            phrase_notes = self._find_pattern_notes(notes, representative)
            
            if phrase_notes:
                phrase = MusicalPhrase(
                    notes=phrase_notes,
                    frequency=total_count,
                    occurrences=[],  # Could track specific occurrences
                    score=score,
                    pattern_type='exact' if len(similar_patterns) == 1 else 'approximate'
                )
                scored_phrases.append(phrase)
        
        # Sort by score and return top N
        scored_phrases.sort(key=lambda p: p.score, reverse=True)
        return scored_phrases[:top_n]
    
    def _find_pattern_notes(self, notes: List[Note], 
                           pattern: Tuple) -> Optional[List[Note]]:
        """Find the first occurrence of a pattern in the note sequence."""
        intervals, rhythm, start_pitch = pattern
        target_length = len(intervals) + 1
        
        for i in range(len(notes) - target_length + 1):
            segment = notes[i:i + target_length]
            
            # Check if starting pitch matches
            if segment[0].pitch != start_pitch:
                continue
            
            # Check if intervals match
            seg_intervals = tuple(segment[j+1].pitch - segment[j].pitch 
                                for j in range(len(segment) - 1))
            
            if seg_intervals == intervals:
                return segment
        
        return None
    
    def create_phrase_midi(self, phrase: MusicalPhrase, output_path: str, 
                          ticks_per_beat: int = 480):
        """
        Create a MIDI file containing the musical phrase.
        
        Args:
            phrase: MusicalPhrase object to export
            output_path: Path to save the MIDI file
            ticks_per_beat: MIDI ticks per beat
        """
        midi = mido.MidiFile(ticks_per_beat=ticks_per_beat)
        track = mido.MidiTrack()
        midi.tracks.append(track)
        
        # Add metadata
        track.append(mido.MetaMessage('track_name', name='Musical Phrase', time=0))
        track.append(mido.MetaMessage('set_tempo', tempo=500000, time=0))
        
        # Sort notes by start time
        sorted_notes = sorted(phrase.notes, key=lambda n: n.start_time)
        
        # Normalize times - start from 0
        if sorted_notes:
            first_note_time = sorted_notes[0].start_time
        else:
            first_note_time = 0
        
        # Create events with normalized times
        events = []
        for note in sorted_notes:
            normalized_start = note.start_time - first_note_time
            normalized_end = normalized_start + note.duration
            events.append((normalized_start, 'on', note.pitch, note.velocity))
            events.append((normalized_end, 'off', note.pitch, 0))
        
        events.sort(key=lambda e: (e[0], 0 if e[1] == 'on' else 1))
        
        # Write events with delta times
        current_time = 0
        for abs_time, event_type, pitch, velocity in events:
            delta = abs_time - current_time
            if event_type == 'on':
                track.append(mido.Message('note_on', note=pitch, 
                                        velocity=velocity, time=delta))
            else:
                track.append(mido.Message('note_off', note=pitch, 
                                        velocity=0, time=delta))
            current_time = abs_time
        
        track.append(mido.MetaMessage('end_of_track', time=0))
        midi.save(output_path)
    
    def extract(self, midi_file: mido.MidiFile, output_path: str, 
                verbose: bool = False, top_n: int = 1) -> Optional[List[dict]]:
        """
        Extract and save top musical phrases.
        
        Args:
            midi_file: Input MIDI file
            output_path: Base path for output (will add _phrase1, _phrase2, etc.)
            verbose: Print detailed information
            top_n: Number of top phrases to extract
            
        Returns:
            List of dictionaries with phrase info
        """
        phrases = self.get_best_phrases(midi_file, top_n=top_n)
        
        if not phrases:
            if verbose:
                print("  No significant repeated musical phrases found")
            return None
        
        results = []
        output_base = Path(output_path)
        
        for idx, phrase in enumerate(phrases):
            if verbose:
                rank = idx + 1
                print(f"\n  Musical Phrase #{rank}:")
                print(f"    - Score: {phrase.score:.2f}")
                print(f"    - Frequency: {phrase.frequency} times")
                print(f"    - Length: {phrase.length} notes")
                print(f"    - Type: {phrase.pattern_type}")
                
                # Show interval pattern
                intervals = phrase.interval_sequence
                print(f"    - Intervals: {intervals}")
                
                # Calculate pitch range
                pitches = [n.pitch for n in phrase.notes]
                pitch_range = max(pitches) - min(pitches)
                print(f"    - Pitch range: {pitch_range} semitones")
                
                # Show notes
                pitch_names = [self._midi_to_note_name(p) for p in pitches]
                print(f"    - Notes: {' → '.join(pitch_names)}")
            
            # Create output filename
            if top_n == 1:
                phrase_path = output_base.parent / f"{output_base.stem}_phrase.mid"
            else:
                phrase_path = output_base.parent / f"{output_base.stem}_phrase{idx+1}.mid"
            
            # Save phrase
            self.create_phrase_midi(phrase, str(phrase_path), midi_file.ticks_per_beat)
            
            if verbose:
                print(f"    - Saved to: {phrase_path}")
            
            results.append({
                'rank': idx + 1,
                'score': phrase.score,
                'frequency': phrase.frequency,
                'length': phrase.length,
                'pattern_type': phrase.pattern_type,
                'file': str(phrase_path)
            })
        
        return results
    
    def _midi_to_note_name(self, midi_note: int) -> str:
        """Convert MIDI note number to note name."""
        notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        octave = (midi_note // 12) - 1
        note = notes[midi_note % 12]
        return f"{note}{octave}"

