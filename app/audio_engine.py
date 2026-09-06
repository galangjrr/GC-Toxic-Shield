# =============================================================
# GC Toxic Shield — Audio Engine (Google Speech Online)
# =============================================================
# T9: Google Speech Recognition (online, id-ID)
# T11: Post-Lockdown Latency Fix
#   - Persistent mic stream (no re-init per iteration)
#   - Async callback dispatch (listen loop never blocks)
#   - Buffer flush mechanism
#   - Thread priority HIGH
# T12: WinError 50 Fix
#   - Fallback sample rates: 16000 → 44100 → 48000
#   - Software resample when native rate differs
#   - Robust WinError 50 handling: pause + full device re-init
#   - blocksize=0 for both listen and VU meter
# =============================================================

import threading
import time
import logging
from typing import List, Dict, Any

import numpy as np
import ctypes
from PySide6.QtCore import QObject, Signal

try:
    import speech_recognition as sr
except ImportError:
    sr = None

# ── Logging ────────────────────────────────────────────────────
logger = logging.getLogger("GCToxicShield.AudioEngine")

# ── Constants ──────────────────────────────────────────────────
TARGET_SAMPLE_RATE = 16000
FALLBACK_SAMPLE_RATES = [16000, 44100, 48000]
RE_INIT_DELAY_SEC = 5
LISTEN_TIMEOUT = 10
TARGET_RMS_DB = -20.0  # Target RMS level in dB for auto-normalization
MIN_RMS_THRESHOLD = 0.001  # Below this → silence, don't normalize
PHRASE_TIME_LIMIT = 8        # Max 8s per chunk — cegah mic gantung di ruang bising warnet
MAX_NORMALIZE_GAIN = 3.0     # Batas gain 3x — cegah clipping kotak yang rusak kualitas STT


def _set_thread_priority_high():
    """Set current thread to HIGH priority on Windows."""
    try:
        THREAD_PRIORITY_HIGHEST = 2
        handle = ctypes.windll.kernel32.GetCurrentThread()
        ctypes.windll.kernel32.SetThreadPriority(handle, THREAD_PRIORITY_HIGHEST)
        logger.info("✓ Listen thread priority set to HIGH")
    except Exception as e:
        logger.warning("Could not set thread priority: %s", e)


def _resample_audio_data(audio_data: "sr.AudioData", target_rate: int) -> "sr.AudioData":
    """
    Resample AudioData ke target_rate jika berbeda.
    Menggunakan linear interpolation (numpy).
    """
    if audio_data.sample_rate == target_rate:
        return audio_data

    try:
        raw = np.frombuffer(
            audio_data.get_raw_data(), dtype=np.int16
        ).astype(np.float32)

        # Compute resample ratio
        ratio = target_rate / audio_data.sample_rate
        new_length = int(len(raw) * ratio)

        if new_length <= 0:
            return audio_data

        # Linear interpolation resample
        old_indices = np.linspace(0, len(raw) - 1, num=new_length)
        resampled = np.interp(old_indices, np.arange(len(raw)), raw)

        np.clip(resampled, -32768, 32767, out=resampled)
        resampled_bytes = resampled.astype(np.int16).tobytes()

        logger.debug(
            "Resampled: %dHz → %dHz (%d → %d samples)",
            audio_data.sample_rate, target_rate, len(raw), new_length
        )

        return sr.AudioData(resampled_bytes, target_rate, audio_data.sample_width)

    except Exception as e:
        logger.warning("Resample failed: %s — using original", e)
        return audio_data


def _try_open_microphone(device_index, sample_rates):
    """
    Coba buka Microphone dengan fallback sample rates.
    Returns (mic, actual_rate) atau raise jika semua gagal.
    """
    last_error = None

    for rate in sample_rates:
        try:
            mic = sr.Microphone(
                device_index=device_index,
                sample_rate=rate,
            )
            # Test open — akan raise jika driver tidak support
            with mic as source:
                pass  # Just test if it opens successfully

            logger.info("✓ Microphone opened at %dHz", rate)
            return mic, rate

        except OSError as e:
            error_str = str(e)
            logger.warning(
                "⚠ Cannot open mic at %dHz: %s", rate, error_str
            )
            last_error = e
            continue

        except Exception as e:
            logger.warning(
                "⚠ Mic open failed at %dHz: %s", rate, e
            )
            last_error = e
            continue

    raise OSError(
        f"Semua sample rate gagal ({sample_rates}). "
        f"Error terakhir: {last_error}"
    )


class AudioEngine(QObject):
    """
    Non-Stop Audio Engine menggunakan Google Speech Recognition.

    T11 Fixes:
    - Listen loop NEVER blocks (async callback dispatch)
    - Mic stream stays open across iterations
    - Buffer flush when lockdown triggers
    - Thread runs at HIGH priority

    T12 (WinError 50 Fix):
    - Fallback sample rates: 16000 → 44100 → 48000
    - Software resample to 16kHz for Google Speech
    - Robust WinError 50 handling with full device re-init
    - blocksize=0 for Windows driver compatibility
    """
    
    transcription_signal = Signal(str)

    def __init__(
        self,
        language: str = "id-ID",
        on_transcription=None,
        input_device_index: int = None,
        initial_gain: float = 1.5,
        # Legacy params (ignored)
        model_size: str = None,
        device: str = None,
        compute_type: str = None,
    ):
        if sr is None:
            raise ImportError(
                "speech_recognition is required. "
                "Install via: pip install SpeechRecognition PyAudio"
            )
            
        super().__init__()

        self.language = language
        self.on_transcription = on_transcription
        if self.on_transcription:
            self.transcription_signal.connect(self.on_transcription)
            
        self.normalizer_callback = None  # Hook for standardizing transcript text
        self.input_device_index = input_device_index
        self.gain = initial_gain

        # ── State ──
        self._running = False
        self._online = True
        self._lock = threading.Lock()
        self._current_rms = 0.0
        self._device_changed = False  # Flag untuk device swap
        self._actual_sample_rate = TARGET_SAMPLE_RATE  # Resolved at open time

        # ── Speech Recognition Setup ──
        self._recognizer = sr.Recognizer()
        self._recognizer.dynamic_energy_threshold = True      # NYALAKAN KEMBALI: Wajib agar STT berjalan sesuai volume mic
        self._recognizer.energy_threshold = 150               # Mulai dari angka sangat rendah agar mic yang pelan bisa tertangkap
        self._recognizer.pause_threshold = 1.2                # Tunggu 1.2s (snappy response for shouting)
        self._recognizer.phrase_threshold = 0.3               # Minimum panjang frase
        self._recognizer.non_speaking_duration = 0.5          # Simpan 0.5 detik awal/akhir agar tidak terpotong

        # ── Threads ──
        self._listen_thread = None
        self._vu_thread = None

        logger.info(
            "AudioEngine (Google Speech) initialized | lang=%s | gain=%.1f",
            language, initial_gain
        )

    # ================================================================
    # PUBLIC API
    # ================================================================

    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True

        logger.info("▶ Starting AudioEngine (Google Speech)...")

        self._listen_thread = threading.Thread(
            target=self._listen_loop,
            name="AudioEngine-Listener",
            daemon=True,
        )
        self._listen_thread.start()

        self._vu_thread = threading.Thread(
            target=self._vu_meter_loop,
            name="AudioEngine-VUMeter",
            daemon=True,
        )
        self._vu_thread.start()

        logger.info("✓ AudioEngine is now ACTIVE (online mode)")

    def stop(self):
        with self._lock:
            if not self._running:
                return
            self._running = False

        logger.info("■ Stopping AudioEngine...")
        if self._listen_thread and self._listen_thread.is_alive():
            self._listen_thread.join(timeout=3)
        if self._vu_thread and self._vu_thread.is_alive():
            self._vu_thread.join(timeout=2)
        logger.info("✓ AudioEngine stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_online(self) -> bool:
        return self._online

    # ── Audio Settings API ──

    @staticmethod
    def list_devices():
        devices = []
        try:
            import pyaudio
            pa = pyaudio.PyAudio()
            for i in range(pa.get_device_count()):
                info = pa.get_device_info_by_index(i)
                if info.get("maxInputChannels", 0) > 0:
                    devices.append((i, info["name"]))
            pa.terminate()
        except Exception as e:
            logger.error("Failed to list devices: %s", e)
        return devices

    def set_input_device(self, index: int):
        if self.input_device_index == index:
            return
        logger.info("Changing input device to index %d", index)
        self.input_device_index = index
        self._device_changed = True  # Signal listen loop to re-open mic

    def set_gain(self, gain: float) -> None:
        """Set the digital gain value, clamped to [0.0, 10.0].

        Args:
            gain: Desired gain multiplier.
        """
        self.gain = max(0.0, min(gain, 10.0))

    def get_vu_level(self) -> float:
        """Get VU meter level with perceptual scaling (0.0–1.0).

        Uses an exponential curve to match human loudness perception.
        Typical speech hits ~0.02–0.05 RMS → ~48–70% on the meter.

        Returns:
            Scaled VU level between 0.0 and 1.0.
        """
        if self._current_rms <= 0.0:
            return 0.0
        level = (self._current_rms * 15.0) ** 0.6
        return float(max(0.0, min(1.0, level)))

    def get_current_rms(self) -> float:
        """Return the current raw RMS value (0.0–1.0) for UI display.

        Unlike ``get_vu_level()`` which applies perceptual scaling,
        this returns the actual linear RMS suitable for zone calibration.

        Returns:
            Current RMS float value between 0.0 and 1.0.
        """
        return float(self._current_rms)

    # ================================================================
    # CORE: NON-STOP LISTEN LOOP (T11 + T12 Fixed)
    # ================================================================

    def _listen_loop(self):
        """
        Main recognition loop — NEVER blocks on callbacks.

        Key design:
        1. Mic opens with fallback sample rates (16k → 44.1k → 48k).
        2. Audio resampled to 16kHz before Google Speech if needed.
        3. WinError 50 triggers 5s pause + full device re-init.
        4. Thread runs at HIGH priority.
        """
        _set_thread_priority_high()

        logger.info("Listen loop started (non-blocking, persistent mic)")
        consecutive_errors = 0

        while self._running:
            try:
                # ── Open mic with fallback sample rates ──
                mic, actual_rate = _try_open_microphone(
                    self.input_device_index, FALLBACK_SAMPLE_RATES
                )
                self._actual_sample_rate = actual_rate

                needs_resample = (actual_rate != TARGET_SAMPLE_RATE)
                if needs_resample:
                    logger.info(
                        "⚙ Will resample %dHz → %dHz in software",
                        actual_rate, TARGET_SAMPLE_RATE
                    )

                with mic as source:
                    # Reset error counter on successful open
                    consecutive_errors = 0

                    # ── Auto-calibrate mic noise floor per-device ──
                    # Ukur desis ambient warnet (AC/kipas) sekali saat buka mic.
                    # Hasil ukuran ini menggantikan hardcode energy_threshold = 150.
                    try:
                        logger.info("Calibrating ambient noise (1s)...")
                        self._recognizer.adjust_for_ambient_noise(source, duration=1.0)
                        logger.info(
                            "Ambient noise calibrated → energy_threshold=%.1f",
                            self._recognizer.energy_threshold
                        )
                    except Exception as cal_err:
                        logger.warning("Ambient noise calibration failed: %s", cal_err)

                    # ── Inner loop: listen continuously ──
                    self._device_changed = False

                    while self._running and not self._device_changed:
                        try:
                            audio = self._recognizer.listen(
                                source,
                                timeout=LISTEN_TIMEOUT,
                                phrase_time_limit=PHRASE_TIME_LIMIT,
                            )

                            # Resample if mic is not at target rate
                            if needs_resample:
                                audio = _resample_audio_data(
                                    audio, TARGET_SAMPLE_RATE
                                )

                            # ── Detach audio from stream ──
                            # Deep-copy raw bytes so the processing thread
                            # never touches the live audio driver (WinError 50 fix)
                            try:
                                raw_bytes = audio.get_raw_data()
                                detached_audio = sr.AudioData(
                                    raw_bytes,
                                    audio.sample_rate,
                                    audio.sample_width,
                                )
                            except OSError as copy_err:
                                logger.warning(
                                    "Audio detach failed: %s — skipping",
                                    copy_err
                                )
                                continue

                            # ── Proximity Zone Gate ──
                            # Evaluasi RMS chunk sebelum kirim ke Google STT.
                            # Zona IGNORE dibuang di sini — suara desis & bocor PC sebelah tidak pernah sampai ke cloud.
                            chunk_rms = self._calculate_rms(detached_audio)
                            if not self._is_rms_in_process_zone(chunk_rms):
                                logger.debug(
                                    "Proximity IGNORED: rms=%.4f (desis/bocor)",
                                    chunk_rms
                                )
                                continue

                            # >>> ASYNC DISPATCH — never blocks listen loop <<<
                            threading.Thread(
                                target=self._process_audio,
                                args=(detached_audio,),
                                name="AudioEngine-Process",
                                daemon=True,
                            ).start()

                        except sr.WaitTimeoutError:
                            continue  # No speech, keep listening

                        except OSError as e:
                            # WinError 50 or similar during listen
                            error_str = str(e)
                            if "WinError 50" in error_str or "[Errno" in error_str:
                                logger.error(
                                    "🎤 WinError during listen: %s — "
                                    "breaking for full re-init",
                                    error_str
                                )
                                break  # Break inner loop → full re-init
                            else:
                                raise  # Other OSError, let outer handler deal

                # Device changed → re-open mic at top of outer loop
                if self._device_changed:
                    logger.info("Device changed, re-opening mic...")
                    continue

            except OSError as e:
                consecutive_errors += 1
                error_str = str(e)

                if "WinError 50" in error_str:
                    logger.error(
                        "🎤 WinError 50: %s — "
                        "Pausing %ds then full device re-init (attempt #%d)",
                        error_str, RE_INIT_DELAY_SEC, consecutive_errors
                    )
                else:
                    logger.error(
                        "🎤 Device error: %s — "
                        "Retrying in %ds (attempt #%d)",
                        error_str, RE_INIT_DELAY_SEC, consecutive_errors
                    )

                # Full re-init: destroy recognizer state, wait, recreate
                self._full_audio_reinit()
                time.sleep(RE_INIT_DELAY_SEC)

                # Exponential backoff on repeated failures (max 30s)
                if consecutive_errors > 3:
                    extra_wait = min(consecutive_errors * 2, 25)
                    logger.warning(
                        "⚠ %d consecutive failures — extra wait %ds",
                        consecutive_errors, extra_wait
                    )
                    time.sleep(extra_wait)

            except Exception as e:
                consecutive_errors += 1
                logger.error(
                    "✗ Listen error: %s — Retrying in %ds",
                    e, RE_INIT_DELAY_SEC
                )
                time.sleep(RE_INIT_DELAY_SEC)

        logger.info("Listen loop ended")

    def _full_audio_reinit(self):
        """
        Full re-initialization of audio subsystem.
        Called after WinError 50 or persistent device errors.
        """
        logger.info("⟳ Full audio re-init...")
        try:
            # Reset recognizer state
            self._recognizer = sr.Recognizer()
            self._recognizer.dynamic_energy_threshold = True
            self._recognizer.energy_threshold = 150
            self._recognizer.pause_threshold = 1.2
            self._recognizer.phrase_threshold = 0.3
            self._recognizer.non_speaking_duration = 0.5
            logger.info("✓ Recognizer re-created")
        except Exception as e:
            logger.error("Re-init failed: %s", e)

    def _process_audio(self, audio: "sr.AudioData"):
        """
        Process audio in a SEPARATE thread.
        This is fire-and-forget — listen loop continues immediately.
        """
        try:
            # ── Apply Manual Gain ──
            if self.gain != 1.0:
                audio = self._apply_gain(audio)

            # ── Auto-Normalize (compensate weak mics) ──
            audio = self._normalize_audio(audio)

            # ── Update RMS & Store Chunk Metrics ──
            self._update_rms_from_audio(audio)
            # ── Google Speech Recognition ──
            text = self._recognizer.recognize_google(
                audio, language=self.language
            )
            self._online = True

            if text:
                text = text.strip()
                
                if self.normalizer_callback:
                    try:
                        text = self.normalizer_callback(text)
                    except Exception as e:
                        logger.error("Normalizer callback error: %s", e)

                logger.info("📝 Transcription: %s", text)

                try:
                    self.transcription_signal.emit(text)
                except Exception as cb_err:
                    logger.error("Callback error: %s", cb_err)

        except sr.UnknownValueError:
            pass  # No clear speech

        except sr.RequestError as e:
            self._online = False
            logger.warning("🔴 OFFLINE: %s", e)

        except Exception as e:
            logger.error("Process error: %s", e)

    # ================================================================
    # HELPERS
    # ================================================================

    # Zona default proximity warnet.
    # Format: (min_rms, max_rms, action)
    # action="PROCESS" → kirim ke STT | action="IGNORE" → buang
    _DEFAULT_PROXIMITY_ZONES = [
        (0.000, 0.050, "IGNORE"),   # Desis AC/kipas/background noise
        (0.051, 0.300, "PROCESS"),  # Suara mulut user normal
        (0.301, 0.450, "IGNORE"),   # Teriakan bocor dari PC sebelah
        (0.451, 1.000, "PROCESS"),  # Teriakan langsung ke mic user
    ]

    def _is_rms_in_process_zone(self, rms: float) -> bool:
        """
        Evaluasi apakah chunk audio lolos ke STT berdasarkan energi RMS.

        Prioritaskan proximity_zones dari engine (dikonfigurasi admin via UI).
        Fallback ke _DEFAULT_PROXIMITY_ZONES jika belum dikonfigurasi.

        Args:
            rms: Linear RMS energy [0.0, 1.0] dari chunk audio.

        Returns:
            True jika zona action="PROCESS", False jika "IGNORE" atau tidak cocok.
        """
        zones = getattr(self, "proximity_zones", None) or self._DEFAULT_PROXIMITY_ZONES
        for zone in zones:
            if isinstance(zone, dict):
                min_r = float(zone.get("min_rms", 0))
                max_r = float(zone.get("max_rms", 0))
                action = zone.get("action", "IGNORE")
            else:
                min_r, max_r, action = zone[0], zone[1], zone[2]

            if min_r <= rms <= max_r:
                return action == "PROCESS"

        # Tidak ada zona yang cocok → buang (safe default)
        return False

    def _calculate_rms(self, audio: "sr.AudioData") -> float:
        """Calculate the Root Mean Square energy of an audio chunk.

        Normalizes raw int16 samples to the [-1.0, 1.0] float range,
        then computes ``sqrt(mean(samples²))``.  Result is a linear
        energy value between 0.0 (silence) and 1.0 (full-scale).

        Args:
            audio: AudioData object containing raw PCM samples.

        Returns:
            RMS energy as a float in [0.0, 1.0].  Returns 0.0 on error.
        """
        try:
            raw = np.frombuffer(
                audio.get_raw_data(), dtype=np.int16
            ).astype(np.float32) / 32768.0
            return float(np.sqrt(np.mean(raw ** 2)))
        except Exception as e:
            logger.warning("RMS calculation failed: %s", e)
            return 0.0

    def _apply_gain(self, audio: "sr.AudioData") -> "sr.AudioData":
        try:
            raw = np.frombuffer(
                audio.get_raw_data(), dtype=np.int16
            ).astype(np.float32)
            raw *= self.gain
            np.clip(raw, -32768, 32767, out=raw)
            gained_bytes = raw.astype(np.int16).tobytes()
            return sr.AudioData(gained_bytes, audio.sample_rate, audio.sample_width)
        except Exception:
            return audio

    def _normalize_audio(self, audio: "sr.AudioData") -> "sr.AudioData":
        """
        Auto-normalisasi audio ke target RMS level.
        Mengangkat volume suara yang lemah (mic murah / jauh)
        tanpa merusak kualitas audio yang sudah cukup keras.

        Perubahan T13:
        - Batas gain MAX_NORMALIZE_GAIN = 3x (sebelumnya 20x).
          Gain 20x hasilkan gelombang kotak (hard-clip) yang dikenali
          Google Speech sebagai noise, bukan kata.
        - Soft tanh limiter gantikan np.clip keras — permukaan gelombang
          tetap melengkung alami walau amplitudo dipangkas.

        Cocok untuk: Fantech HQ 53, mic headset gaming ekonomi, dll.
        """
        try:
            raw = np.frombuffer(
                audio.get_raw_data(), dtype=np.int16
            ).astype(np.float32) / 32768.0  # Normalize to [-1.0, 1.0]

            # Calculate current RMS
            rms = float(np.sqrt(np.mean(raw ** 2)))

            if rms < MIN_RMS_THRESHOLD:
                # Silence or near-silence — don't amplify noise
                return audio

            # Calculate current RMS in dB
            current_db = 20.0 * np.log10(rms + 1e-10)

            # Calculate required gain to reach target
            gain_db = TARGET_RMS_DB - current_db

            if gain_db <= 0:
                # Audio already loud enough — no boost needed
                return audio

            # Convert dB gain to linear multiplier — cap at MAX_NORMALIZE_GAIN (3x)
            # Sebelumnya 20x: hasilkan hard-clip kotak yang rusak akurasi STT
            gain_linear = min(10 ** (gain_db / 20.0), MAX_NORMALIZE_GAIN)

            # Apply normalization dengan soft tanh limiter
            # tanh: gelombang tetap melengkung alami (tidak kotak) walau dipangkas
            normalized = np.tanh(raw * gain_linear)

            normalized_int16 = (normalized * 32767).astype(np.int16)

            logger.debug(
                "Auto-normalize: %.1f dB -> %.1f dB (gain: %.1fx, soft-limit)",
                current_db, TARGET_RMS_DB, gain_linear
            )

            return sr.AudioData(
                normalized_int16.tobytes(),
                audio.sample_rate,
                audio.sample_width,
            )

        except Exception as e:
            logger.warning("Normalize failed: %s — using original", e)
            return audio

    def _update_rms_from_audio(self, audio: "sr.AudioData"):
        try:
            raw = np.frombuffer(
                audio.get_raw_data(), dtype=np.int16
            ).astype(np.float32) / 32768.0
            rms = float(np.sqrt(np.mean(raw ** 2)))
            self._current_rms = self._current_rms * 0.3 + rms * 0.7
        except Exception:
            pass

    def _vu_meter_loop(self):
        """
        Separate lightweight stream for real-time VU meter.
        T12: fallback sample rates + robust WinError 50 handling.
        """
        try:
            import sounddevice as sd
        except ImportError:
            logger.warning("sounddevice not available — VU meter disabled")
            return

        while self._running:
            try:
                # Try each sample rate until one works
                vu_rate = self._find_working_vu_rate(sd)
                if vu_rate is None:
                    logger.warning("VU meter: no working sample rate found")
                    time.sleep(RE_INIT_DELAY_SEC)
                    continue

                def vu_callback(indata, frames, time_info, status):
                    if not self._running:
                        return
                    chunk = indata[:, 0]
                    if self.gain != 1.0:
                        chunk = chunk * self.gain
                    rms = float(np.sqrt(np.mean(chunk**2)))
                    self._current_rms = self._current_rms * 0.5 + rms * 0.5

                with sd.InputStream(
                    samplerate=vu_rate,
                    channels=1,
                    dtype="float32",
                    blocksize=0,  # Let Windows driver decide buffer size
                    device=self.input_device_index,
                    callback=vu_callback,
                ):
                    logger.info(
                        "✓ VU meter stream active (%dHz, blocksize=0)",
                        vu_rate
                    )
                    while self._running and not self._device_changed:
                        time.sleep(0.1)

                # If device changed, loop back and re-open
                if self._device_changed:
                    logger.info("VU meter: device changed, re-opening...")
                    continue

            except OSError as e:
                error_str = str(e)
                if "WinError 50" in error_str:
                    logger.warning(
                        "VU meter WinError 50: %s — "
                        "pausing %ds then re-init",
                        error_str, RE_INIT_DELAY_SEC
                    )
                else:
                    logger.warning(
                        "VU meter device error: %s — retrying in %ds",
                        error_str, RE_INIT_DELAY_SEC
                    )
                time.sleep(RE_INIT_DELAY_SEC)

            except Exception as e:
                logger.warning("VU meter error: %s — retrying in %ds", e, RE_INIT_DELAY_SEC)
                time.sleep(RE_INIT_DELAY_SEC)

    def _find_working_vu_rate(self, sd_module) -> int:
        """Try each fallback sample rate for VU meter, return first working one."""
        for rate in FALLBACK_SAMPLE_RATES:
            try:
                # Quick test: open stream and close immediately
                with sd_module.InputStream(
                    samplerate=rate,
                    channels=1,
                    dtype="float32",
                    blocksize=0,
                    device=self.input_device_index,
                ):
                    pass
                logger.info("VU meter: %dHz works", rate)
                return rate
            except Exception:
                logger.debug("VU meter: %dHz not supported", rate)
                continue
        return None

