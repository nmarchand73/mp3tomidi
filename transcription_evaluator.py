"""
Transcription Quality Evaluator

Evaluates MIDI transcription quality by comparing it with the original audio
using spectral analysis and multiple metrics.
"""

import numpy as np
import librosa
import mido
from typing import Dict, List, Tuple
from scipy import signal
from scipy.spatial.distance import cosine


class TranscriptionEvaluator:
    """
    Evaluates transcription quality using spectral analysis.
    
    Metrics:
    - Spectral similarity (chromagram correlation)
    - Onset alignment (F1 score)
    - Pitch accuracy (note-level comparison)
    - Temporal coverage (how much of the audio is transcribed)
    """
    
    def __init__(self, sr: int = 22050, hop_length: int = 512):
        """
        Initialize the evaluator.
        
        Args:
            sr: Sample rate (default: 22050)
            hop_length: Hop length for spectral analysis (default: 512)
        """
        self.sr = sr
        self.hop_length = hop_length
    
    def evaluate(self, 
                 audio_file: str,
                 midi_file: mido.MidiFile,
                 verbose: bool = False) -> Dict[str, float]:
        """
        Evaluate MIDI transcription quality against audio.
        
        Args:
            audio_file: Path to original audio file
            midi_file: Transcribed MIDI file
            verbose: Print detailed information
            
        Returns:
            Dictionary of quality metrics (0-1, higher is better)
        """
        if verbose:
            print("\n  Evaluating transcription quality...")
            print("  Loading and analyzing audio...")
        
        # Load audio
        y, sr = librosa.load(audio_file, sr=self.sr)
        
        # Extract audio features
        audio_chroma = self._extract_chromagram(y, sr)
        audio_onsets = self._extract_onsets(y, sr)
        
        if verbose:
            print(f"  Audio: {len(audio_onsets)} onsets detected")
            print("  Synthesizing MIDI for comparison...")
        
        # Synthesize MIDI to audio for spectral comparison
        midi_audio = self._midi_to_audio_simple(midi_file, len(y))
        midi_chroma = self._extract_chromagram(midi_audio, sr)
        midi_onsets = self._extract_midi_onsets(midi_file)
        
        if verbose:
            print(f"  MIDI: {len(midi_onsets)} notes transcribed")
            print("  Computing similarity metrics...")
        
        # Compute metrics
        metrics = {}
        
        # 1. Spectral similarity (chromagram correlation)
        metrics['spectral_similarity'] = self._compute_spectral_similarity(
            audio_chroma, midi_chroma
        )
        
        # 2. Onset precision/recall/F1
        onset_metrics = self._compute_onset_metrics(audio_onsets, midi_onsets)
        metrics.update(onset_metrics)
        
        # 3. Temporal coverage (how much time is covered by notes)
        metrics['temporal_coverage'] = self._compute_temporal_coverage(
            midi_file, len(y) / sr
        )
        
        # 4. Pitch distribution similarity
        metrics['pitch_distribution'] = self._compute_pitch_distribution(
            y, sr, midi_file
        )
        
        # 5. Overall quality score (weighted average)
        metrics['overall_quality'] = self._compute_overall_score(metrics)
        
        if verbose:
            self._print_metrics(metrics)
        
        return metrics
    
    def _extract_chromagram(self, y: np.ndarray, sr: int) -> np.ndarray:
        """
        Extract chromagram (pitch class profile) from audio.
        
        Args:
            y: Audio signal
            sr: Sample rate
            
        Returns:
            Chromagram matrix (12 x frames)
        """
        chroma = librosa.feature.chroma_cqt(
            y=y,
            sr=sr,
            hop_length=self.hop_length,
            n_chroma=12
        )
        
        # Normalize
        chroma = librosa.util.normalize(chroma, axis=0)
        
        return chroma
    
    def _extract_onsets(self, y: np.ndarray, sr: int) -> np.ndarray:
        """
        Extract onset times from audio.
        
        Args:
            y: Audio signal
            sr: Sample rate
            
        Returns:
            Array of onset times in seconds
        """
        onset_env = librosa.onset.onset_strength(
            y=y,
            sr=sr,
            hop_length=self.hop_length
        )
        
        onset_frames = librosa.onset.onset_detect(
            onset_envelope=onset_env,
            sr=sr,
            hop_length=self.hop_length,
            backtrack=True
        )
        
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
                    seconds = mido.tick2second(
                        time,
                        midi_file.ticks_per_beat,
                        500000  # Default tempo
                    )
                    onsets.append(seconds)
        
        return np.array(sorted(onsets))
    
    def _midi_to_audio_simple(self, 
                               midi_file: mido.MidiFile, 
                               target_length: int) -> np.ndarray:
        """
        Simple MIDI to audio synthesis using additive synthesis.
        
        Args:
            midi_file: MIDI file
            target_length: Target audio length in samples
            
        Returns:
            Synthesized audio signal
        """
        audio = np.zeros(target_length)
        
        # Extract all notes
        notes = []
        for track in midi_file.tracks:
            time = 0
            active_notes = {}
            
            for msg in track:
                time += msg.time
                seconds = mido.tick2second(time, midi_file.ticks_per_beat, 500000)
                
                if msg.type == 'note_on' and msg.velocity > 0:
                    active_notes[msg.note] = (seconds, msg.velocity)
                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    if msg.note in active_notes:
                        start_time, velocity = active_notes[msg.note]
                        notes.append({
                            'pitch': msg.note,
                            'start': start_time,
                            'end': seconds,
                            'velocity': velocity
                        })
                        del active_notes[msg.note]
        
        # Synthesize each note as a sine wave
        for note in notes:
            start_sample = int(note['start'] * self.sr)
            end_sample = int(note['end'] * self.sr)
            
            if start_sample >= len(audio):
                continue
            
            end_sample = min(end_sample, len(audio))
            duration_samples = end_sample - start_sample
            
            if duration_samples <= 0:
                continue
            
            # Generate sine wave
            freq = librosa.midi_to_hz(note['pitch'])
            t = np.arange(duration_samples) / self.sr
            amplitude = note['velocity'] / 127.0 * 0.1  # Scale amplitude
            
            # Simple ADSR envelope
            envelope = np.ones(duration_samples)
            attack_samples = min(int(0.01 * self.sr), duration_samples // 4)
            release_samples = min(int(0.05 * self.sr), duration_samples // 4)
            
            if attack_samples > 0:
                envelope[:attack_samples] = np.linspace(0, 1, attack_samples)
            if release_samples > 0:
                envelope[-release_samples:] = np.linspace(1, 0, release_samples)
            
            note_audio = amplitude * np.sin(2 * np.pi * freq * t) * envelope
            
            # Add to audio (with clipping protection)
            audio[start_sample:end_sample] += note_audio
        
        # Normalize
        if np.max(np.abs(audio)) > 0:
            audio = audio / np.max(np.abs(audio))
        
        return audio
    
    def _compute_spectral_similarity(self,
                                     chroma1: np.ndarray,
                                     chroma2: np.ndarray) -> float:
        """
        Compute spectral similarity between two chromagrams.
        
        Args:
            chroma1: First chromagram
            chroma2: Second chromagram
            
        Returns:
            Similarity score (0-1, higher is better)
        """
        # Align lengths
        min_len = min(chroma1.shape[1], chroma2.shape[1])
        chroma1 = chroma1[:, :min_len]
        chroma2 = chroma2[:, :min_len]
        
        # Compute correlation for each frame
        correlations = []
        for i in range(min_len):
            # Cosine similarity
            sim = 1 - cosine(chroma1[:, i], chroma2[:, i])
            if not np.isnan(sim):
                correlations.append(sim)
        
        if len(correlations) == 0:
            return 0.0
        
        # Average correlation
        return np.mean(correlations)
    
    def _compute_onset_metrics(self,
                               audio_onsets: np.ndarray,
                               midi_onsets: np.ndarray,
                               tolerance: float = 0.05) -> Dict[str, float]:
        """
        Compute onset detection precision, recall, and F1 score.
        
        Args:
            audio_onsets: Ground truth onsets from audio
            midi_onsets: Detected onsets from MIDI
            tolerance: Time tolerance for matching (seconds)
            
        Returns:
            Dictionary with precision, recall, and F1 score
        """
        if len(midi_onsets) == 0:
            return {'onset_precision': 0.0, 'onset_recall': 0.0, 'onset_f1': 0.0}
        
        if len(audio_onsets) == 0:
            return {'onset_precision': 0.0, 'onset_recall': 0.0, 'onset_f1': 0.0}
        
        # Count true positives
        true_positives = 0
        matched_audio = set()
        
        for midi_onset in midi_onsets:
            # Find closest audio onset
            distances = np.abs(audio_onsets - midi_onset)
            min_dist_idx = np.argmin(distances)
            min_dist = distances[min_dist_idx]
            
            if min_dist <= tolerance and min_dist_idx not in matched_audio:
                true_positives += 1
                matched_audio.add(min_dist_idx)
        
        # Compute metrics
        precision = true_positives / len(midi_onsets) if len(midi_onsets) > 0 else 0
        recall = true_positives / len(audio_onsets) if len(audio_onsets) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        return {
            'onset_precision': precision,
            'onset_recall': recall,
            'onset_f1': f1
        }
    
    def _compute_temporal_coverage(self, 
                                   midi_file: mido.MidiFile,
                                   audio_duration: float) -> float:
        """
        Compute what proportion of the audio is covered by MIDI notes.
        
        Args:
            midi_file: MIDI file
            audio_duration: Total audio duration in seconds
            
        Returns:
            Coverage ratio (0-1)
        """
        # Extract all note intervals
        intervals = []
        
        for track in midi_file.tracks:
            time = 0
            active_notes = {}
            
            for msg in track:
                time += msg.time
                seconds = mido.tick2second(time, midi_file.ticks_per_beat, 500000)
                
                if msg.type == 'note_on' and msg.velocity > 0:
                    active_notes[msg.note] = seconds
                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    if msg.note in active_notes:
                        start = active_notes[msg.note]
                        intervals.append((start, seconds))
                        del active_notes[msg.note]
        
        if len(intervals) == 0:
            return 0.0
        
        # Merge overlapping intervals
        intervals.sort()
        merged = [intervals[0]]
        
        for start, end in intervals[1:]:
            if start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        
        # Compute total covered time
        covered_time = sum(end - start for start, end in merged)
        
        return min(covered_time / audio_duration, 1.0) if audio_duration > 0 else 0.0
    
    def _compute_pitch_distribution(self,
                                   y: np.ndarray,
                                   sr: int,
                                   midi_file: mido.MidiFile) -> float:
        """
        Compare pitch class distributions between audio and MIDI.
        
        Args:
            y: Audio signal
            sr: Sample rate
            midi_file: MIDI file
            
        Returns:
            Distribution similarity (0-1)
        """
        # Get audio pitch class distribution from chromagram
        audio_chroma = self._extract_chromagram(y, sr)
        audio_dist = np.mean(audio_chroma, axis=1)
        audio_dist = audio_dist / np.sum(audio_dist) if np.sum(audio_dist) > 0 else audio_dist
        
        # Get MIDI pitch class distribution
        pitch_counts = np.zeros(12)
        
        for track in midi_file.tracks:
            for msg in track:
                if msg.type == 'note_on' and msg.velocity > 0:
                    pitch_class = msg.note % 12
                    pitch_counts[pitch_class] += 1
        
        midi_dist = pitch_counts / np.sum(pitch_counts) if np.sum(pitch_counts) > 0 else pitch_counts
        
        # Compute similarity (1 - Jensen-Shannon divergence)
        if np.sum(audio_dist) > 0 and np.sum(midi_dist) > 0:
            similarity = 1 - cosine(audio_dist, midi_dist)
            return max(0, min(1, similarity))
        
        return 0.0
    
    def _compute_overall_score(self, metrics: Dict[str, float]) -> float:
        """
        Compute weighted overall quality score.
        
        Args:
            metrics: Dictionary of individual metrics
            
        Returns:
            Overall quality score (0-1)
        """
        weights = {
            'spectral_similarity': 0.3,
            'onset_f1': 0.3,
            'temporal_coverage': 0.2,
            'pitch_distribution': 0.2
        }
        
        score = 0.0
        total_weight = 0.0
        
        for metric, weight in weights.items():
            if metric in metrics:
                score += metrics[metric] * weight
                total_weight += weight
        
        return score / total_weight if total_weight > 0 else 0.0
    
    def _print_metrics(self, metrics: Dict[str, float]):
        """Print evaluation metrics in a readable format."""
        print("\n  ═══════════════════════════════════════════════")
        print("  📊 TRANSCRIPTION QUALITY EVALUATION")
        print("  ═══════════════════════════════════════════════")
        
        print(f"\n  🎵 Spectral Similarity:    {metrics['spectral_similarity']:.1%}")
        print(f"     (chromagram correlation with original audio)")
        
        print(f"\n  🎯 Onset Detection:")
        print(f"     Precision:  {metrics.get('onset_precision', 0):.1%}")
        print(f"     Recall:     {metrics.get('onset_recall', 0):.1%}")
        print(f"     F1 Score:   {metrics.get('onset_f1', 0):.1%}")
        
        print(f"\n  ⏱️  Temporal Coverage:     {metrics['temporal_coverage']:.1%}")
        print(f"     (proportion of audio covered by notes)")
        
        print(f"\n  🎼 Pitch Distribution:    {metrics['pitch_distribution']:.1%}")
        print(f"     (similarity of pitch class profiles)")
        
        print(f"\n  ⭐ OVERALL QUALITY:       {metrics['overall_quality']:.1%}")
        
        # Quality rating
        quality = metrics['overall_quality']
        if quality >= 0.8:
            rating = "Excellent ⭐⭐⭐⭐⭐"
        elif quality >= 0.6:
            rating = "Good ⭐⭐⭐⭐"
        elif quality >= 0.4:
            rating = "Fair ⭐⭐⭐"
        elif quality >= 0.2:
            rating = "Poor ⭐⭐"
        else:
            rating = "Very Poor ⭐"
        
        print(f"  Rating: {rating}")
        print("  ═══════════════════════════════════════════════\n")

