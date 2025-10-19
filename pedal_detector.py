"""
Pedal Detection Module

Estimates sustain pedal usage from MIDI note patterns and audio analysis.
Inspired by GiantMIDI-Piano's pedal detection approach.

Method:
- Analyzes note overlap patterns (many sustained notes = likely pedal)
- Detects harmonic resonance in audio
- Adds CC64 (sustain pedal) messages to MIDI
"""

import numpy as np
import librosa
import mido
from typing import List, Tuple, Dict
from collections import defaultdict


class PedalDetector:
    """
    Detects sustain pedal usage from note patterns and audio characteristics.
    """
    
    def __init__(self, 
                 overlap_threshold: int = 4,
                 min_pedal_duration: float = 0.5,
                 resonance_threshold: float = 0.3):
        """
        Initialize pedal detector.
        
        Args:
            overlap_threshold: Minimum simultaneous notes to suggest pedal (default: 4)
            min_pedal_duration: Minimum pedal duration in seconds (default: 0.5)
            resonance_threshold: Threshold for harmonic resonance detection (default: 0.3)
        """
        self.overlap_threshold = overlap_threshold
        self.min_pedal_duration = min_pedal_duration
        self.resonance_threshold = resonance_threshold
    
    def detect_pedal(self, midi_file: mido.MidiFile, audio_path: str = None,
                    verbose: bool = False) -> List[Tuple[float, bool]]:
        """
        Detect pedal events from MIDI note patterns and optional audio.
        
        Args:
            midi_file: MIDI file to analyze
            audio_path: Optional audio file for resonance analysis
            verbose: Print detection details
            
        Returns:
            List of (time_seconds, pedal_down) tuples
        """
        if verbose:
            print("    Analyzing note overlap patterns...")
        
        # Extract note events with timing
        notes = self._extract_note_events(midi_file)
        
        if len(notes) == 0:
            return []
        
        # Analyze polyphony (simultaneous notes) over time
        pedal_events = self._detect_from_polyphony(notes, verbose)
        
        # Optional: refine with audio resonance analysis
        if audio_path:
            pedal_events = self._refine_with_audio(
                pedal_events, audio_path, verbose
            )
        
        # Filter short pedal events
        pedal_events = self._filter_short_events(pedal_events)
        
        if verbose:
            pedal_downs = sum(1 for _, down in pedal_events if down)
            print(f"    Detected {pedal_downs} pedal down/up cycles")
        
        return pedal_events
    
    def add_pedal_to_midi(self, midi_file: mido.MidiFile,
                         pedal_events: List[Tuple[float, bool]]) -> mido.MidiFile:
        """
        Add sustain pedal (CC64) messages to MIDI file.
        
        Args:
            midi_file: Original MIDI file
            pedal_events: List of (time_seconds, pedal_down) tuples
            
        Returns:
            Enhanced MIDI file with pedal messages
        """
        if len(pedal_events) == 0:
            return midi_file
        
        # Create new MIDI with pedal messages
        new_midi = mido.MidiFile(ticks_per_beat=midi_file.ticks_per_beat)
        
        for track in midi_file.tracks:
            new_track = mido.MidiTrack()
            
            # Convert pedal events to tick times
            tempo = 500000  # Default tempo
            pedal_ticks = []
            for time_sec, pedal_down in pedal_events:
                tick_time = mido.second2tick(
                    time_sec, midi_file.ticks_per_beat, tempo
                )
                pedal_ticks.append((tick_time, pedal_down))
            
            # Merge pedal events with existing track
            pedal_idx = 0
            current_time = 0
            
            for msg in track:
                current_time += msg.time
                
                # Update tempo if found
                if msg.type == 'set_tempo':
                    tempo = msg.tempo
                
                # Insert pedal events before this message if needed
                while pedal_idx < len(pedal_ticks):
                    pedal_tick, pedal_down = pedal_ticks[pedal_idx]
                    
                    if pedal_tick <= current_time:
                        # Calculate delta time for pedal message
                        delta = pedal_tick - (current_time - msg.time)
                        
                        # Add pedal CC64 message (127=down, 0=up)
                        new_track.append(mido.Message(
                            'control_change',
                            control=64,  # Sustain pedal
                            value=127 if pedal_down else 0,
                            time=max(0, delta),
                            channel=0
                        ))
                        
                        pedal_idx += 1
                    else:
                        break
                
                # Add original message
                new_track.append(msg.copy())
            
            # Add remaining pedal events
            while pedal_idx < len(pedal_ticks):
                pedal_tick, pedal_down = pedal_ticks[pedal_idx]
                delta = pedal_tick - current_time
                
                new_track.append(mido.Message(
                    'control_change',
                    control=64,
                    value=127 if pedal_down else 0,
                    time=max(0, delta),
                    channel=0
                ))
                
                current_time = pedal_tick
                pedal_idx += 1
            
            new_midi.tracks.append(new_track)
        
        return new_midi
    
    def _extract_note_events(self, midi_file: mido.MidiFile) -> List[Dict]:
        """Extract all note events with timing."""
        notes = []
        
        for track in midi_file.tracks:
            time = 0
            tempo = 500000
            active_notes = {}
            
            for msg in track:
                time += msg.time
                
                if msg.type == 'set_tempo':
                    tempo = msg.tempo
                
                time_sec = mido.tick2second(time, midi_file.ticks_per_beat, tempo)
                
                if msg.type == 'note_on' and msg.velocity > 0:
                    active_notes[msg.note] = time_sec
                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    if msg.note in active_notes:
                        start_sec = active_notes[msg.note]
                        notes.append({
                            'pitch': msg.note,
                            'start': start_sec,
                            'end': time_sec,
                            'velocity': msg.velocity if msg.type == 'note_on' else 64
                        })
                        del active_notes[msg.note]
        
        return sorted(notes, key=lambda n: n['start'])
    
    def _detect_from_polyphony(self, notes: List[Dict],
                               verbose: bool) -> List[Tuple[float, bool]]:
        """
        Detect pedal from polyphony (note overlap) patterns.
        
        High polyphony suggests pedal usage.
        """
        if len(notes) == 0:
            return []
        
        # Sample polyphony at regular intervals
        duration = max(n['end'] for n in notes)
        sample_rate = 20  # 20 samples per second
        num_samples = int(duration * sample_rate)
        
        times = np.linspace(0, duration, num_samples)
        polyphony = np.zeros(num_samples)
        
        # Count simultaneous notes at each time
        for i, t in enumerate(times):
            count = sum(1 for note in notes if note['start'] <= t <= note['end'])
            polyphony[i] = count
        
        # Detect pedal regions (high polyphony)
        pedal_down = polyphony >= self.overlap_threshold
        
        # Find transitions (on/off edges)
        pedal_events = []
        currently_down = False
        
        for i in range(len(pedal_down)):
            if pedal_down[i] and not currently_down:
                # Pedal down
                pedal_events.append((times[i], True))
                currently_down = True
            elif not pedal_down[i] and currently_down:
                # Pedal up
                pedal_events.append((times[i], False))
                currently_down = False
        
        # Close pedal if still down at end
        if currently_down:
            pedal_events.append((duration, False))
        
        return pedal_events
    
    def _refine_with_audio(self, pedal_events: List[Tuple[float, bool]],
                          audio_path: str, verbose: bool) -> List[Tuple[float, bool]]:
        """
        Refine pedal detection using audio resonance analysis.
        
        Harmonic resonance in audio suggests sustained notes (pedal effect).
        """
        try:
            if verbose:
                print("    Analyzing harmonic resonance in audio...")
            
            # Load audio
            y, sr = librosa.load(audio_path, sr=22050)
            
            # Compute spectral centroid (brightness) and spectral rolloff
            # Pedal tends to increase resonance (more high-frequency content)
            centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=512)
            rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, hop_length=512)
            
            # Normalize
            centroid = (centroid - np.mean(centroid)) / (np.std(centroid) + 1e-8)
            rolloff = (rolloff - np.mean(rolloff)) / (np.std(rolloff) + 1e-8)
            
            # Combined resonance score
            resonance = (centroid[0] + rolloff[0]) / 2
            times = librosa.frames_to_time(np.arange(len(resonance)), sr=sr, hop_length=512)
            
            # Refine pedal events based on resonance
            # (This is a simplified approach; full implementation would use more sophisticated analysis)
            refined_events = []
            for event_time, pedal_down in pedal_events:
                # Find closest time in resonance array
                idx = np.argmin(np.abs(times - event_time))
                
                # Check if resonance supports pedal hypothesis
                if pedal_down:
                    # Pedal down: expect increase in resonance
                    if idx < len(resonance) - 10:
                        avg_resonance = np.mean(resonance[idx:idx+10])
                        if avg_resonance > -0.5:  # Threshold
                            refined_events.append((event_time, pedal_down))
                    else:
                        refined_events.append((event_time, pedal_down))
                else:
                    # Pedal up: always keep
                    refined_events.append((event_time, pedal_down))
            
            return refined_events
            
        except Exception as e:
            if verbose:
                print(f"    Warning: Audio analysis failed ({e}), using pattern-only detection")
            return pedal_events
    
    def _filter_short_events(self, pedal_events: List[Tuple[float, bool]]
                            ) -> List[Tuple[float, bool]]:
        """Remove very short pedal events (likely false positives)."""
        if len(pedal_events) < 2:
            return pedal_events
        
        filtered = []
        i = 0
        
        while i < len(pedal_events):
            time, pedal_down = pedal_events[i]
            
            if pedal_down and i + 1 < len(pedal_events):
                # Check duration until next up event
                next_time, next_down = pedal_events[i + 1]
                duration = next_time - time
                
                if duration >= self.min_pedal_duration:
                    filtered.append((time, pedal_down))
                    filtered.append((next_time, next_down))
                # else: skip short pedal event
                
                i += 2
            else:
                filtered.append((time, pedal_down))
                i += 1
        
        return filtered

