# Motif Extraction Algorithm Improvements

## Research Summary

Based on research into state-of-the-art pattern recognition in Music Information Retrieval (MIR), the following improvements were implemented:

### Key Research Findings

1. **Point-Set Pattern Matching** (Microsoft Research)
   - Treats music as multidimensional points rather than linear sequences
   - More effective for polyphonic music
   - O(n²) time for pattern discovery

2. **Dynamic Time Warping (DTW)**
   - Handles tempo variations and expressive timing
   - Allows approximate matching of patterns
   - Tempo-invariant pattern recognition

3. **Edit Distance / Levenshtein Distance**
   - Measures similarity between melodic sequences
   - Allows finding "similar" patterns, not just exact matches
   - Groups related motifs together

4. **Vector Representations**
   - Efficient similarity searches using cosine similarity
   - Fast pre-filtering before detailed comparison
   - Used in systems like Shazam

5. **Musical Significance Scoring**
   - Combines multiple factors: frequency, length, melodic contour, rhythm
   - Identifies musically interesting patterns, not just repeated notes
   - Penalizes trivial patterns (repeated single notes, extreme registers)

## Improvements Implemented

### Version 2: EnhancedMotifExtractor

**New Features:**
1. **Advanced Pattern Recognition**
   - Uses interval sequences (transposition-invariant)
   - Normalizes rhythm patterns (tempo-invariant)
   - Groups approximate matches using edit distance

2. **Multi-Factor Scoring System**
   - **Frequency**: How often pattern repeats (logarithmic scaling)
   - **Length**: Optimal around 8 notes
   - **Melodic Interest**: Prefers 70% stepwise motion, 30% leaps
   - **Rhythmic Variety**: Rewards diverse rhythms
   - **Pitch Range**: Favors patterns with melodic range
   - **Register Penalty**: Penalizes extreme low/high pitches

3. **Approximate Matching**
   - Finds similar patterns with variations
   - Configurable similarity threshold (default 80%)
   - Groups transposed and slightly varied patterns

4. **Top-N Extraction**
   - Can extract multiple best motifs, not just one
   - Ranked by combined musical significance score
   - Avoids extracting trivial repeated notes

5. **Enhanced Data Structure**
   - `Note` dataclass with precise timing
   - `Motif` dataclass with rich metadata
   - Tracks pattern type (exact vs approximate)
   - Stores occurrence locations

## Algorithm Comparison

### Original Algorithm (v1)
- Simple interval + rhythm pattern matching
- Exact matches only
- Counts frequency, returns most common
- Found: "A1 A1 A1" (repeated bass note)

### Enhanced Algorithm (v2)
- Multi-dimensional pattern analysis
- Approximate matching with edit distance
- Weighted scoring system
- Finds: Musically significant melodic motifs

## Technical Details

### Pattern Representation
```python
# Old: Simple tuple
pattern = (pitch_intervals, rhythm_pattern, start_pitch)

# New: Rich data structure
@dataclass
class Motif:
    notes: List[Note]          # Full note information
    frequency: int             # Times repeated
    occurrences: List[int]     # Where it appears
    score: float              # Musical significance
    pattern_type: str         # exact/approximate
```

### Scoring Formula
```
score = frequency_score (log-scaled)
      + length_score (optimal ~8 notes)
      + melodic_score (prefers 70% steps)
      + rhythm_score (variety bonus)
      + range_score (octave normalized)
      - pitch_penalty (extreme registers)
```

### Approximate Matching
```python
similarity = 1 - (edit_distance / pattern_length)
if similarity >= threshold:  # default 0.8
    group_patterns_together()
```

## New Command-Line Options

```bash
# Extract top 3 motifs
python mp3tomidi.py input.mp3 --extract-motif --motif-count 3

# Adjust similarity threshold
python mp3tomidi.py input.mp3 --extract-motif --motif-similarity 0.9

# Customize length range
python mp3tomidi.py input.mp3 --extract-motif \
    --motif-min-length 4 \
    --motif-max-length 16
```

## Benefits

1. **More Meaningful Results**
   - Identifies actual musical themes, not just repeated notes
   - Finds melodically interesting patterns
   - Considers musical context

2. **Robustness**
   - Handles transpositions automatically
   - Groups similar patterns together
   - Works with approximate matches

3. **Flexibility**
   - Extract multiple motifs
   - Adjustable parameters
   - Detailed scoring information

4. **Performance**
   - Efficient pattern matching
   - Scales to longer pieces
   - O(n²) complexity for pattern discovery

## Future Enhancements

Possible improvements based on research:

1. **Dynamic Time Warping (DTW)**
   - Full DTW implementation for temporal flexibility
   - Handle rubato and tempo changes

2. **Geometric Hashing**
   - Faster similarity searches
   - Better for large corpus analysis

3. **Machine Learning**
   - LSTM/CNN for pattern learning
   - Train on labeled datasets of musical themes

4. **Contour Matching**
   - Melodic contour similarity
   - Shape-based pattern recognition

5. **Harmonic Context**
   - Consider chord progressions
   - Harmonic function analysis

## References

- Microsoft Research: "Algorithms for Discovering Repeated Patterns in Music"
- Dynamic Time Warping for melody detection
- Edit distance algorithms in bioinformatics adapted for music
- Geometric hashing for symbolic fingerprinting
- Music21 pattern recognition techniques

