# MP3 to MIDI Piano Converter

Convert piano recordings (MP3, WAV) to MIDI files with automatic left/right hand separation and chord progression analysis.

**✨ NEW Features:**
- **Chord Detection:** Automatically analyzes and generates chord progressions
- **Mixed Audio Support:** Isolates piano from songs with vocals, drums, and other instruments

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
Creates `output/midi/input.mid` with 2 tracks (right hand + left hand).
Separated audio is saved to `output/audio/` (piano only).

**Note:** First run will download AI models (~80MB for Demucs). Audio separation adds ~1-2 minutes per minute of audio. Use `--no-separation` for solo piano recordings (faster).

## Common Adjustments

### Custom Output Location
```powershell
.\RUN.bat input.mp3 -o myfile.mid      # Save to specific file
```

### Extract Repeated Musical Phrases
```powershell
# Extract single best phrase
.\RUN.bat input.mp3 --extract-phrases --verbose

# Extract top 3 phrases
.\RUN.bat input.mp3 --extract-phrases --phrase-count 3 --verbose
# Creates: output/midi/input.mid + output/phrases/input_phrase_phrase1.mid, phrase2.mid, phrase3.mid
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

### Skip Quality Evaluation
Quality evaluation runs by default. To skip it for faster processing:
```powershell
.\RUN.bat input.mp3 --no-quality-eval
```
Saves ~10 seconds per file.

### Skip Hand Separation
Keep all notes in one track:
```powershell
.\RUN.bat input.mp3 --no-hand-separation
```

## All Options

```
.\RUN.bat --help
```

### Transcription Options
| Option | Description | Default |
|--------|-------------|---------|
| `--onset-threshold` | Note detection (0-1, higher=stricter) | 0.5 |
| `--frame-threshold` | Duration detection (0-1) | 0.3 |

### Source Separation Options  
| Option | Description | Default |
|--------|-------------|---------|
| `--no-separation` | Skip audio separation (for solo piano) | off |

### Musical Phrase Detection Options
| Option | Description | Default |
|--------|-------------|---------|
| `--extract-phrases` | Extract repeated musical phrases | off |
| `--phrase-count` | Number of top phrases to extract | 1 |
| `--phrase-min-length` | Minimum notes in phrase | 8 |
| `--phrase-max-length` | Maximum notes in phrase | 20 |
| `--phrase-min-frequency` | Minimum repetitions required | 1 |
| `--phrase-similarity` | Similarity threshold for matching (0-1) | 0.75 |

### Error Correction Options
| Option | Description | Default |
|--------|-------------|---------|
| `--no-correction` | Skip error correction | off |
| `--min-note-duration` | Min note length in ms | 120 |
| `--min-velocity` | Min note velocity (0-127) | 15 |
| `--no-quantize` | Disable rhythmic quantization | off (quantize ON) |
| `--quantize-resolution` | Quantization: 4/8/16/32 notes | 16 |
| `--no-merge` | Disable note merging (legato) | off (merge ON) |
| `--merge-threshold` | Max gap for merging (ms) | 50 |

### Hand Separation Options
| Option | Description | Default |
|--------|-------------|---------|
| `--split-note` | MIDI note for hand split | 60 (middle C) |
| `--hysteresis` | Prevents rapid hand switching | 5 semitones |
| `--no-hand-separation` | Keep all notes in single track | off (separation ON) |

### Chord Detection Options
| Option | Description | Default |
|--------|-------------|---------|
| `--no-chord-detection` | Skip chord analysis | off (detection ON) |
| `--show-chords` | Display full chord progression | off (summary only) |
| `--chord-voicing` | Chord MIDI style: block\|arpeggio\|broken | block |
| `--chord-quantize` | Time grid in beats | 1.0 (quarter note) |

### General Options
| Option | Description | Default |
|--------|-------------|---------|
| `-v, --verbose` | Show detailed progress | off |
| `--keep-temp` | Keep intermediate files | off |
| `--no-quality-eval` | Skip quality evaluation | off (evaluation ON) |

## Output

### Main MIDI File
- **Track 0**: Right Hand (e.g., 234 notes)
- **Track 1**: Left Hand (e.g., 292 notes)

### Chord Files (generated automatically)
- **output/midi/chords/song_chords.mid**: Simplified chord progression MIDI
- **output/midi/chords/song_chords.txt**: Text chord chart

Opens in any DAW or notation software (MuseScore, FL Studio, Ableton, Sibelius, etc.)

## Tips

✓ **Works with mixed audio!** Automatically isolates piano from vocals/drums/other instruments  
✓ For solo piano recordings, use `--no-separation` to skip separation (faster)  
✓ First run downloads models: Demucs (~80MB) + Basic-Pitch (auto)  
✓ Processing time: ~1.5x audio length with separation, ~0.5x without  
✓ Expected accuracy: ~85% transcription, ~70% hand separation  
✓ Best results with clear piano parts (covers, soundtracks, pop songs with piano)  
✓ Start with defaults, adjust only if results need refinement  

## Test Results

### Solo Piano - "A Forest.mp3" (1:15)
- **Transcribed**: 1042 notes (MIDI 33-81)
- **Detected key**: D# minor
- **Error correction**: 0 notes removed
- **Out-of-key**: 772 notes (74.1% - typical for chromatic music)
- **Right hand**: 449 notes | **Left hand**: 454 notes
- **Time**: ~15 seconds (with `--no-separation`)

### Mixed Audio - "Paint It Black - Westworld Soundtrack.mp3" (4:02)
- **Separation**: ✓ Successfully isolated piano from vocals/drums
- **Transcribed**: 2349 notes (MIDI 24-88) from separated track
- **Detected key**: G# minor
- **Out-of-key**: 947 notes (40.3%)
- **Right hand**: 898 notes | **Left hand**: 1082 notes
- **Time**: ~6 minutes (4 min separation + 2 min transcription)

## Features

### 🎼 Audio Source Separation (NEW!)
- **Automatic piano isolation** using Meta's Demucs (HTDemucs model)
- Works with **mixed audio** (vocals, drums, other instruments)
- Extracts piano/keyboard tracks before transcription
- Optional - can be skipped for solo piano recordings

### 🎵 Audio Transcription
- Spotify's basic-pitch neural network (~85-90% accuracy)
- Polyphonic piano transcription
- Configurable sensitivity

### 📊 Quality Evaluation (NEW! - RUNS BY DEFAULT)
- **Onset F1 Score**: Note timing accuracy (MIREX standard)
- **Pitch Accuracy**: Pitch correctness with tolerance window
- **Spectral Similarity**: Chromagram correlation with original audio
- **Polyphony Score**: Simultaneous note count comparison
- **Rhythmic Precision**: Inter-onset interval analysis
- **Overall Quality**: Weighted score (0-100%) with rating (Excellent/Good/Fair/Poor)
- **Automatic**: Runs on every transcription, displays quality report
- **Optional**: Use `--no-quality-eval` to skip (saves ~10s)

### ✨ Enhanced Error Correction (NEW!)
- **Smart duration handling**: Removes only very short notes (<50ms), extends short notes (50-120ms)
- **Automatic tempo detection**: Uses actual MIDI tempo for accurate calculations
- **Rhythmic quantization**: 50% strength by default (preserves natural feel)
- **Velocity filtering**: Removes very quiet notes (< velocity 15)
- **Range filtering**: Removes notes outside piano range (A0-C8)
- **Key detection**: Automatically detects musical key using Krumhansl-Schmuckler algorithm
- **Out-of-key flagging**: Identifies suspicious notes outside the detected scale

### 🤝 Hand Separation
- Rule-based algorithm with pitch clustering
- Voice leading principles
- Configurable split point and hysteresis

### 🎼 Musical Phrase Detection (NEW!)
- **Identifies melodic phrases** (8-20 notes) automatically
- **Musical statements**: detects meaningful phrases spanning 1-2 bars
- **Smart scoring**: frequency + length + melodic interest + rhythm
- **Approximate matching**: finds similar phrases with variations (edit distance)
- **Transposition-invariant**: uses interval sequences, works in any key
- **Top-N extraction**: can find multiple best phrases, ranked by score
- **Flexible detection**: finds both repeated and unique significant phrases
- Exports phrases as separate MIDI files
- Useful for finding themes, melodies, and musical ideas

## Technology

- **Source Separation**: Meta's Demucs (HTDemucs - Hybrid Transformer model)
- **Transcription**: Spotify's basic-pitch (state-of-the-art neural network)
- **Error Correction**: Krumhansl-Schmuckler key detection + statistical filtering + note merging
- **Hand Separation**: Rule-based algorithm with pitch clustering and voice leading
- **Environment**: Python 3.11 with TensorFlow 2.15 + PyTorch 2.5.1

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
