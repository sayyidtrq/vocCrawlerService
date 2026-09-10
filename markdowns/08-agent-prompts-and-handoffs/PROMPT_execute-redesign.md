# Prompt: Eksekusi Redesign (ADR-0001 + ADR-0002) — URGENT

> Paste blok `txt` di bawah ke Claude Code yang dibuka di project ini.

```txt
URGENT: eksekusi redesign arsitektur. Sistem sudah diimplementasikan sampai RI-07 di atas asumsi yang SALAH. Tugasmu memperbaikinya sesuai ADR, bukan membangun fitur baru.

## BACA DULU (urut, ADR adalah otoritas tertinggi)
1. markdowns/00-start-here/MUST_READ.md — lihat bagian ADR + daftar dokumen yang TIDAK BERLAKU
2. markdowns/02-meetings-and-decisions/adr/ADR-0001-ownership-inversion.md
3. markdowns/02-meetings-and-decisions/adr/ADR-0002-ai-execution-split.md
4. markdowns/04-implementation-plans/onebox/implementation-plan-onebox/RI-02_keputusan-arsitektur.md (perhatikan banner: D2/D6 batal, D10 direvisi)
5. markdowns/04-implementation-plans/onebox/implementation-plan-onebox/LABELING_rule-first-strategy.md (D11 masih berlaku)

Kalau dokumen lain bertentangan dengan ADR, ADR yang menang. Dokumen berbanner SUPERSEDED JANGAN dijadikan acuan.

## INTI PERUBAHAN
Sebelum: VoC memiliki Location/Competitor/Company/User + FE sendiri. OneBox mereferensi ID milik VoC (Connection.TargetId = location_id VoC). Tambah 1 lokasi = kerja manual di 2 sistem.

Sesudah: OneBox = System of Record untuk SEMUA modul VoC kecuali scraping. VoC = crawler engine headless. User HANYA menyentuh OneBox; OneBox auto-provisioning ke VoC lewat API.

## KODE YANG SUDAH ADA (jangan dibuang, diperbaiki)
- app/services/Provider/VocProvider.php  — receive(), cursor di Options._sync_cursor, assertTenant() cek Options.company_id, TargetId = location_id VoC
- app/library/VoiceOfCustomerSystemClient.php — health/login/getReviews/getIntegrationReviews/fetchPage. BELUM ada method tulis (create location) → perlu ditambah.
- app/controllers/VocController.php — index/dashboard/reviews/locations/competitors/fetchjobs/analysis + syncnowAction (POST, pakai messaging->receiveConnectionById). locationsDataAction saat ini HANYA agregat dari review, bukan CRUD.
- app/views/Voc/*.volt
- app/tasks/VoiceOfCustomerSystemTask.php

## MEKANISME ONEBOX YANG WAJIB DIPAKAI (jangan bikin sendiri)
- Benefit/entitlement: Benefit (Code) + SiteBenefit (Amount/MaxAmount/Quantity/MaxQuantity/ExpireDate) + BenefitService::hasBenefit/verifyBenefit($code,$qty)/addUsage($code,$value). UI kelola: PackageController.
  ⚠️ VERIFIKASI DULU: BenefitService::__construct($common,$jwt) mengambil site dari JWT — cek apakah bekerja di konteks web session (VocController). Kalau tidak, laporkan sebagai blocker sebelum memakainya.
- Scheduler: GatewayTask::scheduleAction → Gateway::schedule → messaging->queueConnections(). Provider terdaftar sebagai Connection otomatis terjadwal. JANGAN bikin scheduler baru.
- Labeling: Service\Ruling (Rule.Conditions/Actions JSON per SiteId) dipanggil otomatis oleh Ticketing::addTicket. JANGAN panggil AI untuk klasifikasi kategori/prioritas.
- VoC endpoint tulis yang SUDAH ADA: POST /api/locations, PUT update, POST toggle-active, DELETE (apps/api/app_api/routers/locations.py).

## URUTAN EKSEKUSI (satu per satu, BERHENTI dan lapor setiap selesai satu nomor)

T1. VERIFIKASI & RENCANA (belum menulis kode)
    - Konfirmasi struktur Connection.Options milik Connection VoC yang ada sekarang.
    - Konfirmasi apakah BenefitService bekerja di web session (risiko JWT di atas).
    - Konfirmasi kontrak POST /api/locations di VoC (field wajib, response).
    - Output: daftar file yang akan dibuat/diubah + alasan. Tunggu persetujuan.

T2. CRUD Location di OneBox
    - VocController: tambah action list/create/update/delete Location (JSON, POST untuk yang mengubah).
    - View locations.volt: dari agregat menjadi halaman kelola (tabel + form).
    - Simpan master lokasi di OneBox. Tentukan penyimpanannya saat T1 (JANGAN migration sebelum disetujui).

T3. Auto-provisioning Location → VoC
    - VoiceOfCustomerSystemClient: tambah createLocation()/updateLocation()/deleteLocation().
    - Saat simpan lokasi di OneBox: panggil VoC → terima location_id → auto-create/update Connection (TargetId=location_id, Options.company_id, credential, Enabled=1).
    - Wajib: retry + simpan status provisioning di sisi OneBox. Kalau VoC gagal, lokasi tetap tersimpan di OneBox dengan status "belum tersinkron" — jangan gagal senyap.

T4. CRUD Competitor + auto-provisioning (pola sama dengan T2+T3)

T5. Parameter & Benefit
    - Daftarkan Benefit code: VOC_SCRAPE, VOC_AI, VOC_COMPETITOR.
    - Simpan parameter AI (ai_enabled, model, prompt_version, threshold) di Connection.Options.
    - Panggil verifyBenefit() sebelum crawl/analisa, addUsage() sesudah.
    - Kelola lewat PackageController existing — JANGAN bikin UI benefit baru.

T6. Kontrak AI (ADR-0002)
    - Kirim parameter AI dalam request ke VoC.
    - Terima tokens_used dari response → addUsage('VOC_AI', tokens).
    - Kalau endpoint VoC belum menerima parameter/mengembalikan tokens_used → CATAT sebagai "API Gap (handoff Codex)", JANGAN tambal di OneBox.

## GUARDRAIL
- Semua query/insert WAJIB scoped SiteId.
- Jangan hardcode credential — simpan di Connection.Options.
- Jangan commit .env, .env.local, app/config/development.php, app/config/local.php.
- Jangan migration tanpa persetujuan eksplisit.
- Jangan memindahkan logic scraping/Selenium ke OneBox.
- Jangan menghapus kode VoC yang jadi dead code (FE Next.js, auth user) — cukup keluarkan dari alur produksi dan catat.
- Branch: feature/DNGO19-3346_Media-Crawler-Google-Business-Review.
- Teks review = konten publik tak terpercaya → escape di view.

## CARA KERJA
1. Verifikasi ke kode sebelum menulis. Tandai klaim: [verified] / [assumption] / [blocked].
2. Satu task (T#) selesai → BERHENTI → lapor → tunggu persetujuan.
3. Sebelum mengubah file: sebutkan path, alasan, ringkasan perubahan.
4. Menemukan fakta yang bertentangan dengan ADR → laporkan sebagai "Temuan & Deviasi", jangan diam-diam menyesuaikan.
5. Setiap selesai T#, update ADR/dokumen terkait kalau ada keputusan baru.

Mulai dari T1. Jangan menulis kode sebelum T1 disetujui.
```

---

## Catatan
- ADR-0001 & ADR-0002 **belum diratifikasi Pak Agung** — ini mengubah asumsi RI-06 & RI-02 (D2/D6/D10). Bawa ke dia paralel dengan eksekusi.
- Urutan T2→T3 sengaja: bikin CRUD dulu di OneBox, baru sambungkan ke VoC. Supaya kalau VoC bermasalah, UI-nya sudah bisa didemokan.
