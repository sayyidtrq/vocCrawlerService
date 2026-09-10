# Prompt: Generate Detailed Implementation Plan per Task (≤5MD)

> Paste prompt di bawah ini ke Claude Code (Fable 5) yang dibuka di project ini.
> Tujuan: menghasilkan implementation plan detail per task yang bisa langsung dipakai sebagai instruksi kerja dev.

---

```txt
Kamu adalah senior engineer yang bertugas menyusun IMPLEMENTATION PLAN detail untuk proyek integrasi Voice of Customer System × OneBox. Plan yang kamu buat akan dipakai sebagai INSTRUKSI KERJA developer (intern) — jadi harus konkret, bisa dieksekusi langkah demi langkah, dan tidak berasumsi pembaca hafal codebase.

## KONTEKS WAJIB DIBACA DULU (urut)

1. C:\Users\sayyi\Documents\project\hermina_crawler\markdowns\00-start-here\MUST_READ.md  ← naming & boundary rules, ini yang menang kalau konflik
2. C:\Users\sayyi\Documents\project\hermina_crawler\markdowns\08-agent-prompts-and-handoffs\two_agents_workflow.md  ← pembagian peran, phase plan, field mapping awal
3. C:\Users\sayyi\Documents\project\hermina_crawler\markdowns\01-product-and-backlog\task-breakdowns\tasklist-draft.md  ← daftar task RI-01..RI-17 (sumber utama)
4. C:\Users\sayyi\Documents\project\hermina_crawler\markdowns\99-legacy-reference\developer_guide.md  ← cara ngoding di OneCloud (MVC, git, best practice)
5. C:\Users\sayyi\Documents\project\hermina_crawler\markdowns\03-architecture\crawler-system\dfd.md + erd.md  ← rancangan VoC System & integrasi
6. C:\Users\sayyi\Documents\project\hermina_crawler\markdowns\03-architecture\onebox-system\dfd.md + erd.md  ← peta domain OneBox

## FAKTA KUNCI (jangan dilanggar)

- Naming: "Voice of Customer System" (VoC). Class: VoiceOfCustomerSystemClient, VoiceOfCustomerSystemTask. JANGAN pakai nama lama.
- Keputusan lead (terkunci): data review di-persist ke tabel Ticket existing OneBox, lewat/menyerupai modul Mediamonitoring; UI = dashboard VOC; ingest meniru pola SonarTask.
- Codebase OneBox: WSL, akses via \\wsl.localhost\Ubuntu22.04-Swoole\var\www\html\onecloud\onecloud (app PHP asli di subfolder onecloud/onecloud). Stack: Phalcon 5.9 + PHP 8.4 + Swoole + Volt + MySQL. Multi-tenant via SiteId — SEMUA query/insert wajib scoped SiteId.
- Codebase VoC System: C:\Users\sayyi\Documents\project\hermina_crawler (FastAPI + SQLAlchemy, models di app/db/models.py).
- Pattern rujukan di OneBox: app/library/CiptalifeApi.php (external REST client), app/tasks/SonarTask.php (ingest API eksternal → dedup RemoteId → new Ticket), app/models/Ticket.php, app/controllers/MediamonitoringController.php + app/views/Mediamonitoring/*.
- Git: feature branch dari develop, format feature/DNGO19-xxxx_Deskripsi. JANGAN kerja di hotfix/1.118.1. JANGAN commit .env, .env.local, app/config/development.php, app/config/local.php.
- JANGAN hardcode credential; config via per-environment config OneBox.

## TUGASMU

Buat implementation plan SATU TASK PER DOKUMEN untuk task-task di tasklist(draft).md, mulai dari urutan MVP: RI-01 → RI-03 → RI-04 → RI-05 → RI-06 → RI-07 → RI-08 → RI-10 → RI-11 → RI-12 → RI-15 (sisanya belakangan).

ATURAN KERJA:
1. Kerjakan SATU task dulu (mulai RI-01). Setelah selesai satu dokumen, BERHENTI dan minta saya review sebelum lanjut ke task berikutnya.
2. SEBELUM menulis plan, VERIFIKASI dulu ke codebase asli (read-only): buka file pattern yang relevan di WSL/lokal, pastikan nama file/method/kolom yang kamu tulis benar-benar ada. Jangan menulis instruksi berdasarkan ingatan/asumsi.
3. Tandai setiap klaim penting dengan status: [verified] (sudah dicek ke file), [assumption] (perlu dicek), [blocked] (butuh keputusan lead/Codex). Plan yang bagus punya banyak [verified] dan sedikit [assumption].
4. Kalau saat verifikasi kamu menemukan fakta yang bertentangan dengan tasklist/dokumen, JANGAN diam-diam menyesuaikan — tulis di bagian "Temuan & Deviasi" dan tanya saya.
5. Kalau task butuh API yang belum ada di VoC System, catat sebagai "API Gap (handoff ke Codex)" — jangan rancang perubahan OneBox untuk menambalnya.

FORMAT SETIAP DOKUMEN (simpan di C:\Users\sayyi\Documents\project\hermina_crawler\markdowns\04-implementation-plans\onebox\implementation-plan-onebox\RI-XX_nama-task.md):

# RI-XX — [Nama Task] (≤X MD)
1. **Tujuan & Definition of Done** — apa yang harus terjadi supaya task dianggap selesai (ambil dari tasklist, perjelas).
2. **Prasyarat & Dependency** — task/keputusan yang harus beres dulu; branch git yang dipakai.
3. **File Target** — daftar exact path file yang dibuat/diubah, dengan status [baru]/[ubah]/[baca-saja].
4. **Langkah Implementasi** — step-by-step bernomor, tiap step: apa yang dilakukan, di file mana, dengan skeleton/contoh kode yang meniru pattern existing (sebut file pattern-nya). Sertakan penanda SiteId-scoping di tiap query.
5. **Cara Verifikasi/Test Manual** — command konkret (di WSL) + expected result, termasuk kasus rerun/idempotency kalau relevan.
6. **Risiko & Rollback** — apa yang bisa salah, cara mundurnya.
7. **Temuan & Deviasi** — hasil verifikasi codebase yang mengubah/menguatkan rencana.
8. **API Gap / Handoff ke Codex** — kalau ada.
9. **Estimasi breakdown** — pecahan hari (mis. hari 1: X, hari 2: Y) supaya intern bisa pace diri.

Bahasa: Indonesia santai-teknis (gaya dokumen existing). Panjang per dokumen: secukupnya untuk bisa dieksekusi tanpa nanya — bukan sepanjang mungkin.

Mulai sekarang dengan RI-01 (Field mapping review VoC → Ticket/Message): verifikasi dulu kolom-kolom nyata di app/models/Ticket.php, Message.php, MessageContent.php, MessageUser.php, Contact.php di OneBox WSL dan field response /api/reviews di app/db/models.py + router VoC System, baru tulis tabel mapping-nya.
```

---

## Catatan pemakaian

- Jalankan di Claude Code yang dibuka di folder project ini (butuh akses WSL + file lokal).
- Satu dokumen per task → review → baru suruh lanjut ("lanjut RI-03"). Jangan minta semua sekaligus.
- Kalau ada keputusan baru dari Pak Agung, update MUST_READ.md / tasklist dulu, baru lanjutkan generate — biar plan berikutnya ikut keputusan terbaru.
