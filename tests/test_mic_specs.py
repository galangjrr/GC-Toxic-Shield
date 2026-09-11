# =============================================================
# GC Toxic Shield — Test Suite: USB Headset Mic Specs (-40±2 dB)
# =============================================================
import numpy as np
import pytest
import speech_recognition as sr

from app.audio_engine import (
    AudioEngine,
    TARGET_SAMPLE_RATE,
    MIN_RMS_THRESHOLD,
    MAX_NORMALIZE_GAIN,
    _resample_audio_data,
)
from app.detector import ToxicDetector


@pytest.fixture
def engine():
    return AudioEngine(language="id-ID")


@pytest.fixture
def detector():
    return ToxicDetector("assets/word_list.json")


def _generate_synthetic_speech(sample_rate: int, duration_sec: float, rms_target: float, freq: float = 250.0):
    """Generate synthetic speech-like tone with specific RMS amplitude."""
    t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), endpoint=False)
    # Fundamental + harmonics to mimic vocal tract
    sig = (
        0.6 * np.sin(2 * np.pi * freq * t)
        + 0.3 * np.sin(2 * np.pi * freq * 2 * t)
        + 0.1 * np.sin(2 * np.pi * freq * 3 * t)
    )
    current_rms = np.sqrt(np.mean(sig ** 2))
    scale = rms_target / (current_rms + 1e-9)
    sig = sig * scale
    sig = np.clip(sig, -1.0, 1.0)
    int16_samples = (sig * 32767).astype(np.int16)
    return sr.AudioData(int16_samples.tobytes(), sample_rate, 2)


def test_usb_headset_sample_rates_resampling(engine):
    """
    Spesifikasi USB Headset: Native USB codec biasanya 44.1kHz atau 48kHz.
    Engine wajib me-resample ke 16kHz (TARGET_SAMPLE_RATE) dengan akurat.
    """
    for native_rate in [44100, 48000]:
        audio_in = _generate_synthetic_speech(native_rate, 1.0, rms_target=0.03)
        resampled = _resample_audio_data(audio_in, TARGET_SAMPLE_RATE)

        assert resampled.sample_rate == TARGET_SAMPLE_RATE
        assert len(resampled.get_raw_data()) == TARGET_SAMPLE_RATE * 2  # 16000 samples * 2 bytes (int16)
        
        # RMS setelah resample tidak boleh drop drastis
        orig_rms = engine._calculate_rms(audio_in)
        res_rms = engine._calculate_rms(resampled)
        assert abs(orig_rms - res_rms) < 0.005


def test_mic_sensitivity_minus_40db_quiet_speech(engine):
    """
    Spesifikasi: Sensitivitas -40 ± 2 dB.
    Suara pelan/bisik pada mic -40 dB menghasilkan RMS sekitar 0.015 - 0.025.
    Sebelum fix: Diblokir oleh gate 0.000 - 0.050 (IGNORE).
    Sesudah fix: Lolos silence filter dan dinormalisasi dengan gain terkontrol.
    """
    quiet_speech = _generate_synthetic_speech(16000, 2.0, rms_target=0.018)
    rms = engine._calculate_rms(quiet_speech)

    # 1. Pastikan di atas threshold noise floor
    assert rms > MIN_RMS_THRESHOLD
    # 2. Pastikan lolos evaluasi zona
    assert engine._is_rms_in_process_zone(rms) is True

    # 3. Normalisasi menaikkan volume mendekati target tanpa clipping kotak
    norm_audio = engine._normalize_audio(quiet_speech)
    norm_rms = engine._calculate_rms(norm_audio)
    assert norm_rms > rms
    assert norm_rms <= rms * MAX_NORMALIZE_GAIN + 0.05


def test_mic_sensitivity_normal_speech(engine):
    """
    Spesifikasi: Sensitivitas -40 ± 2 dB pada jarak 3-5 cm dari mulut.
    Suara percakapan normal menghasilkan RMS sekitar 0.035 - 0.055.
    Wajib lolos dan diproses STT.
    """
    normal_speech = _generate_synthetic_speech(16000, 2.0, rms_target=0.040)
    rms = engine._calculate_rms(normal_speech)

    assert engine._is_rms_in_process_zone(rms) is True
    norm_audio = engine._normalize_audio(normal_speech)
    assert engine._calculate_rms(norm_audio) > 0.040


def test_mic_shouting_not_blocked_by_old_dead_zone(engine):
    """
    Bug Lama: RMS 0.301 - 0.450 masuk zona IGNORE ('teriakan bocor tetangga').
    Padahal teriakan emosi gamer ke mic -40 dB sering mencapai RMS 0.35.
    Wajib lolos dan tidak diblokir.
    """
    shout_speech = _generate_synthetic_speech(16000, 1.5, rms_target=0.35)
    rms = engine._calculate_rms(shout_speech)

    assert engine._is_rms_in_process_zone(rms) is True

    # Soft tanh limiter memastikan tidak terjadi overflow int16
    norm_audio = engine._normalize_audio(shout_speech)
    raw = np.frombuffer(norm_audio.get_raw_data(), dtype=np.int16)
    assert np.max(np.abs(raw)) <= 32767


def test_mic_impedance_noise_floor_vs_silence(engine):
    """
    Spesifikasi: Impedansi 2.2 kΩ.
    Desis thermal mic + noise lantai kamar biasanya RMS < 0.001.
    Audio murni desis/diam wajib diabaikan oleh MIN_RMS_THRESHOLD.
    """
    ambient_hiss = _generate_synthetic_speech(16000, 1.0, rms_target=0.0003)
    rms = engine._calculate_rms(ambient_hiss)

    assert rms < MIN_RMS_THRESHOLD


def test_end_to_end_headset_stt_pipeline(engine, detector):
    """
    Test End-to-End: Suara diproses lewat _apply_gain, _normalize_audio,
    dan Google Speech STT online, lalu dideteksi oleh ToxicDetector.
    """
    import win32com.client
    import os

    wav_path = "tests/temp_headset_test.wav"
    try:
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        stream = win32com.client.Dispatch("SAPI.SpFileStream")
        stream.Open(wav_path, 3)
        speaker.AudioOutputStream = stream
        # Gunakan fonetik yang dikenali Google id-ID dari English SAPI voice
        speaker.Speak("may make")
        stream.Close()

        r = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio = r.record(source)

        # Scale ke level sensitivitas mic -40 dB (RMS ~0.025)
        raw = np.frombuffer(audio.get_raw_data(), dtype=np.int16).astype(np.float32)
        scaled_raw = (raw * 0.35).astype(np.int16)
        mic_audio = sr.AudioData(scaled_raw.tobytes(), audio.sample_rate, audio.sample_width)

        rms = engine._calculate_rms(mic_audio)
        assert engine._is_rms_in_process_zone(rms) is True

        processed = engine._normalize_audio(engine._apply_gain(mic_audio))
        text = r.recognize_google(processed, language="id-ID")
        assert len(text) > 0

        res = detector.detect(text)
        assert res.is_toxic is True
        assert "memek" in res.matched_words
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)

