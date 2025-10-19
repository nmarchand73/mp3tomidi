"""
Audio-MIDI Alignment Module

Aligns MIDI note timings with audio using spectral analysis and onset detection.
Uses Dynamic Time Warping (DTW) to find optimal alignment.
"""

import numpy as np
import librosa
import mido
from typing import List, Tuple, Dict
from scipy import signal
from pathlib import Path


class AudioMidiAligner:
    """Aligns MIDI timing with audio using spectral analysis."""
    
    def __init__(self, 
                 hop_length: int = 512,
                 sr: int = 22050):
        """
        Initialize the aligner.
        
        Args:
            hop_length: Hop length for spectral analysis (default: 512)
            sr: Sample rate for audio analysis (default: 22050)
        """
        self.hop_length = hop_length
        self.sr = sr
        self.alignment_cost = None
        self.alignment_path = None
    
    def align(self, 
              audio_file: str, 
              midi_file: mido.MidiFile,
              verbose: bool = False) -> mido.MidiFile:
        """
        Align MIDI timing to audio using onset detection and DTW.
        
        Args:
            audio_file: Path to audio file (MP3, WAV, etc.)
            midi_file: MIDI file to align
            verbose: Print alignment information
            
        Returns:
            Aligned MIDI file
        """
        if verbose:
            print("  Analyzing audio onsets...")
        
        # Extract onsets from audio
        audio_onsets = self._extract_audio_onsets(audio_file)
        
        if verbose:
            print(f"  Detected {len(audio_onsets)} onsets in audio")
            print("  Extracting MIDI onsets...")
        
        # Extract onsets from MIDI
        midi_onsets = self._extract_midi_onsets(midi_file)
        
        if verbose:
            print(f"  Detected {len(midi_onsets)} notes in MIDI")
        
        # If not enough data, return original
        if len(audio_onsets) < 10 or len(midi_onsets) < 10:
            if verbose:
                print("  Warning: Not enough onsets for alignment, skipping...")
            return midi_file
        
        if verbose:
            print("  Computing alignment using Dynamic Time Warping...")
        
        # Perform DTW alignment
        alignment_map = self._compute_dtw_alignment(
            audio_onsets, 
            midi_onsets,
            verbose=verbose
        )
        
        if verbose:
            print("  Applying time corrections to MIDI...")
        
        # Apply alignment to MIDI
        aligned_midi = self._apply_alignment(midi_file, alignment_map)
        
        if verbose:
            avg_correction = np.mean([abs(old - new) for old, new in alignment_map.items()])
            print(f"  Average time correction: {avg_correction*1000:.1f} ms")
        
        return aligned_midi
    
    def _extract_audio_onsets(self, audio_file: str) -> np.ndarray:
        """
        Extract onset times from audio using spectral flux.
        
        Args:
            audio_file: Path to audio file
            
        Returns:
            Array of onset times in seconds
        """
        # Load audio
        y, sr = librosa.load(audio_file, sr=self.sr)
        
        # Compute onset strength envelope
        onset_env = librosa.onset.onset_strength(
            y=y, 
            sr=sr,
            hop_length=self.hop_length,
            aggregate=np.median
        )
        
        # Detect onsets
        onset_frames = librosa.onset.onset_detect(
            onset_envelope=onset_env,
            sr=sr,
            hop_length=self.hop_length,
            backtrack=True,
            pre_max=3,
            post_max=3,
            pre_avg=3,
            post_avg=5,
            delta=0.07,
            wait=10
        )
        
        # Convert frames to time
        onset_times = librosa.frames_to_time(
            onset_frames,
            sr=sr,
            hop_length=self.hop_length
        )
        
        return onset_times
    
    def _extract_midi_onsets(self, midi_file: mido.MidiFile) -> np.ndarray:
        """
        Extract onset times from MIDI file.
        
        Args:
            midi_file: MIDI file
            
        Returns:
            Array of onset times in seconds
        """
        onsets = []
        
        for track in midi_file.tracks:
            time = 0
            for msg in track:
                time += msg.time
                if msg.type == 'note_on' and msg.velocity > 0:
                    # Convert ticks to seconds
                    seconds = mido.tick2second(
                        time, 
                        midi_file.ticks_per_beat,
                        500000  # Default tempo (120 BPM)
                    )
                    onsets.append(seconds)
        
        return np.array(sorted(onsets))
    
    def _compute_dtw_alignment(self,
                               audio_onsets: np.ndarray,
                               midi_onsets: np.ndarray,
                               verbose: bool = False) -> Dict[float, float]:
        """
        Compute alignment mapping using Dynamic Time Warping.
        
        Args:
            audio_onsets: Array of audio onset times
            midi_onsets: Array of MIDI onset times
            verbose: Print DTW information
            
        Returns:
            Dictionary mapping MIDI time -> aligned audio time
        """
        # Create feature matrices for DTW
        # Use local neighborhoods around each onset
        
        # Subsample if too many onsets (for performance)
        max_onsets = 500
        if len(audio_onsets) > max_onsets:
            audio_onsets = audio_onsets[::len(audio_onsets)//max_onsets]
        if len(midi_onsets) > max_onsets:
            midi_onsets = midi_onsets[::len(midi_onsets)//max_onsets]
        
        # Compute cost matrix based on onset timing differences
        n_audio = len(audio_onsets)
        n_midi = len(midi_onsets)
        
        # Use a simplified DTW approach with onset intervals
        # Compute inter-onset intervals (rhythm)
        audio_ioi = np.diff(audio_onsets) if len(audio_onsets) > 1 else np.array([])
        midi_ioi = np.diff(midi_onsets) if len(midi_onsets) > 1 else np.array([])
        
        # If not enough data, use simple linear mapping
        if len(audio_ioi) < 2 or len(midi_ioi) < 2:
            # Linear time stretch
            ratio = audio_onsets[-1] / midi_onsets[-1] if midi_onsets[-1] > 0 else 1.0
            return {midi_t: midi_t * ratio for midi_t in midi_onsets}
        
        # Compute DTW on inter-onset intervals
        # This is more robust than absolute times
        D, wp = self._dtw(audio_ioi, midi_ioi)
        
        if verbose:
            print(f"  DTW cost: {D[-1, -1]:.2f}")
        
        # Convert warping path to time mapping
        alignment_map = {}
        
        # Map each MIDI onset to corresponding audio onset
        for i, (ai, mi) in enumerate(wp):
            if mi < len(midi_onsets) and ai < len(audio_onsets):
                alignment_map[midi_onsets[mi]] = audio_onsets[ai]
        
        return alignment_map
    
    def _dtw(self, x: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, List[Tuple]]:
        """
        Simple DTW implementation for onset interval alignment.
        
        Args:
            x: First sequence (audio IOIs)
            y: Second sequence (MIDI IOIs)
            
        Returns:
            Tuple of (cost matrix, warping path)
        """
        n, m = len(x), len(y)
        
        # Compute cost matrix
        cost = np.zeros((n, m))
        for i in range(n):
            for j in range(m):
                cost[i, j] = abs(x[i] - y[j])
        
        # Accumulated cost matrix
        D = np.zeros((n + 1, m + 1))
        D[0, :] = np.inf
        D[:, 0] = np.inf
        D[0, 0] = 0
        
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                D[i, j] = cost[i-1, j-1] + min(D[i-1, j], D[i, j-1], D[i-1, j-1])
        
        # Backtrack to find warping path
        i, j = n, m
        path = [(i-1, j-1)]
        
        while i > 1 or j > 1:
            if i == 1:
                j -= 1
            elif j == 1:
                i -= 1
            else:
                # Choose minimum of three predecessors
                costs = [D[i-1, j], D[i, j-1], D[i-1, j-1]]
                idx = np.argmin(costs)
                if idx == 0:
                    i -= 1
                elif idx == 1:
                    j -= 1
                else:
                    i -= 1
                    j -= 1
            path.append((i-1, j-1))
        
        path.reverse()
        return D, path
    
    def _apply_alignment(self, 
                        midi_file: mido.MidiFile,
                        alignment_map: Dict[float, float]) -> mido.MidiFile:
        """
        Apply time alignment to MIDI file.
        
        Args:
            midi_file: Original MIDI file
            alignment_map: Mapping of MIDI time -> audio time
            
        Returns:
            Time-aligned MIDI file
        """
        # Create interpolation function for smooth alignment
        midi_times = np.array(sorted(alignment_map.keys()))
        audio_times = np.array([alignment_map[t] for t in midi_times])
        
        # Create new MIDI file
        aligned = mido.MidiFile(ticks_per_beat=midi_file.ticks_per_beat)
        
        for track in midi_file.tracks:
            new_track = mido.MidiTrack()
            
            # Process each message
            absolute_time = 0
            prev_absolute_time = 0
            
            for msg in track:
                absolute_time += msg.time
                
                # Get original time in seconds
                orig_seconds = mido.tick2second(
                    absolute_time,
                    midi_file.ticks_per_beat,
                    500000  # Default tempo
                )
                
                # Interpolate aligned time
                if len(midi_times) > 1:
                    aligned_seconds = np.interp(orig_seconds, midi_times, audio_times)
                else:
                    aligned_seconds = orig_seconds
                
                # Convert back to ticks
                aligned_ticks = mido.second2tick(
                    aligned_seconds,
                    midi_file.ticks_per_beat,
                    500000
                )
                
                # Compute delta time
                delta_ticks = max(0, aligned_ticks - prev_absolute_time)
                
                # Create new message with adjusted time
                new_msg = msg.copy(time=int(delta_ticks))
                new_track.append(new_msg)
                
                prev_absolute_time = aligned_ticks
            
            aligned.tracks.append(new_track)
        
        return aligned

