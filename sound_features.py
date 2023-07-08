import librosa
import numpy as np
import webrtcvad


def detect_voice_gender(audio_file):
    # Perform Harmonic-Percussive source separation
    signal, sr = librosa.load(audio_file, sr=None)
    harmonic, percussive = librosa.effects.hpss(y=signal)

    # Extract the pitch
    pitches, magnitudes = librosa.piptrack(y=harmonic, sr=sr)
    pitch = np.mean(pitches)

    threshold = 8.1
    print("pitch", pitch)
    if pitch > threshold:
        return {"female voice": float(pitch)}
    else:
        return {"male voice": float(pitch)}


def estimate_pitch_yin(audio_file):
    # Load the audio file.
    y, sr = librosa.load(audio_file)

    # Estimate the fundamental frequency using the YIN algorithm.
    yin_f0 = librosa.yin(y, fmin=50, fmax=300, sr=sr)

    # Get the median of the estimated frequencies as the fundamental frequency (pitch).
    fundamental_freq = np.median(yin_f0)

    return fundamental_freq


def measure_speech_clarity_mfcc(audio_file):
    # Load the audio file.
    y, sr = librosa.load(audio_file)

    spectral_contrast = librosa.feature.spectral_contrast(y=y, sr=sr)

    # Calculate speech clarity
    speech_clarity = spectral_contrast.mean()

    return speech_clarity


def estimate_tonality_hps(audio_file):
    # Load the audio file.
    y, sr = librosa.load(audio_file)

    # Compute the Harmonic Product Spectrum (HPS).
    D = librosa.stft(y)
    D_hps = np.copy(D)
    for i in range(2, 5):
        D_hps[i:, :] *= D[:-i, :]
    y_hps = librosa.istft(D_hps)

    # Perform pitch analysis using the YIN algorithm to estimate tonality.
    pitches = librosa.yin(y_hps, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'))

    # Filter out negative and zero values in the pitch estimates.
    positive_pitches = pitches[pitches > 0]

    # Check if positive_pitches is empty.
    if len(positive_pitches) == 0:
        return None

    # Get the median of the estimated pitches as the tonal pitch.
    tonal_pitch = np.median(positive_pitches)

    return tonal_pitch


def measure_energy_rms(audio_file):
   # Load the audio file.
   y, sr = librosa.load(audio_file)

   # Compute the root mean square (RMS) energy.
   energy_rms = np.sqrt(np.mean(y**2))

   return float(energy_rms)


def measure_silence_duration(audio_file, vad_mode=3):
    # Load the audio file.
    audio, sr = librosa.load(audio_file, sr=None)

    # Convert the audio to 16-bit PCM format expected by the VAD library.
    audio_int16 = (audio * 32768).astype(np.int16)

    # Initialize the Voice Activity Detector (VAD) with the desired mode.
    vad = webrtcvad.Vad(vad_mode)

    # Define the VAD frame duration and hop length.
    frame_duration = 30  # In milliseconds
    hop_length = int(sr * frame_duration / 1000)

    # Split the audio into frames and classify each frame as speech or non-speech.
    frames = [audio_int16[i:i + hop_length] for i in range(0, len(audio_int16), hop_length)]
    speech_flags = [vad.is_speech(frame.tobytes(), sr) for frame in frames]

    # Calculate the duration of silence.
    silence_duration = sum(1 for flag in speech_flags if not flag) * frame_duration / 1000

    return silence_duration


def detect_silence(audio_file, threshold_db=-40, frame_duration=30):
    # Load the audio file.
    audio, sr = librosa.load(audio_file, sr=None)

    # Calculate the frame duration in samples.
    frame_size = int(sr * frame_duration / 1000)

    # Split the audio into frames.
    audio_frames = [audio[i:i+frame_size] for i in range(0, len(audio), frame_size)]

    # Compute the energy of each frame.
    frame_energies = [np.sum(frame**2) for frame in audio_frames]

    # Convert the energy values to decibels (dB).
    frame_energies_db = 10 * np.log10(frame_energies)

    # Determine the frames classified as silence based on the energy threshold.
    silence_frames = [i for i, energy_db in enumerate(frame_energies_db) if energy_db <= threshold_db]

    # Calculate the duration and percentage of silence.
    audio_duration = len(audio) / sr
    silence_duration = len(silence_frames) * frame_duration / 1000
    print(silence_duration, audio_duration)
    silence_percentage = (silence_duration / audio_duration) * 100

    # Calculate the start and end time of each silence segment.
    silence_segments = []
    for frame_index in silence_frames:
        start_time = frame_index * frame_duration / 1000
        end_time = (frame_index + 1) * frame_duration / 1000
        silence_segments.append((start_time, end_time))

    return silence_duration, silence_percentage

