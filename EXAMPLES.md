# Usage Examples

## Basic Usage

### Convert Mixed Audio (with vocals, drums, etc.)
```bash
# Automatically isolates piano and converts to MIDI
python mp3tomidi.py "song_with_vocals.mp3" --verbose
```

**What happens:**
1. Demucs separates piano from other instruments (~4-6 min for 4 min song)
2. Basic-Pitch transcribes the isolated piano (~2 min)
3. Error correction removes artifacts
4. Hand separation creates left/right hand tracks
5. Output saved to `output/song_with_vocals.mid`

### Convert Solo Piano (faster)
```bash
# Skip separation step for pure piano recordings
python mp3tomidi.py "solo_piano.mp3" --no-separation
```

**What happens:**
1. Skips Demucs separation (saves time)
2. Directly transcribes the audio (~15 sec for 1 min song)
3. Error correction and hand separation
4. Output saved to `output/solo_piano.mid`

## Real-World Examples

### Example 1: Piano Cover with Vocals
```bash
python mp3tomidi.py "Bohemian_Rhapsody_piano_cover.mp3" --verbose

# Expected results:
# - Separation: 3-5 minutes
# - Transcription: 1-2 minutes
# - Output: Clean piano MIDI with left/right hands
```

### Example 2: Soundtrack with Orchestra
```bash
python mp3tomidi.py "Westworld_Theme.mp3" --verbose

# The tool will:
# - Isolate piano/keys from orchestral elements
# - Extract ~1000-2000 notes depending on complexity
# - Create separated hand tracks
```

### Example 3: Pop Song with Piano Part
```bash
python mp3tomidi.py "Let_It_Be.mp3" --verbose

# Works best when:
# - Piano is clearly audible in the mix
# - Not too much reverb/effects
# - Piano plays throughout (not just intro/outro)
```

### Example 4: Classical Piano Solo
```bash
python mp3tomidi.py "Chopin_Nocturne.mp3" --no-separation --verbose

# Use --no-separation for:
# - Solo piano recordings
# - 3-5x faster processing
# - When audio is already clean
```

## Advanced Options

### Fine-Tune Transcription Sensitivity
```bash
# More strict (fewer false notes, might miss quiet notes)
python mp3tomidi.py input.mp3 --onset-threshold 0.7 --frame-threshold 0.5

# More sensitive (catch more notes, might add false positives)
python mp3tomidi.py input.mp3 --onset-threshold 0.3 --frame-threshold 0.2
```

### Adjust Hand Split Point
```bash
# Higher split (more notes in right hand)
python mp3tomidi.py input.mp3 --split-note 65 --hysteresis 7

# Lower split (more notes in left hand)
python mp3tomidi.py input.mp3 --split-note 55 --hysteresis 3
```

### Custom Error Correction
```bash
# Stricter filtering (remove more suspicious notes)
python mp3tomidi.py input.mp3 --min-note-duration 100 --min-velocity 25

# More lenient (keep more notes, including artifacts)
python mp3tomidi.py input.mp3 --no-correction
```

### Combine Multiple Options
```bash
python mp3tomidi.py "My_Song.mp3" \
    --verbose \
    --onset-threshold 0.6 \
    --split-note 62 \
    --min-note-duration 75 \
    --output "custom_output/my_song.mid"
```

## Batch Processing

### Process Multiple Files
```powershell
# PowerShell
Get-ChildItem input\*.mp3 | ForEach-Object {
    python mp3tomidi.py $_.FullName --verbose
}
```

```bash
# Linux/Mac
for file in input/*.mp3; do
    python mp3tomidi.py "$file" --verbose
done
```

## Tips for Best Results

### ✅ Good Use Cases
- Piano covers of popular songs
- Movie/game soundtracks with piano
- Pop/rock songs with clear piano parts
- Jazz standards with piano
- Classical piano solos
- Piano-driven ballads

### ⚠️ Challenging Cases
- Heavy distortion or effects on piano
- Multiple keyboards playing simultaneously
- Very quiet piano buried in dense mix
- Synthesized/electronic piano sounds
- Extreme tempo changes or rubato

### 🎯 Optimization Tips

**For Mixed Audio:**
- Use `--verbose` to monitor separation progress
- First run downloads model (~80MB)
- Processing time ≈ 1.5x audio length
- Piano should be clearly audible in original

**For Solo Piano:**
- Always use `--no-separation` flag
- Processing time ≈ 0.5x audio length
- Much faster, same quality
- Best for pure piano recordings

**For Transcription Quality:**
- Higher `--onset-threshold` (0.6-0.8) for cleaner results
- Lower `--onset-threshold` (0.3-0.4) to catch soft notes
- Adjust `--min-note-duration` to filter out artifacts
- Use `--min-velocity` to remove ghost notes

**For Hand Separation:**
- Default split at Middle C (60) works for most music
- Raise `--split-note` (65-70) for higher-register pieces
- Lower `--split-note` (50-55) for bass-heavy pieces
- Increase `--hysteresis` (7-10) to reduce hand switching

## Troubleshooting

### Issue: Separation takes too long
```bash
# Solution: Use --no-separation if input is already solo piano
python mp3tomidi.py input.mp3 --no-separation
```

### Issue: Too many wrong notes
```bash
# Solution: Increase onset threshold and minimum duration
python mp3tomidi.py input.mp3 --onset-threshold 0.7 --min-note-duration 100
```

### Issue: Missing quiet notes
```bash
# Solution: Decrease thresholds
python mp3tomidi.py input.mp3 --onset-threshold 0.3 --min-velocity 10
```

### Issue: Poor hand separation
```bash
# Solution: Adjust split point and hysteresis
python mp3tomidi.py input.mp3 --split-note 58 --hysteresis 7
```

### Issue: Demucs not working
```bash
# Solution: Check installation
pip install --upgrade demucs torch==2.5.1 torchaudio==2.5.1 av

# Or skip separation
python mp3tomidi.py input.mp3 --no-separation
```

## Performance Benchmarks

| Audio Type | Length | Separation | Transcription | Total | Notes |
|------------|--------|------------|---------------|-------|-------|
| Solo Piano | 1:15 | 0s (skipped) | 15s | ~15s | 1042 |
| Piano + Vocals | 4:02 | 4min | 2min | ~6min | 2349 |
| Full Band | 3:30 | 3.5min | 1.5min | ~5min | ~1800 |
| Orchestral | 5:00 | 5min | 2.5min | ~7.5min | ~2500 |

*Times are approximate and vary based on system performance*

