# PROMPT untuk Codex — Buktikan Crawl Berjalan (Key Process, tahap 3–5)

> Handoff dari agen OneBox (Claude Code) ke Codex (owner Voice of Customer System).
> Konteks lengkap: [PLAN_KEY_PROCESS_DEMO.md](../04-implementation-plans/key-process/PLAN_KEY_PROCESS_DEMO.md) · Otoritas: [ADR-0003](../02-meetings-and-decisions/adr/ADR-0003-crawl-execution-pull-queue.md)
> Tandai setiap klaim: **[verified] / [assumption] / [blocked]**.

## Konteks: apa yang SUDAH terbukti

Rantai OneBox → crawler **sudah jalan di dev** [verified 28 Jul 2026]:

```
docker compose exec api python -m scripts.refresh_worklist --company-id 3 --json
→ {"status":"synced","company_id":3,"site_id":169,"fetched":1,"upserted":1,"warning":null}
```

Artinya: user menambah cabang di OneBox → crawler menariknya sendiri → masuk cache VoC. Target yang masuk adalah **Hermina depok** dengan `external_place_id` dari worklist.

**Sekarang giliran bagian yang belum pernah dibuktikan sama sekali: crawl-nya sendiri.**

---

## X1 — GERBANG: buktikan crawl 1 target *(kerjakan ini dulu, sendirian)*

Jalankan crawl untuk target `Hermina depok` yang baru masuk lewat worklist.

**Yang wajib dilaporkan, apa pun hasilnya:**
1. Perintah persis yang dipakai
2. Apakah Selenium **butuh login Google**? Kalau ya: sekali saja, atau tiap run?
3. Berapa lama satu target selesai
4. Berapa review berhasil diambil
5. Kalau gagal — pesan errornya, dan di tahap mana

**Ini boleh gagal.** Kalau memang tidak bisa jalan tanpa GUI, **lapor apa adanya dan berhenti** — jangan akali dengan langkah manual yang tidak bisa diulang. Catatan lama menyebut *"Selenium mode tidak jalan di container, butuh manual Google login GUI"* [assumption — justru itu yang mau diverifikasi].

Alasannya penting: seluruh rencana antrean crawl & penjadwalan otomatis 3 window berdiri di atas asumsi bahwa crawl bisa berjalan tanpa manusia. Kalau asumsi itu salah, **arsitekturnya yang harus ditinjau**, bukan dipaksakan. Lebih murah ketahuan sekarang.

**Jangan lanjut X2–X5 sebelum X1 punya jawaban.**

---

## X2 — Review terikat ke target yang benar

Pastikan review hasil crawl tersimpan dengan **`location_id` milik target dari worklist**, bukan target lama.

- Kunci stabil lintas sistem tetap **`external_place_id`**.
- Verifikasi lewat query: review baru → `location_id` → cocok dengan lokasi hasil `refresh_worklist`.

Ini penting karena OneBox memetakan balik `location_id` VoC ke `Location` OneBox. Salah di sini, tiket muncul sebagai cabang **"Unknown"**.

## X3 — Analisa AI untuk review baru

Jalankan analisa untuk review hasil crawl. Tiap review harus punya **sentimen, urgensi, kategori**.

- Kategori memakai slug enum yang sudah disepakati (`doctor_service`, `waiting_time`, dst) — OneBox memetakannya ke `Category.Remarks`.
- **Laporkan `tokens_used`** (ADR-0002: metering dikendalikan OneBox).
- ⚠️ Catatan lama: pernah **seluruh** hasil analisa jatuh ke `doctor_service` karena prompt kurang diskriminatif [assumption — cek ulang sebelum demo, hasil seragam akan terlihat jelas di dashboard].

## X4 — Review baru terbaca lewat kontrak integrasi

Pastikan `GET /api/integration/v1/reviews` mengembalikan review hasil crawl, dan cursor maju dengan benar.

- OneBox menarik secara **delta** memakai `checkpoint_cursor`.
- ⚠️ **Jebakan:** kalau checkpoint OneBox sudah maju, review bertanggal lama dari lokasi baru bisa terlewat. Pastikan `updated_since`/`location_id` bisa dipakai untuk **backfill bertarget** satu lokasi.

## X5 — Pemicu crawl yang bisa dipanggil dari luar

Sediakan CLI/endpoint untuk memicu crawl satu atau beberapa target.

- **Wajib non-blocking**: balas segera, jangan menahan pemanggil selama Selenium bekerja (ADR-0003 D2). OneBox berjalan di Swoole dengan worker terbatas — panggilan panjang akan menahan worker dan membuat aplikasi tidak responsif untuk semua user.
- Balikan minimal: identitas batch + status.
- Sediakan cara menanyakan status/riwayat batch.

---

## Aturan yang berlaku

- Jangan hardcode / commit / mencetak kredensial ke log.
- Jangan membuat penjadwal window sendiri — pemilik penjadwalan tetap OneBox (RI-08).
- Review kompetitor **tidak** didorong ke jalur integration reviews OneBox.
- `company_id` selalu dari service identity, tidak pernah dari request.

## Definition of Done

- [ ] X1 terjawab: crawl berhasil, **atau** kegagalan terdokumentasi beserta sebabnya
- [ ] Review baru terikat ke `location_id` yang benar
- [ ] Tiap review punya sentimen, urgensi, kategori; `tokens_used` dilaporkan
- [ ] Review baru terbaca lewat `/api/integration/v1/reviews`, cursor benar
- [ ] Ada pemicu crawl non-blocking beserta cara cek statusnya

## Yang dikerjakan agen OneBox secara paralel

Membenahi Connection VoC di dev (`Url`, `api_mode`, `service_token`, `company_id`) supaya OneBox bisa menarik review hasil crawl. Tidak saling menunggu dengan X1.

**Titik temu:** setelah X4 selesai, kabari agen OneBox untuk menjalankan ingest di dev dan memverifikasi review menjadi Ticket.
