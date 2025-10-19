"""
Hand Separation Module for Piano MIDI Files

Implements a rule-based algorithm to separate piano notes into left and right hand tracks.
Uses pitch analysis, note clustering, and voice leading principles.
"""

import mido
import numpy as np
from collections import defaultdict
from typing import List, Tuple, Dict


class HandSeparator:
    """Separates piano MIDI notes into left and right hand tracks."""
    
    def __init__(self, split_note: int = 60, hysteresis: int = 5):
        """
        Initialize the hand separator.
        
        Args:
            split_note: MIDI note number to use as the split point (default: 60 = middle C)
            hysteresis: Number of semitones for hysteresis to prevent rapid switching
        """
        self.split_note = split_note
        self.hysteresis = hysteresis
        
    def separate(self, midi_file: mido.MidiFile) -> mido.MidiFile:
        """
        Separate a single-track MIDI file into left and right hand tracks.
        
        Args:
            midi_file: Input MIDI file with piano notes
            
        Returns:
            New MIDI file with two tracks (0: right hand, 1: left hand)
        """
        # Extract all note events with timing
        notes = self._extract_notes(midi_file)
        
        if not notes:
            print("Warning: No notes found in MIDI file")
            return self._create_empty_midi(midi_file)
        
        # Analyze pitch distribution and adjust split point if needed
        adjusted_split = self._analyze_pitch_distribution(notes)
        
        # Assign each note to left or right hand
        hand_assignments = self._assign_hands(notes, adjusted_split)
        
        # Create new MIDI file with two tracks
        output_midi = self._create_separated_midi(midi_file, notes, hand_assignments)
        
        return output_midi
    
    def _extract_notes(self, midi_file: mido.MidiFile) -> List[Dict]:
        """Extract all note_on/note_off events with absolute timing."""
        notes = []
        absolute_time = 0
        
        for track in midi_file.tracks:
            track_time = 0
            active_notes = {}  # note_number -> (start_time, velocity)
            
            for msg in track:
                track_time += msg.time
                
                if msg.type == 'note_on' and msg.velocity > 0:
                    active_notes[msg.note] = (track_time, msg.velocity)
                    
                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    if msg.note in active_notes:
                        start_time, velocity = active_notes[msg.note]
                        notes.append({
                            'note': msg.note,
                            'start_time': start_time,
                            'end_time': track_time,
                            'duration': track_time - start_time,
                            'velocity': velocity,
                            'channel': msg.channel if hasattr(msg, 'channel') else 0
                        })
                        del active_notes[msg.note]
        
        # Sort notes by start time
        notes.sort(key=lambda x: x['start_time'])
        return notes
    
    def _analyze_pitch_distribution(self, notes: List[Dict]) -> int:
        """
        Analyze the pitch distribution to find an optimal split point.
        
        Returns the adjusted split note (or original if distribution is reasonable).
        """
        pitches = [note['note'] for note in notes]
        
        if not pitches:
            return self.split_note
        
        # Calculate statistics
        mean_pitch = np.mean(pitches)
        median_pitch = np.median(pitches)
        
        # If the distribution is very skewed from our default split, adjust it
        # Use median as it's more robust to outliers
        adjusted_split = int(median_pitch)
        
        # But don't deviate too far from middle C (usually a good split point)
        # Keep it within an octave of middle C
        if adjusted_split < 48:  # C3
            adjusted_split = 48
        elif adjusted_split > 72:  # C5
            adjusted_split = 72
            
        return adjusted_split
    
    def _assign_hands(self, notes: List[Dict], split_note: int) -> List[str]:
        """
        Assign each note to 'left' or 'right' hand.
        
        Uses pitch-based assignment with hysteresis and voice leading principles.
        """
        assignments = []
        
        # Track recent assignments for each time window
        recent_left = []
        recent_right = []
        
        for i, note in enumerate(notes):
            pitch = note['note']
            start_time = note['start_time']
            
            # Clear old notes from recent tracking (older than 500 ticks)
            recent_left = [n for n in recent_left if start_time - n['start_time'] < 500]
            recent_right = [n for n in recent_right if start_time - n['start_time'] < 500]
            
            # Basic pitch-based assignment with hysteresis
            if pitch < split_note - self.hysteresis:
                hand = 'left'
            elif pitch > split_note + self.hysteresis:
                hand = 'right'
            else:
                # In the ambiguous zone - use context
                # Check which hand played notes more recently
                if recent_left and recent_right:
                    left_recency = start_time - recent_left[-1]['start_time']
                    right_recency = start_time - recent_right[-1]['start_time']
                    
                    # Also consider pitch proximity
                    left_pitch_dist = abs(pitch - recent_left[-1]['note'])
                    right_pitch_dist = abs(pitch - recent_right[-1]['note'])
                    
                    # Combined score (lower is better)
                    left_score = left_recency + left_pitch_dist * 10
                    right_score = right_recency + right_pitch_dist * 10
                    
                    hand = 'left' if left_score < right_score else 'right'
                elif recent_left:
                    hand = 'left'
                elif recent_right:
                    hand = 'right'
                else:
                    # Default to pitch-based
                    hand = 'left' if pitch < split_note else 'right'
            
            assignments.append(hand)
            
            # Track this note
            if hand == 'left':
                recent_left.append(note)
            else:
                recent_right.append(note)
        
        return assignments
    
    def _create_separated_midi(self, original_midi: mido.MidiFile, 
                               notes: List[Dict], 
                               hand_assignments: List[str]) -> mido.MidiFile:
        """Create a new MIDI file with separated tracks."""
        # Create new MIDI file
        output = mido.MidiFile(ticks_per_beat=original_midi.ticks_per_beat)
        
        # Create two tracks
        right_hand_track = mido.MidiTrack()
        left_hand_track = mido.MidiTrack()
        
        # Add track names
        right_hand_track.append(mido.MetaMessage('track_name', name='Right Hand', time=0))
        left_hand_track.append(mido.MetaMessage('track_name', name='Left Hand', time=0))
        
        # Copy tempo and other meta messages from original
        for track in original_midi.tracks:
            for msg in track:
                if msg.type in ['set_tempo', 'time_signature', 'key_signature']:
                    right_hand_track.append(msg.copy(time=0))
                    left_hand_track.append(msg.copy(time=0))
                    break
        
        # Separate notes into tracks
        right_notes = [(notes[i], i) for i, hand in enumerate(hand_assignments) if hand == 'right']
        left_notes = [(notes[i], i) for i, hand in enumerate(hand_assignments) if hand == 'left']
        
        # Add notes to respective tracks
        self._add_notes_to_track(right_hand_track, right_notes)
        self._add_notes_to_track(left_hand_track, left_notes)
        
        # Add end of track messages
        right_hand_track.append(mido.MetaMessage('end_of_track', time=0))
        left_hand_track.append(mido.MetaMessage('end_of_track', time=0))
        
        # Add tracks to output
        output.tracks.append(right_hand_track)
        output.tracks.append(left_hand_track)
        
        return output
    
    def _add_notes_to_track(self, track: mido.MidiTrack, notes: List[Tuple[Dict, int]]):
        """Add notes to a track with proper timing."""
        if not notes:
            return
        
        # Create note events (both note_on and note_off)
        events = []
        for note, idx in notes:
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
        
        # Convert to delta times and add to track
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
    
    def _create_empty_midi(self, original_midi: mido.MidiFile) -> mido.MidiFile:
        """Create an empty MIDI file with two tracks."""
        output = mido.MidiFile(ticks_per_beat=original_midi.ticks_per_beat)
        
        right_track = mido.MidiTrack()
        left_track = mido.MidiTrack()
        
        right_track.append(mido.MetaMessage('track_name', name='Right Hand', time=0))
        right_track.append(mido.MetaMessage('end_of_track', time=0))
        
        left_track.append(mido.MetaMessage('track_name', name='Left Hand', time=0))
        left_track.append(mido.MetaMessage('end_of_track', time=0))
        
        output.tracks.append(right_track)
        output.tracks.append(left_track)
        
        return output

