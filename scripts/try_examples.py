"""Example reviews for scripts.try_reviews and scripts.try_replies, per industry.

Slugs, flags and preset ids are those of OneBox's industry catalog (scripts/data/industries.json);
tests/test_try_examples.py fails when an example names one the catalog no longer has.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Example:
    """One review and what a good analysis says about it. Tags are matched by any of the listed slugs."""

    name: str
    rating: int
    text: str
    sentiment: tuple[str, ...]  # acceptable overall sentiments
    tags: tuple[tuple[tuple[str, ...], str], ...] = ()  # ((acceptable slugs), sentiment about that aspect)
    flags: tuple[str, ...] = ()  # risk flags that must be raised
    none_negative: bool = False  # a pure compliment must not carry a negative tag


@dataclass(frozen=True)
class ReplyExample:
    """One review and the reply decision a good suggestion makes: a preset, an escalation, or none."""

    name: str
    text: str
    mode: str  # preset | escalate | none
    presets: tuple[str, ...] = ()  # acceptable preset ids when mode == preset
    flags: tuple[str, ...] = ()  # critical risk flags that must be raised when mode == escalate


def _t(*slugs: str, s: str) -> tuple[tuple[str, ...], str]:
    return slugs, s


REVIEW_EXAMPLES: dict[str, tuple[Example, ...]] = {
    "kesehatan": (
        Example(
            "Positif: dokter, perawat, kebersihan", 5,
            "Dokternya ramah dan menjelaskan dengan sangat jelas, perawatnya sigap dan sabar, ruangannya bersih sekali. Terima kasih RS Hermina!",
            ("positive",),
            (_t("pelayanan_dokter", s="positive"), _t("pelayanan_perawat", s="positive"), _t("kebersihan", s="positive")),
            none_negative=True,
        ),
        Example(
            "Positif: pujian singkat", 5, "Pelayanan memuaskan, terima kasih.", ("positive",),
            (_t("pujian_umum", "kualitas_layanan", "pelayanan_petugas", s="positive"),), none_negative=True,
        ),
        Example(
            "Negatif: antre, administrasi, parkir", 1,
            "Antre pendaftaran lebih dari dua jam, petugas administrasinya judes, dan parkirnya penuh. Sangat mengecewakan.",
            ("negative",),
            (_t("waktu_tunggu", s="negative"), _t("administrasi", "pelayanan_petugas", s="negative"), _t("parkir", s="negative")),
        ),
        Example(
            "Campuran: dokter bagus, parkir buruk", 3,
            "Dokternya bagus dan sabar menjelaskan, tapi parkirnya penuh dan harus muter lama cari tempat.",
            ("mixed",), (_t("pelayanan_dokter", s="positive"), _t("parkir", s="negative")),
        ),
        Example(
            "Campuran: apotek cepat, tagihan keliru", 2,
            "Obat di apotek lengkap dan cepat, tapi tagihan kamar tidak sesuai estimasi dan kasirnya tidak ramah.",
            ("mixed",), (_t("farmasi", s="positive"), _t("tagihan_pembayaran", s="negative")),
        ),
        Example(
            "Negatif berat: salah obat, mau viral", 1,
            "Anak saya salah diberi obat oleh perawat dan hampir celaka. Akan saya viralkan di media sosial!",
            ("negative",), (_t("pelayanan_perawat", "farmasi", "keamanan", s="negative"),),
            flags=("keselamatan_pasien", "risiko_viral"),
        ),
        Example(
            "Campuran (English): IGD lama, perawat baik", 3,
            "The ER wait was very long, but the nurses were kind and caring.",
            ("mixed",), (_t("igd", "waktu_tunggu", s="negative"), _t("pelayanan_perawat", s="positive")),
        ),
    ),
    "spbu": (
        Example(
            "Positif: petugas, antrean, toilet", 5,
            "Petugas SPBU ramah, antre cepat dan toiletnya bersih. Terima kasih!", ("positive",),
            (_t("pelayanan_petugas", s="positive"), _t("waktu_tunggu", s="positive"), _t("kebersihan", s="positive")), none_negative=True,
        ),
        Example(
            "Negatif: takaran kurang, petugas cuek", 1,
            "Isi bensin 20 liter tapi takarannya kurang, curiga kena kecurangan. Petugas malah cuek.", ("negative",),
            (_t("takaran_bbm", s="negative"), _t("pelayanan_petugas", s="negative")), flags=("kecurangan_bbm",),
        ),
        Example(
            "Campuran: BBM bagus, QRIS gagal", 3,
            "Bensinnya selalu tersedia dan kualitasnya bagus, tapi pembayaran QRIS sering gagal.", ("mixed",),
            (_t("ketersediaan_bbm", "kualitas_bbm", s="positive"), _t("pembayaran_digital", s="negative")),
        ),
        Example(
            "Kritis: merokok dekat pompa", 1,
            "Ada bapak merokok di dekat pompa dan petugas membiarkan, hampir terjadi kebakaran!", ("negative",),
            (_t("keamanan", "pelayanan_petugas", s="negative"),), flags=("risiko_kebakaran",),
        ),
    ),
    "asuransi": (
        Example(
            "Positif: klaim cepat, agen membantu", 5,
            "Klaim saya diproses cepat dan agennya sangat membantu. Terima kasih!", ("positive",),
            (_t("penanganan_klaim", s="positive"), _t("perilaku_agen", "pelayanan_petugas", s="positive")), none_negative=True,
        ),
        Example(
            "Negatif: klaim ditolak, lapor OJK", 1,
            "Klaim ditolak tanpa alasan jelas, sudah tiga bulan tidak ada kabar. Saya akan lapor OJK.", ("negative",),
            (_t("penanganan_klaim", s="negative"),), flags=("sengketa_klaim",),
        ),
        Example(
            "Campuran: aplikasi bagus, rekanan sedikit", 3,
            "Aplikasinya bagus dan mudah dipakai, tapi rumah sakit rekanan di kota saya sedikit.", ("mixed",),
            (_t("layanan_digital", s="positive"), _t("jaringan_rekanan", s="negative")),
        ),
        Example(
            "Dugaan penipuan: janji premi kembali", 1,
            "Agen menjanjikan premi bisa dikembalikan 100% padahal tidak ada di polis, ini penipuan.", ("negative",),
            (_t("perilaku_agen", "pelayanan_petugas", s="negative"),), flags=("dugaan_penipuan",),
        ),
    ),
    "kuliner": (
        Example(
            "Positif: rasa, suasana, pelayan", 5,
            "Makanannya enak banget, tempatnya nyaman dan pelayannya ramah.", ("positive",),
            (_t("makanan_minuman", s="positive"), _t("suasana_tempat", "fasilitas", s="positive"), _t("pelayanan_petugas", s="positive")),
            none_negative=True,
        ),
        Example(
            "Negatif: menu habis, pelayanan lambat", 2,
            "Menu favorit sering habis dan pelayanannya lambat sekali.", ("negative",),
            (_t("ketersediaan_menu", s="negative"), _t("waktu_tunggu", "pelayanan_petugas", s="negative")),
        ),
        Example(
            "Campuran: enak tapi kotor", 3,
            "Rasanya enak tapi mejanya kotor dan lalat di mana-mana.", ("mixed",),
            (_t("makanan_minuman", s="positive"), _t("kebersihan", s="negative")),
        ),
        Example(
            "Kritis: dugaan keracunan", 1,
            "Setelah makan di sini anak saya muntah-muntah, kayaknya keracunan makanan.", ("negative",),
            (_t("makanan_minuman", "kebersihan", s="negative"),), flags=("keamanan_pangan",),
        ),
    ),
    "telekomunikasi": (
        Example(
            "Positif: internet stabil, teknisi tepat waktu", 5,
            "Internet stabil dan teknisinya datang tepat waktu. Puas banget.", ("positive",),
            (_t("stabilitas_jaringan", "kecepatan_internet", s="positive"), _t("kunjungan_teknisi", s="positive")), none_negative=True,
        ),
        Example(
            "Negatif: sering putus, mau berhenti", 1,
            "Internet sering putus, sudah seminggu tidak ada perbaikan. Saya mau berhenti langganan saja.", ("negative",),
            (_t("stabilitas_jaringan", s="negative"),), flags=("ancaman_berhenti_langganan",),
        ),
        Example(
            "Campuran: cepat tapi tagihan naik", 3,
            "Kecepatan internet bagus tapi tagihan bulan ini naik tanpa pemberitahuan.", ("mixed",),
            (_t("kecepatan_internet", s="positive"), _t("tagihan_pembayaran", "harga_biaya", s="negative")),
        ),
        Example(
            "Gangguan massal: satu komplek mati", 1,
            "Satu komplek mati internet dari semalam, tetangga semua mengalami hal yang sama.", ("negative",),
            (_t("stabilitas_jaringan", s="negative"),), flags=("gangguan_massal",),
        ),
    ),
    "layanan_publik": (
        Example(
            "Positif: KTP cepat, petugas ramah", 5,
            "Pengurusan KTP cepat, petugasnya ramah dan informasinya jelas.", ("positive",),
            (_t("urusan_dokumen", s="positive"), _t("pelayanan_petugas", s="positive"), _t("kejelasan_informasi", s="positive")),
            none_negative=True,
        ),
        Example(
            "Negatif: berbelit, bolak-balik", 1,
            "Prosedurnya berbelit, disuruh bolak-balik tiga kali dan informasinya tidak jelas.", ("negative",),
            (_t("prosedur_birokrasi", s="negative"), _t("kejelasan_informasi", s="negative")),
        ),
        Example(
            "Campuran: aplikasi membantu, loket antre", 3,
            "Aplikasi online-nya membantu, tapi antrean loket tetap panjang.", ("mixed",),
            (_t("layanan_digital", s="positive"), _t("waktu_tunggu", s="negative")),
        ),
        Example(
            "Dugaan pungli: uang tambahan", 1,
            "Petugas minta uang tambahan Rp 200 ribu supaya berkas cepat selesai.", ("negative",),
            (_t("pelayanan_petugas", "urusan_dokumen", s="negative"),), flags=("dugaan_pungli",),
        ),
    ),
    "lapangan_udara": (
        Example(
            "Positif: petugas ramah, prosedur jelas", 5,
            "Petugas keamanan ramah dan prosedur masuknya jelas. Tempatnya juga bersih.", ("positive",),
            (_t("pelayanan_petugas", "keamanan", s="positive"), _t("prosedur_akses", s="positive")), none_negative=True,
        ),
        Example(
            "Negatif: izin masuk lama", 2,
            "Proses izin masuk lama dan petugas tidak memberi penjelasan.", ("negative",),
            (_t("prosedur_akses", "waktu_tunggu", s="negative"),),
        ),
        Example(
            "Campuran: wisata pesawat bagus, parkir sempit", 3,
            "Melihat pesawat dari dekat seru untuk wisata keluarga, tapi parkirnya sempit.", ("mixed",),
            (_t("kegiatan_pengunjung", s="positive"), _t("parkir", s="negative")),
        ),
        Example(
            "Kritis: drone dekat landasan", 1,
            "Ada drone terbang rendah dekat landasan dan tidak ada petugas yang menegur, sangat membahayakan penerbangan.", ("negative",),
            (_t("keamanan", "pelayanan_petugas", s="negative"),), flags=("keselamatan_penerbangan",),
        ),
        Example(
            "Kritis: orang menerobos pagar", 1,
            "Ada orang tak dikenal menerobos pagar area terbatas dan petugas tidak bereaksi sama sekali.", ("negative",),
            (_t("keamanan", "pelayanan_petugas", s="negative"),), flags=("insiden_keamanan",),
        ),
    ),
    "umum": (
        Example(
            "Positif: cepat, bersih, ramah", 5, "Pelayanan cepat, tempat bersih, petugas ramah.", ("positive",),
            (_t("pelayanan_petugas", s="positive"), _t("waktu_tunggu", s="positive"), _t("kebersihan", s="positive")), none_negative=True,
        ),
        Example(
            "Negatif: antre, parkir, mahal", 1, "Antre lama, parkir susah, dan harga mahal.", ("negative",),
            (_t("waktu_tunggu", s="negative"), _t("parkir", s="negative"), _t("harga_biaya", s="negative")),
        ),
        Example(
            "Campuran: ramah tapi kotor", 3, "Petugasnya ramah tapi tempatnya kotor.", ("mixed",),
            (_t("pelayanan_petugas", s="positive"), _t("kebersihan", s="negative")),
        ),
        Example(
            "Ancaman viral", 1, "Kalau tidak segera diperbaiki saya akan viralkan di media sosial.", ("negative",), flags=("risiko_viral",),
        ),
    ),
}

REPLY_EXAMPLES: dict[str, tuple[ReplyExample, ...]] = {
    "kesehatan": (
        ReplyExample("Pujian", "Terima kasih dokter dan perawatnya ramah sekali, pelayanan memuaskan.", "preset", ("terima_kasih_pujian",)),
        ReplyExample("Antre lama", "Antre pendaftaran hampir tiga jam dan tidak ada informasi yang jelas.", "preset", ("mohon_maaf_waktu_tunggu",)),
        ReplyExample("Petugas judes", "Petugas pendaftarannya judes dan menjawab dengan ketus.", "preset", ("mohon_maaf_pelayanan_petugas",)),
        ReplyExample("Toilet kotor, AC mati", "Toilet kotor dan AC mati di ruang tunggu.", "preset", ("mohon_maaf_kebersihan_fasilitas",)),
        ReplyExample("Tagihan membengkak", "Tagihan membengkak dan kasirnya tidak mau menjelaskan rinciannya.", "preset", ("mohon_maaf_tagihan",)),
        ReplyExample("Saran ringan", "Sebaiknya tambah kursi di ruang tunggu supaya lebih nyaman.", "preset", ("terima_kasih_masukan",)),
        ReplyExample("Salah obat", "Anak saya salah diberi obat oleh perawat dan hampir celaka.", "escalate", flags=("keselamatan_pasien",)),
    ),
    "spbu": (
        ReplyExample("Pujian", "Pelayanannya cepat dan petugasnya ramah, terima kasih.", "preset", ("terima_kasih_pujian",)),
        ReplyExample("Takaran kurang", "Takaran bensin kurang, isi 10 liter tapi rasanya cuma 9.", "preset", ("mohon_maaf_takaran_bbm",)),
        ReplyExample("BBM habis", "Pertamax habis terus setiap saya datang.", "preset", ("mohon_maaf_ketersediaan_bbm",)),
        ReplyExample("QRIS gagal", "Bayar pakai QRIS selalu gagal dan akhirnya harus bayar tunai.", "preset", ("mohon_maaf_pembayaran_digital",)),
        ReplyExample("Merokok dekat pompa", "Ada orang merokok dekat pompa dan hampir terjadi kebakaran.", "escalate", flags=("risiko_kebakaran",)),
    ),
    "asuransi": (
        ReplyExample("Pujian", "Prosesnya mudah dan agennya sangat membantu, terima kasih.", "preset", ("terima_kasih_pujian",)),
        ReplyExample("Klaim belum cair", "Klaim saya belum cair setelah dua bulan menunggu.", "preset", ("mohon_maaf_penanganan_klaim",)),
        ReplyExample("Saran kanal", "Sebaiknya tambah kanal WhatsApp untuk menanyakan status klaim.", "preset", ("terima_kasih_masukan",)),
    ),
    "kuliner": (
        ReplyExample("Pujian", "Makanannya enak dan pelayanannya cepat, terima kasih.", "preset", ("terima_kasih_pujian", "terima_kasih_pujian_suasana")),
        ReplyExample("Menu habis", "Menu andalan habis padahal baru jam 7 malam.", "preset", ("mohon_maaf_menu_habis",)),
        ReplyExample("Suasana nyaman", "Suasananya cozy banget buat nongkrong bareng teman.", "preset", ("terima_kasih_pujian_suasana",)),
        ReplyExample("Dugaan keracunan", "Setelah makan di sini anak saya muntah-muntah, kayaknya keracunan makanan.", "escalate", flags=("keamanan_pangan",)),
    ),
    "telekomunikasi": (
        ReplyExample("Pujian", "Layanannya memuaskan dan petugasnya ramah, terima kasih.", "preset", ("terima_kasih_pujian",)),
        ReplyExample("Internet putus", "Internet sering putus-putus selama seminggu ini.", "preset", ("mohon_maaf_gangguan_jaringan",)),
        ReplyExample("Teknisi tidak datang", "Teknisi janji datang kemarin tapi tidak muncul sama sekali.", "preset", ("mohon_maaf_kunjungan_teknisi",)),
    ),
    "layanan_publik": (
        ReplyExample("Pujian", "Pengurusannya cepat dan petugasnya ramah, terima kasih.", "preset", ("terima_kasih_pujian",)),
        ReplyExample("Prosedur berbelit", "Prosedurnya berbelit-belit, saya disuruh bolak-balik berkali-kali.", "preset", ("mohon_maaf_prosedur_birokrasi",)),
        ReplyExample("Saran", "Sebaiknya papan informasi persyaratan dibuat lebih besar.", "preset", ("terima_kasih_masukan",)),
    ),
    "lapangan_udara": (
        ReplyExample("Pujian", "Petugasnya ramah dan tempatnya rapi, terima kasih.", "preset", ("terima_kasih_pujian",)),
        ReplyExample("Prosedur masuk", "Bagaimana cara masuk untuk melihat pesawat? Prosedurnya tidak jelas.", "preset", ("informasi_prosedur_akses",)),
        ReplyExample("Drone dekat landasan", "Ada drone terbang rendah dekat landasan dan tidak ada yang menegur, sangat membahayakan penerbangan.", "escalate", flags=("keselamatan_penerbangan",)),
    ),
    "umum": (
        ReplyExample("Pujian", "Pelayanan memuaskan, terima kasih.", "preset", ("terima_kasih_pujian",)),
        ReplyExample("Antre lama", "Antre lama sekali, hampir satu jam menunggu.", "preset", ("mohon_maaf_waktu_tunggu",)),
        ReplyExample("Petugas cuek", "Petugasnya cuek dan tidak mau membantu.", "preset", ("mohon_maaf_pelayanan_petugas",)),
    ),
}
