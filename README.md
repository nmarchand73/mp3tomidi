# MP3 to MIDI Piano Converter

Convert piano recordings (MP3, WAV) to MIDI files with automatic left/right hand separation.

## ✅ Ready to Use!

Python 3.11 environment is already set up in your Conda installation.

## Usage

### Easy Way (using batch script)
```powershell
.\RUN.bat "input\A Forest.mp3" --verbose
```

### Direct Way
```powershell
C:\Users\nmarc\miniconda3\envs\mp3tomidi\python.exe mp3tomidi.py "input\A Forest.mp3" --verbose
```

### Basic Command
```powershell
C:\Users\nmarc\miniconda3\envs\mp3tomidi\python.exe mp3tomidi.py input.mp3
```
Creates `output/input_separated.mid` with 2 tracks (right hand + left hand).

## Common Adjustments

### Custom Output Location
```powershell
.\RUN.bat input.mp3 -o myfile.mid      # Save to specific file
```

### Change Split Point
Default is middle C (MIDI note 60). Adjust for different ranges:
```powershell
.\RUN.bat input.mp3 --split-note 64    # Higher split
.\RUN.bat input.mp3 --split-note 55    # Lower split
```

### Stricter Note Detection
Reduce false notes:
```powershell
.\RUN.bat input.mp3 --onset-threshold 0.7
```

### More Sensitive Detection
Catch quieter notes:
```powershell
.\RUN.bat input.mp3 --onset-threshold 0.3
```

## All Options

```
.\RUN.bat --help
```

| Option | Description | Default |
|--------|-------------|---------|
| `--split-note` | MIDI note for hand split | 60 (middle C) |
| `--hysteresis` | Prevents rapid hand switching | 5 semitones |
| `--onset-threshold` | Note detection (0-1, higher=stricter) | 0.5 |
| `--frame-threshold` | Duration detection (0-1) | 0.3 |
| `--verbose` | Show detailed progress | off |
| `--keep-temp` | Keep intermediate files | off |

## Output

MIDI file with 2 tracks:
- **Track 0**: Right Hand (502 notes in example)
- **Track 1**: Left Hand (540 notes in example)

Opens in any DAW or notation software (MuseScore, FL Studio, Ableton, Sibelius, etc.)

## Tips

✓ Use clear, solo piano recordings  
✓ Start with defaults, adjust only if needed  
✓ Processing time ≈ 1-2x audio length  
✓ Expected accuracy: ~85% transcription, ~70% hand separation  

## Test Results

Sample conversion of "A Forest.mp3":
- **Transcribed**: 1042 notes (pitch range: MIDI 33-81)
- **Right hand**: 502 notes
- **Left hand**: 540 notes
- **Processing time**: ~15 seconds

## Technology

- **Transcription**: Spotify's basic-pitch (state-of-the-art neural network)
- **Hand Separation**: Rule-based algorithm with pitch clustering and voice leading
- **Environment**: Python 3.11 with TensorFlow 2.15

## Setup (Already Done!)

Your system is already configured with:
- ✅ Python 3.11 in Conda environment: `mp3tomidi`
- ✅ All dependencies installed (basic-pitch, tensorflow, mido, librosa, soundfile)
- ✅ `RUN.bat` script for easy execution

## For Other Systems

If you need to set this up on another computer:

```powershell
# Install Miniconda, then:
conda create -n mp3tomidi python=3.11 -y
conda activate mp3tomidi
pip install basic-pitch mido librosa soundfile
```

## Troubleshooting

**"ModuleNotFoundError"**
- Re-run: `conda activate mp3tomidi` then retry

**Wrong hand assignments**
```powershell
.\RUN.bat input.mp3 --split-note 62 --hysteresis 7
```

**Too many false notes**
```powershell
.\RUN.bat input.mp3 --onset-threshold 0.6
```

**Environment issues**
```powershell
# Recreate environment
conda remove -n mp3tomidi --all -y
conda create -n mp3tomidi python=3.11 -y
C:\Users\nmarc\miniconda3\envs\mp3tomidi\python.exe -m pip install basic-pitch mido librosa soundfile
```
