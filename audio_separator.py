"""
Audio Source Separation Module using Demucs

Isolates piano/keyboard tracks from mixed audio using Meta's Demucs model.
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path
import shutil


class AudioSeparator:
    """Separates piano/keyboard tracks from mixed audio using Demucs."""
    
    def __init__(self):
        """Initialize the audio separator."""
        self.demucs_available = self._check_demucs()
    
    def _check_demucs(self) -> bool:
        """Check if demucs is installed."""
        try:
            # Try importing demucs module
            import demucs
            # Check if av (PyAV) is also available for audio loading
            import av
            return True
        except ImportError:
            return False
    
    def separate_piano(self, audio_file: str, output_dir: str = None, 
                      verbose: bool = False) -> str:
        """
        Separate piano/keyboard from mixed audio.
        
        Args:
            audio_file: Path to input audio file
            output_dir: Directory for output (temp if None)
            verbose: Print progress information
            
        Returns:
            Path to the isolated piano track
        """
        if not self.demucs_available:
            if verbose:
                print("  Warning: Demucs not installed, skipping separation")
                print("  Install with: pip install demucs")
            return audio_file
        
        # Use temp directory if not specified
        if output_dir is None:
            output_dir = tempfile.gettempdir()
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        if verbose:
            print(f"  Separating audio sources with Demucs...")
            print(f"  This may take a few minutes for the first run (model download)...")
        
        # Run demucs using Python module
        # We'll use 'other' stem which typically contains piano/keyboards
        try:
            # Configure environment - av backend should be used automatically  
            env = os.environ.copy()
            
            cmd = [
                sys.executable,  # Use current Python interpreter
                '-m', 'demucs',
                '--two-stems=vocals',  # Splits into vocals and no_vocals (instruments)
                '-n', 'htdemucs',      # Use Hybrid Transformer model
                '--mp3',               # Output as MP3
                '--out', str(output_path),
                audio_file
            ]
            
            if verbose:
                print(f"  Running: {' '.join(cmd)}")
                result = subprocess.run(cmd, check=True, env=env)
            else:
                result = subprocess.run(cmd, check=True, 
                                      capture_output=True, 
                                      text=True,
                                      env=env)
            
            # Find the separated file
            # Demucs creates: output_dir/htdemucs/<filename>/no_vocals.{ext}
            input_name = Path(audio_file).stem
            separated_dir = output_path / 'htdemucs' / input_name
            
            # Try different extensions (mp3, wav, flac)
            for ext in ['mp3', 'wav', 'flac']:
                separated_path = separated_dir / f'no_vocals.{ext}'
                if separated_path.exists():
                    if verbose:
                        print(f"  ✓ Piano track isolated: {separated_path}")
                    return str(separated_path)
            
            # If not found, list what's actually there for debugging
            if verbose:
                if separated_dir.exists():
                    files = list(separated_dir.iterdir())
                    print(f"  Warning: Could not find no_vocals file")
                    print(f"  Files in {separated_dir}: {[f.name for f in files]}")
                else:
                    print(f"  Warning: Directory not found: {separated_dir}")
            return audio_file
                
        except subprocess.CalledProcessError as e:
            if verbose:
                print(f"  Warning: Demucs separation failed: {e}")
                print(f"  Using original audio file")
            return audio_file
        except Exception as e:
            if verbose:
                print(f"  Warning: Unexpected error during separation: {e}")
                print(f"  Using original audio file")
            return audio_file
    
    def cleanup_separation(self, separation_dir: str):
        """
        Clean up temporary separation files.
        
        Args:
            separation_dir: Directory containing separated files
        """
        try:
            sep_path = Path(separation_dir)
            if sep_path.exists() and sep_path.is_dir():
                # Remove the htdemucs subdirectory
                htdemucs_path = sep_path / 'htdemucs'
                if htdemucs_path.exists():
                    shutil.rmtree(htdemucs_path)
        except Exception:
            pass  # Fail silently on cleanup errors
    
    def install_instructions(self) -> str:
        """Get installation instructions for demucs."""
        return """
To enable automatic piano isolation from mixed audio, install Demucs:

    pip install demucs

Or update requirements.txt and reinstall:
    
    echo demucs >> requirements.txt
    pip install -r requirements.txt

Note: First run will download the model (~300MB)
        """.strip()

