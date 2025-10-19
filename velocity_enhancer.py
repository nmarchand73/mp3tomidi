"""
Velocity Enhancement Module

Improves MIDI velocity accuracy using audio spectral analysis.
Inspired by GiantMIDI-Piano's velocity modeling.

Method:
- Analyzes spectral energy at each note onset
- Computes attack transient characteristics
- Recalibrates velocities to realistic piano dynamics
- Maps to proper dynamic range (pp to ff)
"""

import numpy as np
import librosa
import mido
from typing import List, Dict, Tuple


class VelocityEnhancer:
    """
    Enhances MIDI velocities using audio analysis.
    """
    
    def __init__(self,
                 min_velocity: int = 30,
                 max_velocity: int = 120,
                 smoothing_window: int = 3):
        """
        Initialize velocity enhancer.
        
        Args:
            min_velocity: Minimum MIDI velocity (default: 30, pianissimo)
            max_velocity: Maximum MIDI velocity (default: 120, fortissimo)
            smoothing_window: Window size for velocity smoothing (default: 3 notes)
        """
        self.min_velocity = min_velocity
        self.max_velocity = max_velocity
        self.smoothing_window = smoothing_window
    
    def enhance_velocities(self, midi_file: mido.MidiFile, audio_path: str,
                          verbose: bool = False) -> mido.MidiFile:
        """
        Enhance MIDI velocities based on audio analysis.
        
        Args:
            midi_file: MIDI file to enhance
            audio_path: Path to audio file
            verbose: Print enhancement details
            
        Returns:
            MIDI file with enhanced velocities
        """
        if verbose:
            print("    Analyzing spectral energy at note onsets...")
        
        # Load audio
        y, sr = librosa.load(audio_path, sr=22050)
        
        # Extract note onsets from MIDI
        note_onsets = self._extract_note_onsets(midi_file)
        
        if len(note_onsets) == 0:
            return midi_file
        
        # Analyze spectral energy at each onset
        onset_energies = self._compute_onset_energies(y, sr, note_onsets)
        
        # Compute attack characteristics
        attack_sharpness = self._compute_attack_sharpness(y, sr, note_onsets)
        
        # Combine features to estimate velocity
        enhanced_velocities = self._estimate_velocities(
            onset_energies, attack_sharpness, note_onsets
        )
        
        # Smooth velocities for musical coherence
        enhanced_velocities = self._smooth_velocities(enhanced_velocities)
        
        # Apply enhanced velocities to MIDI
        enhanced_midi = self._apply_velocities(
            midi_file, note_onsets, enhanced_velocities
        )
        
        if verbose:
            orig_range = f"{min(n['velocity'] for n in note_onsets)}-{max(n['velocity'] for n in note_onsets)}"
            new_range = f"{min(enhanced_velocities)}-{max(enhanced_velocities)}"
            print(f"    Velocity range: {orig_range} → {new_range}")
        
        return enhanced_midi
    
    def _extract_note_onsets(self, midi_file: mido.MidiFile) -> List[Dict]:
        """Extract note onset information from MIDI."""
        onsets = []
        
        for track in midi_file.tracks:
            time = 0
            tempo = 500000
            
            for msg in track:
                time += msg.time
                
                if msg.type == 'set_tempo':
                    tempo = msg.tempo
                
                if msg.type == 'note_on' and msg.velocity > 0:
                    time_sec = mido.tick2second(time, midi_file.ticks_per_beat, tempo)
                    onsets.append({
                        'time': time_sec,
                        'pitch': msg.note,
                        'velocity': msg.velocity,
                        'tick': time,
                        'channel': msg.channel
                    })
        
        return sorted(onsets, key=lambda n: n['time'])
    
    def _compute_onset_energies(self, y: np.ndarray, sr: int,
                                note_onsets: List[Dict]) -> np.ndarray:
        """
        Compute spectral energy at each note onset.
        
        Higher energy = louder note = higher velocity.
        """
        hop_length = 512
        
        # Compute STFT for spectral analysis
        S = np.abs(librosa.stft(y, hop_length=hop_length))
        
        # Convert to dB scale
        S_db = librosa.amplitude_to_db(S, ref=np.max)
        
        # Extract energy at each onset
        energies = []
        for onset in note_onsets:
            # Convert time to frame
            frame = librosa.time_to_frames(onset['time'], sr=sr, hop_length=hop_length)
            
            if frame < S_db.shape[1]:
                # Get spectral energy in relevant frequency range for this pitch
                freq_hz = librosa.midi_to_hz(onset['pitch'])
                freq_bins = librosa.fft_frequencies(sr=sr, n_fft=2048)
                
                # Focus on fundamental and first few harmonics
                bin_idx = np.argmin(np.abs(freq_bins - freq_hz))
                
                # Sum energy around fundamental (±5 bins)
                start_bin = max(0, bin_idx - 5)
                end_bin = min(len(freq_bins), bin_idx + 5)
                
                energy = np.mean(S_db[start_bin:end_bin, frame])
                energies.append(energy)
            else:
                # Use last available frame
                energy = np.mean(S_db[:, -1])
                energies.append(energy)
        
        return np.array(energies)
    
    def _compute_attack_sharpness(self, y: np.ndarray, sr: int,
                                  note_onsets: List[Dict]) -> np.ndarray:
        """
        Compute attack transient sharpness.
        
        Sharper attack = more percussive = higher velocity.
        """
        hop_length = 512
        
        # Compute onset strength envelope
        onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)
        
        sharpness = []
        for onset in note_onsets:
            frame = librosa.time_to_frames(onset['time'], sr=sr, hop_length=hop_length)
            
            if frame < len(onset_env) - 5:
                # Measure slope of onset envelope (attack steepness)
                attack_slope = onset_env[frame] - onset_env[max(0, frame - 2)]
                sharpness.append(attack_slope)
            else:
                sharpness.append(0.0)
        
        return np.array(sharpness)
    
    def _estimate_velocities(self, energies: np.ndarray, sharpness: np.ndarray,
                            note_onsets: List[Dict]) -> np.ndarray:
        """
        Estimate velocities from combined audio features.
        
        Combines spectral energy and attack sharpness.
        """
        if len(energies) == 0:
            return np.array([])
        
        # Normalize features
        energies_norm = (energies - np.min(energies)) / (np.max(energies) - np.min(energies) + 1e-8)
        sharpness_norm = (sharpness - np.min(sharpness)) / (np.max(sharpness) - np.min(sharpness) + 1e-8)
        
        # Combine features (70% energy, 30% attack)
        combined = 0.7 * energies_norm + 0.3 * sharpness_norm
        
        # Map to velocity range
        velocities = self.min_velocity + combined * (self.max_velocity - self.min_velocity)
        
        # Ensure integer values
        velocities = np.clip(velocities, self.min_velocity, self.max_velocity).astype(int)
        
        return velocities
    
    def _smooth_velocities(self, velocities: np.ndarray) -> np.ndarray:
        """
        Smooth velocity changes for musical coherence.
        
        Applies moving average to avoid jarring velocity jumps.
        """
        if len(velocities) < self.smoothing_window:
            return velocities
        
        # Apply moving average
        window = np.ones(self.smoothing_window) / self.smoothing_window
        smoothed = np.convolve(velocities, window, mode='same')
        
        # Preserve original range
        smoothed = np.clip(smoothed, self.min_velocity, self.max_velocity).astype(int)
        
        return smoothed
    
    def _apply_velocities(self, midi_file: mido.MidiFile,
                         note_onsets: List[Dict],
                         enhanced_velocities: np.ndarray) -> mido.MidiFile:
        """
        Apply enhanced velocities to MIDI file.
        """
        # Create velocity lookup by tick time
        velocity_map = {}
        for onset, velocity in zip(note_onsets, enhanced_velocities):
            key = (onset['tick'], onset['pitch'], onset['channel'])
            velocity_map[key] = int(velocity)
        
        # Create new MIDI with enhanced velocities
        new_midi = mido.MidiFile(ticks_per_beat=midi_file.ticks_per_beat)
        
        for track in midi_file.tracks:
            new_track = mido.MidiTrack()
            time = 0
            
            for msg in track:
                time += msg.time
                
                if msg.type == 'note_on' and msg.velocity > 0:
                    # Look up enhanced velocity
                    key = (time, msg.note, msg.channel)
                    if key in velocity_map:
                        new_velocity = velocity_map[key]
                        new_msg = msg.copy(velocity=new_velocity)
                        new_track.append(new_msg)
                    else:
                        new_track.append(msg.copy())
                else:
                    new_track.append(msg.copy())
            
            new_midi.tracks.append(new_track)
        
        return new_midi

