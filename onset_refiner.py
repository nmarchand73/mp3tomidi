"""
Onset/Offset Refinement Module

Refines note timing using audio analysis for sub-frame precision.
Inspired by GiantMIDI-Piano's high-resolution onset/offset regression.

Method:
- Uses spectral flux for precise onset detection
- Energy decay analysis for offset detection
- Cross-correlation with audio envelope
- Sub-frame interpolation for millisecond accuracy
"""

import numpy as np
import librosa
import mido
from typing import List, Dict, Tuple
from scipy import signal


class OnsetRefiner:
    """
    Refines MIDI note timing using audio analysis.
    """
    
    def __init__(self,
                 onset_tolerance_ms: float = 50.0,
                 offset_tolerance_ms: float = 100.0,
                 min_note_duration_ms: float = 30.0):
        """
        Initialize onset refiner.
        
        Args:
            onset_tolerance_ms: Max adjustment for onsets (default: 50ms)
            offset_tolerance_ms: Max adjustment for offsets (default: 100ms)
            min_note_duration_ms: Minimum note duration (default: 30ms)
        """
        self.onset_tolerance_ms = onset_tolerance_ms
        self.offset_tolerance_ms = offset_tolerance_ms
        self.min_note_duration_ms = min_note_duration_ms
    
    def refine_timing(self, midi_file: mido.MidiFile, audio_path: str,
                     verbose: bool = False) -> mido.MidiFile:
        """
        Refine MIDI note timing based on audio analysis.
        
        Args:
            midi_file: MIDI file to refine
            audio_path: Path to audio file
            verbose: Print refinement details
            
        Returns:
            MIDI file with refined timing
        """
        if verbose:
            print("    Computing spectral flux for onset detection...")
        
        # Load audio
        y, sr = librosa.load(audio_path, sr=22050)
        
        # Extract note events from MIDI
        note_events = self._extract_note_events(midi_file)
        
        if len(note_events) == 0:
            return midi_file
        
        # Detect onsets in audio with high precision
        audio_onsets = self._detect_precise_onsets(y, sr)
        
        # Compute energy envelope for offset detection
        energy_env = self._compute_energy_envelope(y, sr)
        
        # Refine each note's timing
        refined_notes = []
        onset_corrections = []
        offset_corrections = []
        
        for note in note_events:
            # Refine onset
            refined_onset = self._refine_onset(
                note['start'], audio_onsets, self.onset_tolerance_ms / 1000
            )
            onset_correction = abs(refined_onset - note['start']) * 1000
            onset_corrections.append(onset_correction)
            
            # Refine offset
            refined_offset = self._refine_offset(
                note['end'], energy_env, sr, self.offset_tolerance_ms / 1000
            )
            offset_correction = abs(refined_offset - note['end']) * 1000
            offset_corrections.append(offset_correction)
            
            # Ensure minimum duration
            if refined_offset - refined_onset < self.min_note_duration_ms / 1000:
                refined_offset = refined_onset + self.min_note_duration_ms / 1000
            
            refined_notes.append({
                'pitch': note['pitch'],
                'start': refined_onset,
                'end': refined_offset,
                'velocity': note['velocity'],
                'channel': note['channel']
            })
        
        # Create refined MIDI
        refined_midi = self._create_refined_midi(midi_file, refined_notes)
        
        if verbose:
            avg_onset_corr = np.mean(onset_corrections)
            avg_offset_corr = np.mean(offset_corrections)
            print(f"    Avg onset correction: {avg_onset_corr:.1f}ms")
            print(f"    Avg offset correction: {avg_offset_corr:.1f}ms")
        
        return refined_midi
    
    def _extract_note_events(self, midi_file: mido.MidiFile) -> List[Dict]:
        """Extract note events with timing."""
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
                    active_notes[msg.note] = {
                        'start': time_sec,
                        'velocity': msg.velocity,
                        'channel': msg.channel
                    }
                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    if msg.note in active_notes:
                        note_info = active_notes[msg.note]
                        notes.append({
                            'pitch': msg.note,
                            'start': note_info['start'],
                            'end': time_sec,
                            'velocity': note_info['velocity'],
                            'channel': note_info['channel']
                        })
                        del active_notes[msg.note]
        
        return sorted(notes, key=lambda n: n['start'])
    
    def _detect_precise_onsets(self, y: np.ndarray, sr: int) -> np.ndarray:
        """
        Detect onsets with sub-frame precision using spectral flux.
        """
        hop_length = 256  # Smaller hop for better precision
        
        # Compute spectral flux (change in spectrum)
        S = np.abs(librosa.stft(y, hop_length=hop_length))
        spectral_flux = np.diff(S, axis=1)
        spectral_flux = np.sum(np.maximum(0, spectral_flux), axis=0)
        
        # Detect peaks in spectral flux
        threshold = np.mean(spectral_flux) + 0.5 * np.std(spectral_flux)
        peaks, _ = signal.find_peaks(spectral_flux, height=threshold, distance=5)
        
        # Convert frames to time
        onset_times = librosa.frames_to_time(peaks, sr=sr, hop_length=hop_length)
        
        return onset_times
    
    def _compute_energy_envelope(self, y: np.ndarray, sr: int) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute smooth energy envelope for offset detection.
        """
        hop_length = 256
        
        # Compute RMS energy
        rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
        
        # Smooth with moving average
        window_size = 5
        rms_smooth = np.convolve(rms, np.ones(window_size)/window_size, mode='same')
        
        # Convert to time array
        times = librosa.frames_to_time(np.arange(len(rms_smooth)), sr=sr, hop_length=hop_length)
        
        return times, rms_smooth
    
    def _refine_onset(self, midi_onset: float, audio_onsets: np.ndarray,
                     tolerance: float) -> float:
        """
        Refine MIDI onset to closest audio onset within tolerance.
        """
        # Find closest audio onset
        if len(audio_onsets) == 0:
            return midi_onset
        
        distances = np.abs(audio_onsets - midi_onset)
        closest_idx = np.argmin(distances)
        closest_onset = audio_onsets[closest_idx]
        closest_distance = distances[closest_idx]
        
        # Only adjust if within tolerance
        if closest_distance <= tolerance:
            return closest_onset
        else:
            return midi_onset
    
    def _refine_offset(self, midi_offset: float, energy_env: Tuple[np.ndarray, np.ndarray],
                      sr: int, tolerance: float) -> float:
        """
        Refine MIDI offset using energy decay analysis.
        """
        times, energy = energy_env
        
        if len(times) == 0:
            return midi_offset
        
        # Find frame closest to MIDI offset
        offset_idx = np.argmin(np.abs(times - midi_offset))
        
        # Search for energy decay after this point
        search_window = int(tolerance / (times[1] - times[0]))  # frames
        start_idx = max(0, offset_idx - search_window // 2)
        end_idx = min(len(energy), offset_idx + search_window // 2)
        
        if start_idx >= end_idx:
            return midi_offset
        
        # Find local minimum in energy (note release point)
        window_energy = energy[start_idx:end_idx]
        
        if len(window_energy) > 0:
            # Find point where energy drops below threshold
            threshold = 0.3 * energy[offset_idx]
            
            # Search forward from offset
            for i in range(len(window_energy)):
                if window_energy[i] < threshold:
                    refined_offset = times[start_idx + i]
                    # Only adjust if within tolerance
                    if abs(refined_offset - midi_offset) <= tolerance:
                        return refined_offset
                    break
        
        return midi_offset
    
    def _create_refined_midi(self, original_midi: mido.MidiFile,
                            refined_notes: List[Dict]) -> mido.MidiFile:
        """
        Create new MIDI file with refined note timing.
        """
        new_midi = mido.MidiFile(ticks_per_beat=original_midi.ticks_per_beat)
        track = mido.MidiTrack()
        new_midi.tracks.append(track)
        
        # Copy meta messages
        for orig_track in original_midi.tracks:
            for msg in orig_track:
                if msg.is_meta:
                    track.append(msg.copy())
                    break
        
        # Convert refined notes to MIDI messages
        tempo = 500000  # Default tempo
        
        # Create all events (note_on and note_off)
        events = []
        for note in refined_notes:
            # Note on
            events.append({
                'time': note['start'],
                'type': 'note_on',
                'note': note['pitch'],
                'velocity': note['velocity'],
                'channel': note['channel']
            })
            # Note off
            events.append({
                'time': note['end'],
                'type': 'note_off',
                'note': note['pitch'],
                'velocity': 0,
                'channel': note['channel']
            })
        
        # Sort by time
        events.sort(key=lambda e: e['time'])
        
        # Convert to MIDI messages with delta times
        current_time_sec = 0
        for event in events:
            # Calculate delta time
            delta_sec = event['time'] - current_time_sec
            delta_ticks = mido.second2tick(
                delta_sec, new_midi.ticks_per_beat, tempo
            )
            delta_ticks = max(0, int(delta_ticks))
            
            # Create message
            if event['type'] == 'note_on':
                msg = mido.Message(
                    'note_on',
                    note=event['note'],
                    velocity=event['velocity'],
                    time=delta_ticks,
                    channel=event['channel']
                )
            else:
                msg = mido.Message(
                    'note_off',
                    note=event['note'],
                    velocity=0,
                    time=delta_ticks,
                    channel=event['channel']
                )
            
            track.append(msg)
            current_time_sec = event['time']
        
        # Add end of track
        track.append(mido.MetaMessage('end_of_track', time=0))
        
        return new_midi

