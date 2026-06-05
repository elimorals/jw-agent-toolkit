"""Genera fixtures de audio sintéticos para tests de ASR providers.

Crea:
- discurso_mini.wav (~5s, contiene texto con una ref bíblica en español)
- discurso_en.wav (~5s, texto con ref bíblica en inglés)

Estrategia (Fase 64):

1. **Modo preferente — `gtts` + `ffmpeg`**: usa Google TTS para sintetizar
   audio "real" con voz humana sintética. Las refs bíblicas son texto
   público (citas) + TTS sintético → sin copyright.

2. **Modo fallback — `numpy` + `wave` stdlib**: si `gtts` o `ffmpeg` no
   están disponibles, genera 5 s de tono sine 440 Hz a 16 kHz mono PCM.
   No es audio inteligible, pero suficiente para validar el pipeline
   (carga de archivo, sample rate detection, paso a transcribe, etc.).
   Los tests de transcripción REAL están marcados con
   `pytest.importorskip("whisperx")` y solo corren cuando whisperX está
   instalado y tiene acceso a un audio con contenido decodificable —
   por eso el fallback con sine es aceptable para el subset de tests
   que no validan output textual.

Uso:
    uv run --with gtts python packages/jw-core/tests/fixtures/audio/build_audio_fixtures.py

Requiere `ffmpeg` en PATH para el modo preferente. Si no, cae al fallback.
"""

from __future__ import annotations

import io
import math
import struct
import wave
from pathlib import Path

HERE = Path(__file__).parent

SCRIPTS = {
    "discurso_mini.wav": ("es", "Bienvenidos hermanos. Leamos juntos Génesis uno uno."),
    "discurso_en.wav": ("en", "Brothers, today we read John three sixteen together."),
}


def _have_ffmpeg() -> bool:
    import shutil

    return shutil.which("ffmpeg") is not None


def _synth_via_gtts(text: str, lang: str, output: Path) -> None:
    """Modo preferente: gTTS → MP3 → ffmpeg → WAV 16 kHz mono."""
    import subprocess

    from gtts import gTTS  # type: ignore[import-not-found]

    tts = gTTS(text=text, lang=lang)
    mp3_buf = io.BytesIO()
    tts.write_to_fp(mp3_buf)
    mp3_buf.seek(0)

    mp3_path = output.with_suffix(".mp3")
    mp3_path.write_bytes(mp3_buf.read())
    subprocess.check_call(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(mp3_path),
            "-ar",
            "16000",
            "-ac",
            "1",
            str(output),
        ],
        stderr=subprocess.DEVNULL,
    )
    mp3_path.unlink()


def _synth_via_sine(output: Path, *, duration_s: float = 5.0, freq_hz: float = 440.0) -> None:
    """Fallback stdlib: tono sine PCM mono 16 kHz.

    Genera audio sin contenido lingüístico, sólo válido para tests de
    pipeline (carga, sample rate, paso a transcribe). Los tests que
    requieren contenido decodificable usan `pytest.importorskip("whisperx")`
    y por tanto skipean en CI sin whisperX.
    """
    sample_rate = 16000
    n_frames = int(duration_s * sample_rate)
    amplitude = 16000  # int16, ~ -94 dBFS-ish

    with wave.open(str(output), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        for i in range(n_frames):
            value = int(amplitude * math.sin(2.0 * math.pi * freq_hz * i / sample_rate))
            wav.writeframesraw(struct.pack("<h", value))


def synth_to_wav(text: str, lang: str, output: Path) -> str:
    """Try gtts+ffmpeg first, fall back to sine.

    Returns the mode used: 'gtts' or 'sine'.
    """
    if _have_ffmpeg():
        try:
            _synth_via_gtts(text, lang, output)
            return "gtts"
        except Exception:  # noqa: BLE001
            # gTTS may fail (no network, no gtts pkg). Fall through.
            pass
    _synth_via_sine(output)
    return "sine"


def main() -> None:
    for filename, (lang, text) in SCRIPTS.items():
        out = HERE / filename
        mode = synth_to_wav(text, lang, out)
        size = out.stat().st_size
        print(f"Wrote {out} ({size} bytes, mode={mode})")


if __name__ == "__main__":
    main()
