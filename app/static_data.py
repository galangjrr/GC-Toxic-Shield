# =============================================================
# GC Toxic Shield V2 — Static Data (Messages & Quotes)
# =============================================================
# Menyediakan pesan peringatan dan kutipan motivasi
# untuk sistem Warning & Lockdown.
#
# Referensi: StaticData.cs dari project C# sebelumnya.
# =============================================================

import random
import logging

logger = logging.getLogger("GCToxicShield.StaticData")


# ── Warning Messages (Level 1-3, cycling) ─────────────────────

_WARNING_MESSAGES = {
    1: (
        "⚠️ Peringatan Pertama\n\n"
        "Sistem mendeteksi penggunaan kata-kata yang tidak pantas.\n"
        "Mohon jaga tutur kata Anda.\n\n"
        "Ini adalah peringatan ringan. Jika terus berlanjut,\n"
        "tindakan yang lebih tegas akan diambil."
    ),
    2: (
        "⚠️ Peringatan Kedua\n\n"
        "Anda KEMBALI menggunakan bahasa yang tidak sopan.\n"
        "Ini adalah peringatan terakhir sebelum lockdown.\n\n"
        "Pelanggaran berikutnya akan mengakibatkan\n"
        "penguncian layar untuk jangka waktu tertentu."
    ),
    3: (
        "🔒 Lockdown Aktif\n\n"
        "Anda telah melanggar aturan berbahasa sebanyak 3 kali.\n"
        "Layar Anda akan dikunci sebagai konsekuensi.\n\n"
        "Gunakan waktu ini untuk merenung dan memperbaiki sikap."
    ),
}

# ── Motivational Quotes for Lockdown Screen ───────────────────

_LOCKDOWN_QUOTES = [
    "\"Kata-kata yang baik bisa mengubah dunia, kata-kata yang buruk bisa menghancurkannya.\"\n— Pepatah",
    "\"Mulutmu harimaumu. Jagalah ucapanmu, karena ia mencerminkan siapa dirimu.\"\n— Peribahasa Indonesia",
    "\"Berbicara dengan sopan tidak membuatmu lemah, justru menunjukkan kekuatan karaktermu.\"\n— Anonim",
    "\"Setiap kata yang kau ucapkan adalah cerminan dari hatimu.\"\n— Ali bin Abi Thalib",
    "\"Orang bijak berbicara karena memiliki sesuatu untuk dikatakan. Orang bodoh berbicara karena ingin mengatakan sesuatu.\"\n— Plato",
    "\"Lidah tidak bertulang, tapi bisa menghancurkan tulang.\"\n— Pepatah",
    "\"Jika kamu tidak bisa berkata baik, lebih baik diam.\"\n— Hadits Nabi",
    "\"Kebaikan dalam kata-kata menciptakan kepercayaan. Kebaikan dalam pikiran menciptakan kedamaian.\"\n— Lao Tzu",
    "\"Harga dirimu ditentukan oleh bagaimana kamu memperlakukan orang lain, termasuk dalam ucapan.\"\n— Anonim",
    "\"Satu kata kasar bisa melukai lebih dalam dari seribu pukulan.\"\n— Pepatah Jepang",
    "\"Internet bukan tempat tanpa aturan. Di balik layar ada manusia yang punya perasaan.\"\n— Anonim",
    "\"Berpikirlah sebelum berbicara. Bacalah sebelum berpikir.\"\n— Fran Lebowitz",
]


def get_message(level: int) -> str:
    """
    Mendapatkan pesan peringatan berdasarkan level (1-3 cycling).

    Args:
        level: Level pelanggaran (1-based). Di-cycle setiap 3:
               violation 1,4,7 → level 1
               violation 2,5,8 → level 2
               violation 3,6,9 → level 3

    Returns:
        Pesan peringatan string.
    """
    # Cycle 1-3
    cycle_level = ((level - 1) % 3) + 1
    return _WARNING_MESSAGES.get(cycle_level, _WARNING_MESSAGES[1])


def get_random_quote(level: int) -> str:
    """
    Mendapatkan kutipan motivasi acak untuk lockdown screen.

    Args:
        level: Level pelanggaran (digunakan sebagai seed variasi).

    Returns:
        Kutipan string.
    """
    if not _LOCKDOWN_QUOTES:
        return "\"Jagalah ucapanmu.\""
    return random.choice(_LOCKDOWN_QUOTES)
