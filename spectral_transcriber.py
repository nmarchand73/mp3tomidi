"""
Advanced Spectral Transcription Module

Uses Constant-Q Transform (CQT) and harmonic analysis for improved
piano transcription accuracy compared to basic neural network approaches.
"""

import numpy as np
import librosa
import mido
from typing import List, Tuple, Dict
from scipy import signal
from collections import defaultdict


class SpectralTranscriber:
    """
    Advanced piano transcription using spectral analysis.
    
    Uses:
    - Constant-Q Transform (CQT) for better frequency resolution
    - Harmonic detection for accurate pitch identification  
    - Temporal smoothing for note onset/offset detection
    """
    
    # Piano frequency range: A0 (27.5 Hz) to C8 (4186 Hz)
    PIANO_MIN_FREQ = 27.5
    PIANO_MAX_FREQ = 4186.0
    
    def __init__(self,
                 sr: int = 22050,
                 hop_length: int = 512,
                 n_bins: int = 84,  # 7 octaves
                 bins_per_octave: int = 12,
                 onset_threshold: float = 0.3,
                 min_note_duration: float = 0.05):
        """
        Initialize the spectral transcriber.
        
        Args:
            sr: Sample rate (default: 22050)
            hop_length: Hop length for analysis (default: 512)
            n_bins: Number of CQT bins (default: 84 = 7 octaves)
            bins_per_octave: Bins per octave (default: 12 = semitones)
            onset_threshold: Threshold for note onset detection (default: 0.3)
            min_note_duration: Minimum note duration in seconds (default: 0.05)
        """
        self.sr = sr
        self.hop_length = hop_length
        self.n_bins = n_bins
        self.bins_per_octave = bins_per_octave
        self.onset_threshold = onset_threshold
        self.min_note_duration = min_note_duration
        
        # MIDI note 21 (A0) = 27.5 Hz
        self.fmin = librosa.midi_to_hz(21)  # A0
    
    def transcribe(self, 
                   audio_file: str,
                   verbose: bool = False) -> mido.MidiFile:
        """
        Transcribe audio to MIDI using CQT analysis.
        
        Args:
            audio_file: Path to audio file
            verbose: Print progress information
            
        Returns:
            MIDI file with transcribed notes
        """
        if verbose:
            print("  Loading audio...")
        
        # Load audio
        y, sr = librosa.load(audio_file, sr=self.sr)
        
        if verbose:
            print("  Computing Constant-Q Transform...")
        
        # Compute CQT
        C = librosa.cqt(
            y=y,
            sr=sr,
            hop_length=self.hop_length,
            fmin=self.fmin,
            n_bins=self.n_bins,
            bins_per_octave=self.bins_per_octave
        )
        
        # Convert to magnitude
        C_mag = np.abs(C)
        
        if verbose:
            print("  Enhancing harmonics...")
        
        # Apply harmonic enhancement
        C_harmonic = self._enhance_harmonics(C_mag)
        
        if verbose:
            print("  Detecting note onsets and offsets...")
        
        # Detect notes from CQT
        notes = self._detect_notes_from_cqt(
            C_harmonic,
            sr,
            verbose=verbose
        )
        
        if verbose:
            print(f"  Detected {len(notes)} notes")
            print("  Creating MIDI file...")
        
        # Convert to MIDI
        midi_file = self._notes_to_midi(notes)
        
        return midi_file
    
    def _enhance_harmonics(self, C: np.ndarray) -> np.ndarray:
        """
        Enhance harmonic content in CQT representation.
        
        Uses harmonic-percussive source separation to emphasize
        tonal (harmonic) content over transients.
        
        Args:
            C: CQT magnitude spectrogram
            
        Returns:
            Enhanced CQT with stronger harmonics
        """
        # Apply harmonic-percussive source separation
        C_harmonic, C_percussive = librosa.decompose.hpss(
            C,
            margin=2.0
        )
        
        # Weight: 80% harmonic, 20% percussive (for attacks)
        C_enhanced = 0.8 * C_harmonic + 0.2 * C_percussive
        
        # Apply temporal smoothing to reduce noise
        kernel_size = 3
        C_enhanced = signal.medfilt2d(C_enhanced, kernel_size=(1, kernel_size))
        
        return C_enhanced
    
    def _detect_notes_from_cqt(self,
                               C: np.ndarray,
                               sr: int,
                               verbose: bool = False) -> List[Dict]:
        """
        Detect notes from CQT representation.
        
        Args:
            C: CQT magnitude spectrogram
            sr: Sample rate
            verbose: Print detection info
            
        Returns:
            List of note dictionaries with pitch, start, end, velocity
        """
        notes = []
        
        # Normalize CQT
        C_norm = librosa.util.normalize(C, axis=1)
        
        # For each pitch (CQT bin)
        for pitch_bin in range(C_norm.shape[0]):
            # Get activation for this pitch over time
            activation = C_norm[pitch_bin, :]
            
            # Smooth activation
            activation = librosa.util.normalize(activation)
            
            # Find peaks (note onsets)
            peaks, properties = signal.find_peaks(
                activation,
                height=self.onset_threshold,
                distance=int(self.sr / self.hop_length * 0.05),  # Min 50ms between notes
                prominence=0.1
            )
            
            if len(peaks) == 0:
                continue
            
            # For each detected onset
            for peak_idx in peaks:
                start_frame = peak_idx
                start_time = librosa.frames_to_time(
                    start_frame,
                    sr=sr,
                    hop_length=self.hop_length
                )
                
                # Find note offset (when activation drops below threshold)
                offset_frame = start_frame + 1
                threshold = activation[start_frame] * 0.3  # 30% of peak
                
                while offset_frame < len(activation):
                    if activation[offset_frame] < threshold:
                        break
                    offset_frame += 1
                
                end_time = librosa.frames_to_time(
                    offset_frame,
                    sr=sr,
                    hop_length=self.hop_length
                )
                
                duration = end_time - start_time
                
                # Filter very short notes
                if duration < self.min_note_duration:
                    continue
                
                # Convert CQT bin to MIDI note
                midi_note = pitch_bin + 21  # Offset to A0 (MIDI 21)
                
                # Velocity from peak height
                velocity = int(np.clip(properties['peak_heights'][list(peaks).index(peak_idx)] * 127, 1, 127))
                
                notes.append({
                    'pitch': midi_note,
                    'start': start_time,
                    'end': end_time,
                    'velocity': velocity
                })
        
        # Sort by start time
        notes.sort(key=lambda n: n['start'])
        
        if verbose:
            print(f"  Note range: MIDI {min(n['pitch'] for n in notes)} - {max(n['pitch'] for n in notes)}")
        
        return notes
    
    def _notes_to_midi(self, notes: List[Dict]) -> mido.MidiFile:
        """
        Convert detected notes to MIDI file.
        
        Args:
            notes: List of note dictionaries
            
        Returns:
            MIDI file
        """
        midi = mido.MidiFile(ticks_per_beat=480)
        track = mido.MidiTrack()
        midi.tracks.append(track)
        
        # Add track name
        track.append(mido.MetaMessage('track_name', name='Piano (CQT)', time=0))
        
        # Set tempo (120 BPM)
        track.append(mido.MetaMessage('set_tempo', tempo=500000, time=0))
        
        # Create note events
        events = []
        for note in notes:
            # Note on event
            events.append({
                'time': note['start'],
                'type': 'note_on',
                'note': int(note['pitch']),
                'velocity': int(note['velocity'])
            })
            
            # Note off event
            events.append({
                'time': note['end'],
                'type': 'note_off',
                'note': int(note['pitch']),
                'velocity': 0
            })
        
        # Sort by time
        events.sort(key=lambda e: (e['time'], e['type'] == 'note_off'))
        
        # Convert to MIDI messages with delta times
        prev_time = 0
        for event in events:
            delta_time = event['time'] - prev_time
            delta_ticks = int(delta_time * midi.ticks_per_beat * 2)  # Assuming 120 BPM
            
            if event['type'] == 'note_on':
                track.append(mido.Message(
                    'note_on',
                    note=event['note'],
                    velocity=event['velocity'],
                    time=delta_ticks
                ))
            else:
                track.append(mido.Message(
                    'note_off',
                    note=event['note'],
                    velocity=0,
                    time=delta_ticks
                ))
            
            prev_time = event['time']
        
        # End of track
        track.append(mido.MetaMessage('end_of_track', time=0))
        
        return midi

