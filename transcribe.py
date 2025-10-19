"""
Transcription Module using Spotify's basic-pitch

Converts audio files (MP3, WAV, etc.) to MIDI using the basic-pitch library.
"""

import os
import tempfile
from pathlib import Path
from basic_pitch.inference import predict_and_save
from basic_pitch import ICASSP_2022_MODEL_PATH
import mido


class AudioTranscriber:
    """Transcribes audio files to MIDI using basic-pitch."""
    
    def __init__(self, model_path: str = ICASSP_2022_MODEL_PATH):
        """
        Initialize the transcriber.
        
        Args:
            model_path: Path to the basic-pitch model (uses default if not specified)
        """
        self.model_path = model_path
    
    def transcribe(self, audio_file: str, output_dir: str = None, 
                  onset_threshold: float = 0.5, 
                  frame_threshold: float = 0.3,
                  minimum_note_length: float = 127.70,
                  minimum_frequency: float = None,
                  maximum_frequency: float = None,
                  melodia_trick: bool = True) -> str:
        """
        Transcribe an audio file to MIDI.
        
        Args:
            audio_file: Path to input audio file (MP3, WAV, etc.)
            output_dir: Directory for output MIDI file (temp dir if None)
            onset_threshold: Threshold for note onset detection (0-1, higher = stricter)
            frame_threshold: Threshold for note frame detection (0-1, higher = stricter)
            minimum_note_length: Minimum note length in milliseconds
            minimum_frequency: Minimum frequency in Hz (None = no limit)
            maximum_frequency: Maximum frequency in Hz (None = no limit)
            melodia_trick: Whether to use melodia trick (helps with pitch accuracy)
            
        Returns:
            Path to the generated MIDI file
        """
        # Validate input file
        if not os.path.exists(audio_file):
            raise FileNotFoundError(f"Audio file not found: {audio_file}")
        
        # Set up output directory
        if output_dir is None:
            output_dir = tempfile.gettempdir()
        else:
            os.makedirs(output_dir, exist_ok=True)
        
        # Get the base name without extension
        audio_path = Path(audio_file)
        base_name = audio_path.stem
        
        print(f"Transcribing {audio_file}...")
        print(f"This may take a few minutes depending on the length of the audio...")
        
        # Perform transcription
        # basic-pitch will create files with _basic_pitch suffix
        try:
            predict_and_save(
                audio_path_list=[audio_file],
                output_directory=output_dir,
                save_midi=True,
                sonify_midi=False,
                save_model_outputs=False,
                save_notes=False,
                model_or_model_path=self.model_path,
                onset_threshold=onset_threshold,
                frame_threshold=frame_threshold,
                minimum_note_length=minimum_note_length,
                minimum_frequency=minimum_frequency,
                maximum_frequency=maximum_frequency,
                melodia_trick=melodia_trick
            )
            
            # The output file will be named: {base_name}_basic_pitch.mid
            output_midi_path = os.path.join(output_dir, f"{base_name}_basic_pitch.mid")
            
            if not os.path.exists(output_midi_path):
                raise RuntimeError(f"MIDI file was not created at expected path: {output_midi_path}")
            
            print(f"Transcription complete! MIDI file created at: {output_midi_path}")
            
            return output_midi_path
            
        except Exception as e:
            raise RuntimeError(f"Transcription failed: {str(e)}")
    
    def load_midi(self, midi_file: str) -> mido.MidiFile:
        """
        Load a MIDI file.
        
        Args:
            midi_file: Path to MIDI file
            
        Returns:
            Loaded MIDI file object
        """
        return mido.MidiFile(midi_file)
    
    def get_midi_info(self, midi_file: mido.MidiFile) -> dict:
        """
        Get information about a MIDI file.
        
        Args:
            midi_file: MIDI file object
            
        Returns:
            Dictionary with MIDI file information
        """
        total_notes = 0
        min_pitch = 127
        max_pitch = 0
        
        for track in midi_file.tracks:
            for msg in track:
                if msg.type == 'note_on' and msg.velocity > 0:
                    total_notes += 1
                    min_pitch = min(min_pitch, msg.note)
                    max_pitch = max(max_pitch, msg.note)
        
        return {
            'ticks_per_beat': midi_file.ticks_per_beat,
            'num_tracks': len(midi_file.tracks),
            'total_notes': total_notes,
            'pitch_range': (min_pitch, max_pitch) if total_notes > 0 else (0, 0)
        }

