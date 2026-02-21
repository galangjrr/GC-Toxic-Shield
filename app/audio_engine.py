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
import numpy as np
import ctypes

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
CALIBRATION_DURATION = 1
LISTEN_TIMEOUT = 10
TARGET_RMS_DB = -20.0  # Target RMS level in dB for auto-normalization
MIN_RMS_THRESHOLD = 0.001  # Below this → silence, don't normalize
PHRASE_TIME_LIMIT = 5


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


class AudioEngine:
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

        self.language = language
        self.on_transcription = on_transcription
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
        self._recognizer.dynamic_energy_threshold = True
        self._recognizer.energy_threshold = 300
        self._recognizer.pause_threshold = 1.0        # Tunggu 1.0s (lebih cepat) sebelum cut
        self._recognizer.phrase_threshold = 0.1       # Terima phrase pendek (0.1s)
        self._recognizer.non_speaking_duration = 0.5  # Padding 0.5s (ekor kalimat)

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

    def set_gain(self, gain: float):
        self.gain = max(0.0, min(gain, 10.0))

    def get_vu_level(self) -> float:
        return min(1.0, self._current_rms * 5.0)

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
                    # Calibrate once per mic open
                    logger.info("🎙 Calibrating (%ds)...", CALIBRATION_DURATION)
                    self._recognizer.adjust_for_ambient_noise(
                        source, duration=CALIBRATION_DURATION
                    )
                    logger.info(
                        "✓ Calibrated at %dHz. Threshold: %.0f",
                        actual_rate, self._recognizer.energy_threshold
                    )

                    # Reset error counter on successful open
                    consecutive_errors = 0

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
            self._recognizer.energy_threshold = 300
            self._recognizer.pause_threshold = 1.0
            self._recognizer.phrase_threshold = 0.1
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

            # ── Update RMS ──
            self._update_rms_from_audio(audio)

            # ── Google Speech Recognition ──
            text = self._recognizer.recognize_google(
                audio, language=self.language
            )
            self._online = True

            if text:
                text = text.strip()
                logger.info("📝 Transcription: %s", text)

                if self.on_transcription:
                    try:
                        self.on_transcription(text)
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

            # Convert dB gain to linear multiplier (cap at 20x / +26dB)
            gain_linear = min(10 ** (gain_db / 20.0), 20.0)

            # Apply normalization
            normalized = raw * gain_linear
            np.clip(normalized, -1.0, 1.0, out=normalized)
            normalized_int16 = (normalized * 32767).astype(np.int16)

            logger.debug(
                "🔊 Auto-normalize: %.1f dB → %.1f dB (gain: %.1fx)",
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
                    rms = float(np.sqrt(np.mean(chunk ** 2)))
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
