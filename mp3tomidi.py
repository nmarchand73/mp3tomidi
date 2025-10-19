"""
MP3 to MIDI Converter with Hand Separation

A command-line tool that converts MP3 piano recordings to MIDI files
with separate left and right hand tracks.

Uses Spotify's basic-pitch for audio-to-MIDI transcription and a rule-based
algorithm for hand separation.
"""

import argparse
import os
import sys
import tempfile
from pathlib import Path

from transcribe import AudioTranscriber
from hand_separator import HandSeparator
from midi_corrector import MidiCorrector
from audio_separator import AudioSeparator
from motif_extractor_v2 import MusicalPhraseDetector
import mido


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description='Convert MP3 piano recordings to MIDI with separate left and right hand tracks',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.mp3
  %(prog)s input.mp3 -o output.mid
  %(prog)s input.mp3 -o output.mid --split-note 64 --verbose
  %(prog)s input.wav -o piano.mid --onset-threshold 0.6

Notes:
  - Input can be MP3, WAV, FLAC, or other audio formats
  - Output MIDI will have 2 tracks: Track 0 (Right Hand), Track 1 (Left Hand)
  - Default split point is MIDI note 60 (middle C)
        """
    )
    
    # Required arguments
    parser.add_argument(
        'input',
        help='Input audio file (MP3, WAV, FLAC, etc.)'
    )
    
    # Optional arguments
    parser.add_argument(
        '-o', '--output',
        help='Output MIDI file path (default: output/<input_name>.mid)',
        default=None
    )
    
    parser.add_argument(
        '--split-note',
        type=int,
        default=60,
        help='MIDI note number to use as split point between hands (default: 60 = middle C)'
    )
    
    parser.add_argument(
        '--hysteresis',
        type=int,
        default=5,
        help='Hysteresis in semitones to prevent rapid hand switching (default: 5)'
    )
    
    parser.add_argument(
        '--onset-threshold',
        type=float,
        default=0.5,
        help='Note onset detection threshold 0-1, higher = stricter (default: 0.5)'
    )
    
    parser.add_argument(
        '--frame-threshold',
        type=float,
        default=0.3,
        help='Note frame detection threshold 0-1, higher = stricter (default: 0.3)'
    )
    
    parser.add_argument(
        '--min-note-length',
        type=float,
        default=127.70,
        help='Minimum note length in milliseconds (default: 127.70)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    parser.add_argument(
        '--keep-temp',
        action='store_true',
        help='Keep temporary transcribed MIDI file (before hand separation)'
    )
    
    parser.add_argument(
        '--no-correction',
        action='store_true',
        help='Skip error correction (keep all transcribed notes)'
    )
    
    parser.add_argument(
        '--min-note-duration',
        type=float,
        default=100.0,
        help='Minimum note duration in milliseconds for error correction (default: 100)'
    )
    
    parser.add_argument(
        '--quantize',
        action='store_true',
        help='Apply rhythmic quantization to MIDI output (50%% strength)'
    )
    
    parser.add_argument(
        '--quantize-resolution',
        type=int,
        default=16,
        choices=[4, 8, 16, 32],
        help='Quantization resolution: 4=quarter notes, 8=8th, 16=16th (default: 16)'
    )
    
    parser.add_argument(
        '--min-velocity',
        type=int,
        default=15,
        help='Minimum note velocity for error correction (default: 15)'
    )
    
    parser.add_argument(
        '--no-separation',
        action='store_true',
        help='Skip audio source separation (use if input is already solo piano)'
    )
    
    parser.add_argument(
        '--extract-phrases',
        action='store_true',
        help='Extract musical phrases (8-20 notes) to separate MIDI files'
    )
    
    parser.add_argument(
        '--phrase-min-length',
        type=int,
        default=8,
        help='Minimum phrase length in notes (default: 8)'
    )
    
    parser.add_argument(
        '--phrase-max-length',
        type=int,
        default=20,
        help='Maximum phrase length in notes (default: 20)'
    )
    
    parser.add_argument(
        '--phrase-count',
        type=int,
        default=1,
        help='Number of top phrases to extract (default: 1)'
    )
    
    parser.add_argument(
        '--phrase-similarity',
        type=float,
        default=0.75,
        help='Similarity threshold for approximate matching 0-1 (default: 0.75)'
    )
    
    parser.add_argument(
        '--phrase-min-frequency',
        type=int,
        default=1,
        help='Minimum repetitions required for a phrase (default: 1)'
    )
    
    args = parser.parse_args()
    
    # Validate input file
    if not os.path.exists(args.input):
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    
    # Create output directory structure
    output_dir = Path("output")
    midi_dir = output_dir / "midi"
    phrases_dir = output_dir / "phrases"
    audio_dir = output_dir / "audio"
    
    midi_dir.mkdir(parents=True, exist_ok=True)
    phrases_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)
    
    # Determine output path
    if args.output is None:
        input_path = Path(args.input)
        args.output = midi_dir / f"{input_path.stem}.mid"
    else:
        args.output = Path(args.output)
        # Ensure output directory exists for custom paths
        args.output.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert to string for consistency
    args.output = str(args.output)
    
    if args.verbose:
        print("="*60)
        print("MP3 to MIDI Converter with Hand Separation")
        print("="*60)
        print(f"Input file: {args.input}")
        print(f"Output file: {args.output}")
        print(f"Split note: {args.split_note} (MIDI)")
        print(f"Hysteresis: {args.hysteresis} semitones")
        print(f"Onset threshold: {args.onset_threshold}")
        print(f"Frame threshold: {args.frame_threshold}")
        print("="*60)
    
    try:
        # Use temp directory for intermediate files
        temp_dir = tempfile.gettempdir()
        
        # Step 1: Separate piano from mixed audio (if needed)
        audio_to_transcribe = args.input
        separation_performed = False
        
        if not args.no_separation:
            print("\n[1/5] Separating piano from audio...")
            separator = AudioSeparator()
            
            if separator.demucs_available:
                audio_to_transcribe = separator.separate_piano(
                    audio_file=args.input,
                    output_dir=str(audio_dir),
                    verbose=args.verbose
                )
                separation_performed = (audio_to_transcribe != args.input)
            else:
                if args.verbose:
                    print("  Demucs not installed - skipping separation")
                    print("  Install with: pip install demucs")
                print("  Proceeding with original audio (assuming solo piano)")
        else:
            if args.verbose:
                print("\n[1/5] Skipping audio separation (--no-separation flag)")
        
        # Step 2: Transcribe audio to MIDI
        print(f"\n[2/5] Transcribing audio to MIDI...")
        transcriber = AudioTranscriber()
        
        transcribed_midi_path = transcriber.transcribe(
            audio_file=audio_to_transcribe,
            output_dir=temp_dir,
            onset_threshold=args.onset_threshold,
            frame_threshold=args.frame_threshold,
            minimum_note_length=args.min_note_length
        )
        
        if args.verbose:
            midi_file = mido.MidiFile(transcribed_midi_path)
            info = transcriber.get_midi_info(midi_file)
            print(f"  - Transcribed {info['total_notes']} notes")
            print(f"  - Pitch range: {info['pitch_range'][0]} - {info['pitch_range'][1]}")
            print(f"  - Ticks per beat: {info['ticks_per_beat']}")
        
        # Step 3: Error correction
        transcribed_midi = mido.MidiFile(transcribed_midi_path)
        
        if not args.no_correction:
            print("\n[3/5] Correcting errors...")
            corrector = MidiCorrector(
                min_note_duration_ms=args.min_note_duration,
                min_velocity=args.min_velocity,
                quantize=args.quantize,
                quantize_resolution=args.quantize_resolution
            )
            transcribed_midi = corrector.correct(transcribed_midi, verbose=args.verbose)
        else:
            if args.verbose:
                print("\n[3/5] Skipping error correction...")
        
        # Step 4: Separate hands
        print("\n[4/5] Separating left and right hand parts...")
        hand_separator = HandSeparator(
            split_note=args.split_note,
            hysteresis=args.hysteresis
        )
        
        # Perform hand separation
        separated_midi = hand_separator.separate(transcribed_midi)
        
        if args.verbose:
            # Count notes in each track
            right_notes = 0
            left_notes = 0
            for i, track in enumerate(separated_midi.tracks):
                note_count = sum(1 for msg in track if msg.type == 'note_on' and msg.velocity > 0)
                if i == 0:
                    right_notes = note_count
                elif i == 1:
                    left_notes = note_count
            print(f"  - Right hand: {right_notes} notes")
            print(f"  - Left hand: {left_notes} notes")
        
        # Step 5: Extract musical phrases (optional)
        if args.extract_phrases:
            print(f"\n[5/6] Extracting top {args.phrase_count} musical phrase(s)...")
            detector = MusicalPhraseDetector(
                min_phrase_length=args.phrase_min_length,
                max_phrase_length=args.phrase_max_length,
                min_frequency=args.phrase_min_frequency,
                similarity_threshold=args.phrase_similarity
            )
            
            # Create phrase output path in phrases subfolder
            output_path_obj = Path(args.output)
            phrases_dir = output_path_obj.parent.parent / "phrases"
            phrases_dir.mkdir(parents=True, exist_ok=True)
            phrase_output = phrases_dir / f"{output_path_obj.stem}_phrase.mid"
            
            # Extract phrases from the corrected MIDI (before hand separation)
            phrase_results = detector.extract(
                transcribed_midi, 
                str(phrase_output), 
                verbose=args.verbose,
                top_n=args.phrase_count
            )
        
        # Step 6: Save output
        step_num = "6/6" if args.extract_phrases else "5/5"
        print(f"\n[{step_num}] Saving output MIDI file...")
        separated_midi.save(args.output)
        
        if args.verbose:
            print(f"  - Saved to: {args.output}")
        
        # Clean up temp files unless requested to keep
        if not args.keep_temp:
            try:
                os.remove(transcribed_midi_path)
            except:
                pass
            
            # Clean up separation files if we performed separation
            if separation_performed and not args.no_separation:
                try:
                    AudioSeparator().cleanup_separation(temp_dir)
                except:
                    pass
        else:
            temp_output = f"{Path(args.output).stem}_transcribed.mid"
            os.rename(transcribed_midi_path, temp_output)
            if args.verbose:
                print(f"  - Intermediate MIDI saved to: {temp_output}")
        
        print(f"\n✓ Conversion complete! Output saved to: {args.output}")
        print(f"  Track 0: Right Hand")
        print(f"  Track 1: Left Hand")
        
        if args.extract_phrases and phrase_results:
            print(f"\n✓ Extracted {len(phrase_results)} musical phrase(s):")
            for result in phrase_results:
                print(f"  #{result['rank']}: {result['file']} "
                      f"(score: {result['score']:.1f}, {result['frequency']}x, {result['length']} notes)")
        elif args.extract_phrases:
            print(f"\n⚠ No significant musical phrases found")
        
    except Exception as e:
        print(f"\n✗ Error: {str(e)}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

