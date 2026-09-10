# ADR-0002 — AI Analysis: Kendali di OneBox, Eksekusi di VoC

- **Status:** Accepted
- **Tanggal:** 2026-07-21
- **Pengambil keputusan:** Sayyid (dev) — ⚠️ belum diratifikasi Pak Agung
- **Terkait:** [ADR-0001](ADR-0001-ownership-inversion.md) · `implementation-plan-onebox/LABELING_rule-first-strategy.md` (D11)

---

## Context

[ADR-0001](ADR-0001-ownership-inversion.md) menetapkan seluruh modul VoC dikonfigurasi di OneBox. Pertanyaan yang tersisa: **AI analysis dieksekusi di mana?**

Fakta terverifikasi:
- **VoC (Python)** sudah punya AI jalan: `analysis_service` + client `gemini` / `openrouter` / `local_llm` / `mock`.
- **OneBox (PHP)** juga punya AI libs produksi: `Library\OpenAi.php`, `Chatgpt.php`, `OpenAiAssistant.php`, `OpenAiResponse.php` — sudah dipakai (mis. SonarTask).
- **OneBox punya metering**: `BenefitService::verifyBenefit($code,$qty)` + `addUsage($code,$value)`, dengan `SiteBenefit.MaxQuantity` sebagai kuota.
- **D11 (rule-first)** sudah memindahkan sebagian besar *klasifikasi* ke `Service\Ruling` di OneBox — **tanpa AI**.

---

## Decision

**Split: parameter & kuota AI dikendalikan OneBox, eksekusi AI tetap di VoC.**

```
OneBox  ── simpan config AI (model, prompt version, threshold, on/off, kuota)
        ── kirim parameter itu dalam request crawl/analisa
                    ↓
VoC     ── eksekusi AI PAKAI parameter yang dikirim
        ── balikan: hasil analisa + JUMLAH TOKEN TERPAKAI
                    ↓
OneBox  ── catat pemakaian: BenefitService::addUsage('VOC_AI', tokens)
```

### Pembagian tegas

| Aspek | Pemilik |
|---|---|
| AI on/off per site | **OneBox** (`Benefit` `VOC_AI`) |
| Pilihan model | **OneBox** (`Connection.Options`) |
| Prompt version | **OneBox** |
| Threshold (mis. hanya rating ≤3 yang dianalisa) | **OneBox** |
| Kuota & metering token | **OneBox** (`SiteBenefit` + `addUsage`) |
| Pemanggilan LLM | **VoC** |
| Pelaporan token terpakai | **VoC** (wajib dikembalikan) |
| Klasifikasi kategori/prioritas | **OneBox** (rules `Ruling`, bukan AI) |

---

## Alternatif yang dipertimbangkan

### Opsi 1 — AI sepenuhnya di VoC (status quo)
✅ Sudah jalan · ekosistem Python kuat · satu pass dengan scraping · kerja lambat jauh dari Swoole
❌ Config AI di luar OneBox (melanggar ADR-0001) · kuota tidak terhubung `Benefit` · analisa ulang harus lewat VoC

### Opsi 2 — AI sepenuhnya di OneBox
✅ Config satu tempat · libs sudah ada · **bisa dipakai lintas modul** (news/chat/ticket) · metering native · bisa re-analisa Ticket lama
❌ Tooling LLM PHP lebih lemah · panggilan AI panjang di Swoole worker berisiko blocking · **membuang kerja VoC yang sudah jadi** · latency ekstra

### Opsi 3 — Split ← **DIPILIH**
✅ Memenuhi "semua di-setup di OneBox" **tanpa porting kode AI** · tetap pakai Python · metering di OneBox · perubahan paling kecil
❌ Kontrak API harus membawa parameter AI · VoC wajib melaporkan token usage

---

## Consequences

### Positif
1. Tidak ada porting kode AI — hemat waktu besar.
2. Kuota AI ikut mekanisme komersial OneBox yang sudah ada.
3. Ganti model/prompt = ubah konfigurasi di OneBox, **tanpa deploy VoC**.

### Negatif
1. **API gap (handoff Codex):** endpoint crawl/analisa harus menerima parameter AI dan mengembalikan `tokens_used`.
2. Perlu kesepakatan nama parameter di dua sisi.
3. Kalau VoC tidak melaporkan token, metering jadi tebakan.

### Batas yang disepakati
- **Jangan** duplikasi logika AI di OneBox. OneBox tidak memanggil LLM untuk review.
- **Jangan** menyimpan prompt di VoC sebagai sumber kebenaran — VoC hanya menerima.

---

## API Gap → handoff ke Codex

1. Endpoint crawl/analisa menerima parameter: `ai_enabled`, `model`, `prompt_version`, `threshold` (mis. `min_rating`, `max_rating`).
2. Response menyertakan `tokens_used` (prompt + completion) per batch.
3. Opsional: `analysis_skipped_count` supaya OneBox tahu berapa yang sengaja tidak dianalisa.

---

## Tindak lanjut
1. Sepakati nama parameter dengan Codex, tulis di kontrak API.
2. OneBox: registrasi Benefit `VOC_AI` + simpan parameter di `Connection.Options`.
3. OneBox: panggil `verifyBenefit('VOC_AI', n)` sebelum minta analisa, `addUsage('VOC_AI', tokens)` sesudah.
