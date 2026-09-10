# Prompt: Implementation Plan VoC Crawler System (Maksimal 5 MD per Task)

> Prompt ini digunakan di Codex yang dibuka pada repository VoC Crawler System.
> Tujuannya adalah menghasilkan implementation plan sisi Crawler System yang setara detailnya dengan plan OneBox, tetapi tetap mengikuti ownership dan boundary masing-masing sistem.

---

```txt
Anda adalah Senior Backend Engineer dan Integration Architect yang bertugas menyusun IMPLEMENTATION PLAN detail untuk sisi Voice of Customer (VoC) Crawler System pada integrasi dengan OneBox.

Dokumen yang Anda hasilkan akan menjadi panduan kerja developer. Karena itu, setiap rencana harus grounded ke codebase, mempunyai file target yang nyata, langkah implementasi yang konkret, cara pengujian yang dapat dijalankan, serta estimasi maksimal 5 man-day (5 MD) per task.

TUGAS INI HANYA MENYUSUN IMPLEMENTATION PLAN. Jangan mengimplementasikan perubahan aplikasi pada tahap ini.

======================================================================
1. TUJUAN UTAMA
======================================================================

Buat satu paket implementation plan untuk sisi VoC Crawler System yang memastikan OneBox dapat:

1. melakukan autentikasi sebagai machine/service;
2. menarik review melalui kontrak API yang stabil;
3. menarik perubahan secara incremental tanpa kehilangan atau menggandakan data;
4. menerima review dan hasil AI analysis dengan tenant scope yang benar;
5. menangani pagination, retry, timeout, dan kegagalan dengan perilaku yang terdokumentasi;
6. menguji alur pull OneBox tanpa harus menunggu seluruh UI OneBox selesai;
7. menjalankan integrasi pada environment Docker/staging dengan runbook yang jelas.

Output akhir harus berupa INDEX dan beberapa dokumen task. Setiap task wajib <= 5 MD. Jika sebuah task diperkirakan lebih dari 5 MD, pecah menjadi dua atau lebih task yang independen dan dapat diverifikasi.

======================================================================
1A. MANDAT PENGAMBILAN KEPUTUSAN
======================================================================

Anda adalah decision maker teknis untuk scope VoC Crawler System. Jangan berhenti untuk meminta review, approval, atau pilihan dari user selama keputusan tersebut dapat ditentukan melalui codebase, kebutuhan integrasi, security practice, dan trade-off engineering.

Aturan pengambilan keputusan:

1. Jika ada beberapa opsi teknis, analisis singkat berdasarkan keamanan, kesederhanaan, backward compatibility, operability, dan biaya implementasi.
2. Pilih SATU opsi terbaik sebagai keputusan final/rekomendasi utama. Jangan hanya menyajikan daftar alternatif tanpa keputusan.
3. Masukkan keputusan tersebut langsung ke implementation plan beserta alasan dan konsekuensinya.
4. Jangan menulis "perlu review user", "menunggu persetujuan user", atau "silakan pilih opsi A/B/C" untuk keputusan teknis.
5. Lakukan self-review dan cross-check sendiri sebelum memberi status ready.
6. Gunakan [blocked] hanya jika pekerjaan benar-benar membutuhkan credential/secret, akses eksternal, informasi kontrak OneBox yang tidak dapat ditemukan, atau keputusan bisnis murni yang mengubah perilaku produk, legal, biaya, maupun ownership organisasi.
7. Jika ada blocker eksternal, tetap selesaikan seluruh bagian plan yang bisa diputuskan dan berikan recommended default.
8. User tidak menjadi reviewer wajib pada tahap penyusunan plan. Hasil harus sudah berupa rekomendasi engineer yang siap dijalankan.

======================================================================
1B. DEFAULT ARSITEKTUR YANG DIREKOMENDASIKAN
======================================================================

Gunakan keputusan berikut sebagai default terbaik untuk MVP. Verifikasi kompatibilitasnya ke codebase. Anda boleh menyimpang hanya jika menemukan bukti teknis kuat; penyimpangan wajib dicatat pada Temuan dan Deviasi dengan keputusan pengganti yang final.

1. Buat endpoint integrasi terpisah dan versioned dengan candidate default GET /api/integration/v1/reviews. Pertahankan GET /api/reviews untuk FE existing.
2. Gunakan opaque service token pada header Authorization: Bearer <service-token>. Simpan hanya hash token. Setiap API client terikat ke satu company_id dan memiliki status active, expires_at, last_used_at, created_at, serta revoked_at. Raw token hanya ditampilkan sekali saat issuance.
3. company_id selalu berasal dari API client identity yang tervalidasi, bukan query parameter bebas.
4. Delta sync menggunakan opaque keyset cursor dengan pasangan sync_updated_at + review_id. Offset pagination bukan mekanisme sinkronisasi utama.
5. Gunakan sync_updated_at pada Review sebagai integration watermark terdenormalisasi. Nilainya berubah saat review berubah dan saat latest ReviewAnalysis dibuat/diperbarui. Ini menjadi default MVP karena mudah diindeks dan aman untuk late analysis.
6. Gunakan UNIQUE(company_id, review_hash). external_review_id tetap dikirim bila tersedia, sedangkan review_hash menjadi canonical fingerprint yang selalu tersedia.
7. Payload integrasi tidak mengekspos raw_payload, raw model response, credential, atau data debugging.
8. Contract integrasi bersifat additive dan memiliki fixture deterministik. Breaking change memakai versi endpoint baru.
9. Error response memiliki code stabil, message aman, request_id, dan detail validasi yang tidak membocorkan secret.
10. Semua keputusan ini ditulis sebagai keputusan final pada 00_INDEX.md, bukan daftar pertanyaan untuk user.

======================================================================
2. SYSTEM BOUNDARY DAN OWNERSHIP
======================================================================

Scope milik Anda, yaitu VoC Crawler System:

- FastAPI routes dan dependency;
- Pydantic request/response schema;
- service layer dan query SQLAlchemy;
- model database dan Alembic migration;
- service-to-service authentication;
- tenant isolation berbasis company_id;
- review API contract;
- delta sync, ordering, dan pagination;
- fixture/mock response untuk OneBox;
- integration test dan contract test;
- logging, health check, metrics minimum, dan error contract;
- konfigurasi Docker dan deployment readiness sisi Crawler System;
- dokumentasi handoff API ke developer OneBox.

Di luar scope Anda, jangan dijadikan file target perubahan:

- app/library/VoiceOfCustomerSystemClient.php di OneBox;
- app/tasks/VoiceOfCustomerSystemTask.php di OneBox;
- Ticket, Message, MessageContent, MessageUser, Contact, atau Reference OneBox;
- MediamonitoringController, Volt UI, dashboard VOC OneBox, menu, dan role;
- scheduler internal OneBox;
- pemindahan Selenium atau crawling logic ke OneBox.

Dokumen OneBox boleh dibaca sebagai consumer requirement dan dependency. Jangan menulis langkah implementasi PHP/Phalcon di paket plan Crawler System.

Flow integrasi yang dipakai:

Google/Review Source
  -> VoC Crawler System: crawl + normalize + dedup + AI analysis + persist
  -> REST API VoC Crawler System
  -> OneBox melakukan pull
  -> OneBox melakukan mapping dan ingestion ke Ticket/Message
  -> dashboard VOC OneBox

======================================================================
3. DOKUMEN DAN CODEBASE WAJIB DIBACA
======================================================================

Baca berurutan sebelum membuat plan:

1. markdowns/00-start-here/MUST_READ.md
2. markdowns/08-agent-prompts-and-handoffs/two_agents_workflow.md
3. markdowns/01-product-and-backlog/task-breakdowns/tasklist-draft.md
4. markdowns/03-architecture/integration/architecture_diagram.md
5. markdowns/03-architecture/crawler-system/dfd.md
6. markdowns/03-architecture/crawler-system/erd.md
7. markdowns/04-implementation-plans/onebox/implementation-plan-onebox/00_INDEX.md
8. markdowns/04-implementation-plans/onebox/implementation-plan-onebox/RI-01_field-mapping.md
9. markdowns/04-implementation-plans/onebox/implementation-plan-onebox/RI-03_kesiapan-api-voc.md
10. markdowns/04-implementation-plans/onebox/implementation-plan-onebox/RI-04_client.md
11. markdowns/04-implementation-plans/onebox/implementation-plan-onebox/RI-05_ingest-task.md
12. markdowns/04-implementation-plans/onebox/implementation-plan-onebox/RI-08_scheduler-delta.md
13. markdowns/04-implementation-plans/onebox/implementation-plan-onebox/RI-09_error-observability.md
14. markdowns/04-implementation-plans/onebox/implementation-plan-onebox/RI-16_integration-test.md

Lalu verifikasi langsung minimal file kode berikut:

- app/db/models.py
- app/db/session.py
- app/config.py
- app/services/review_service.py
- app/services/fetch_service.py
- app/services/analysis_service.py
- app/utils/hashing.py
- app/utils/logger.py
- apps/api/main.py
- apps/api/app_api/dependencies.py
- apps/api/app_api/schemas.py
- apps/api/app_api/serializers.py
- apps/api/app_api/errors.py
- apps/api/app_api/routers/auth.py
- apps/api/app_api/routers/reviews.py
- apps/api/app_api/routers/health.py
- tests/test_tenant_isolation.py
- tests/test_mvp.py
- tests/test_real_integrations.py
- seluruh Alembic migration yang relevan
- Dockerfile
- docker-compose.yml
- .env.example

Gunakan rg/rg --files untuk menemukan file tambahan. Jangan mengandalkan nama file dari prompt jika codebase sudah berubah.

Urutan source of truth jika terjadi konflik:

1. MUST_READ.md untuk naming, ownership, dan boundary;
2. codebase serta test aktual untuk kondisi existing;
3. keputusan arsitektur yang sudah disetujui pada dokumen integrasi;
4. implementation plan OneBox untuk kebutuhan consumer;
5. DFD/ERD draft untuk arah target;
6. dokumen lama hanya sebagai referensi historis.

Jika codebase bertentangan dengan dokumen, jangan menyesuaikan diam-diam. Catat pada bagian Temuan dan Deviasi.

======================================================================
4. BASELINE YANG WAJIB DIVERIFIKASI ULANG
======================================================================

Daftar berikut adalah hasil pembacaan awal, bukan izin untuk langsung dianggap final. Verifikasi ulang dan beri status [verified], [assumption], atau [blocked].

1. Review.updated_at sudah ada di app/db/models.py.
2. ReviewResponse belum mengekspos updated_at.
3. GET /api/reviews belum memiliki updated_since, updated_before, atau cursor.
4. Pagination existing masih page/page_size dengan offset.
5. Ordering existing menggunakan review_time/id, belum menggunakan integration watermark.
6. ReviewAnalysis memiliki created_at tetapi belum memiliki updated_at.
7. Menambahkan ReviewAnalysis belum tentu memperbarui Review.updated_at. Ini berisiko membuat hasil analisis terlambat tidak ikut delta sync.
8. Auth existing adalah JWT milik User melalui POST /api/auth/login, belum ada identity khusus service/API client.
9. ApiClient masih rancangan ERD dan belum tentu ada di model/migration aktual.
10. Tenant scope company_id sudah dipakai pada ReviewService dan memiliki test isolation dasar.
11. Review.review_hash terlihat unique secara global, sedangkan dedup service memeriksa company_id + review_hash. Ini harus diaudit karena contract dedup OneBox adalah SiteId + review_hash.
12. Raw payload bersifat sensitif/berisik dan tidak boleh otomatis masuk response integrasi tanpa keputusan eksplisit.
13. OneBox membutuhkan field review dan latest analysis dalam satu payload yang stabil.

Untuk setiap poin di atas:

- tunjukkan file dan simbol/method yang membuktikan statusnya;
- tentukan apakah menjadi task, subtask, risiko, atau tidak perlu diubah;
- jangan merancang migration sebelum membandingkan model dengan migration dan schema aktual.

======================================================================
5. PRINSIP DESAIN WAJIB
======================================================================

Semua plan harus mematuhi guardrail berikut:

1. Tenant-first
   - Semua query integrasi harus berasal dari identity yang sudah terikat ke company_id.
   - Consumer tidak boleh mengirim company_id bebas lalu membaca tenant lain.
   - Test negatif tenant leakage wajib ada.

2. Idempotent dan lossless
   - OneBox boleh mengulang request tanpa membuat sumber data berubah.
   - Delta sync tidak boleh kehilangan record yang memiliki timestamp sama.
   - Cursor atau watermark harus mempunyai tie-breaker stabil, misalnya timestamp + id.

3. Analysis-aware delta
   - Review yang sudah ada tetapi baru selesai dianalisis harus muncul kembali pada delta pull.
   - Jangan hanya memakai Review.updated_at jika perubahan ReviewAnalysis tidak memperbaruinya.
   - Plan harus membandingkan opsi sync_updated_at terdenormalisasi, event/outbox, atau query watermark gabungan. Pilih rekomendasi paling sederhana yang aman untuk MVP dan jelaskan trade-off.

4. Backward compatible
   - Pertahankan endpoint dan field existing jika masih dipakai FE.
   - Field tambahan harus additive.
   - Jika endpoint integrasi khusus lebih aman daripada mengubah endpoint user, jelaskan alasan dan migration path. Jangan mengada-adakan endpoint tanpa analisis.

5. Secure by configuration
   - Jangan hardcode password, API key, JWT secret, atau credential OneBox.
   - Secret wajib berasal dari environment/secret manager.
   - Tidak boleh ada fallback secret lemah pada non-local environment.
   - Log tidak boleh menyimpan token, API key, password, atau raw payload penuh.

6. Consumer-driven contract
   - Response harus memenuhi kebutuhan ingestion OneBox, bukan bentuk yang hanya nyaman untuk UI VoC.
   - Status HTTP, error body, pagination metadata, dan retry semantics harus jelas.
   - Tentukan field wajib, nullable, enum, format datetime, timezone, dan ordering.

7. Small, testable changes
   - Setiap task harus menghasilkan satu kemampuan yang bisa diuji.
   - Maksimal 5 MD per task termasuk implementasi, test, review, dan dokumentasi task tersebut.
   - Jangan memasukkan refactor besar yang tidak dibutuhkan integrasi.

======================================================================
6. STRUKTUR TASK AWAL
======================================================================

Gunakan task awal berikut sebagai baseline. Setelah audit codebase, Anda boleh memecah task, mengubah estimasi, atau menambah task bila ada gap nyata. Jangan menghapus kebutuhan tanpa alasan tertulis.

VOC-CS-01 - Baseline kontrak API dan integration fixture (<=3 MD)

- Inventaris field GET /api/reviews aktual.
- Tetapkan field required/nullable, enum, datetime ISO 8601, dan contoh response.
- Pastikan updated_at/sync field yang dibutuhkan consumer tersedia.
- Buat fixture sanitasi yang dapat dipakai OneBox untuk mock.
- Dokumentasikan compatibility policy.
- Handoff ke OneBox: RI-01, RI-03, RI-04, RI-05.

VOC-CS-02 - Delta sync dan pagination deterministik (<=5 MD)

- Rancang updated_since/cursor contract.
- Tangani record dengan timestamp sama menggunakan tie-breaker.
- Pastikan AI analysis yang selesai belakangan ikut tersinkron.
- Terapkan filter ke query data dan count secara konsisten.
- Definisikan next_cursor/has_more atau snapshot rule.
- Tambahkan index/migration hanya jika dibuktikan perlu.
- Handoff ke OneBox: RI-05 dan RI-08.

VOC-CS-03 - Service-to-service auth dan tenant binding (<=5 MD)

- Verifikasi bahwa opaque service token hashed dapat diterapkan tanpa merusak JWT user existing.
- Jadikan opaque service token per API client sebagai pilihan MVP utama; dokumentasikan alasan memilihnya dibanding service account user dan client-credential JWT.
- Identity wajib terikat ke company_id, bukan company_id dari query bebas.
- Rancang model/migration, issuance, revoke, rotate, expiry, dan audit minimum.
- Definisikan header dan contoh 401/403.
- Jika implementasi >5 MD, pecah menjadi foundation credential dan enforcement.
- Handoff ke OneBox: RI-02 dan RI-04.

VOC-CS-04 - Integritas tenant dan dedup review (<=4 MD)

- Audit constraint review_hash global vs company-scoped.
- Tetapkan canonical dedup key untuk VoC dan kontrak external_review_id/review_hash untuk OneBox.
- Rancang migration aman jika unique constraint perlu diubah.
- Tambahkan tenant isolation dan race-condition test.
- Jelaskan dampak data existing dan query cleanup sebelum migration.
- Handoff ke OneBox: RI-01, RI-05, RI-06.

VOC-CS-05 - Reliability, error contract, dan observability (<=4 MD)

- Definisikan timeout expectation, status retryable/non-retryable, dan error envelope.
- Tambahkan correlation/request ID pada log/response jika belum ada.
- Pastikan health endpoint membedakan liveness dan dependency readiness bila diperlukan.
- Redact secret dan raw payload.
- Tentukan log minimum untuk audit pull tanpa menyimpan data sensitif.
- Handoff ke OneBox: RI-04 dan RI-09.

VOC-CS-06 - Contract test dan simulasi pull OneBox (<=5 MD)

- Test auth service client.
- Test tenant isolation.
- Test initial pull, pagination, delta pull, same timestamp, late analysis, empty page, dan rerun.
- Test 401, 403, invalid cursor, timeout simulation, dan malformed parameter.
- Sediakan script/curl collection atau test client yang dapat dijalankan dari WSL OneBox.
- Gunakan fixture deterministik, tidak bergantung Google/Selenium live.
- Handoff ke OneBox: RI-03, RI-04, RI-05, RI-08, RI-16.

VOC-CS-07 - Deployment readiness dan integration runbook (<=3 MD)

- Daftar environment variable tanpa value secret.
- Urutan migration, deploy, smoke test, rollback, dan credential rotation.
- Verifikasi Docker health, network reachability, CORS relevance, dan base URL internal.
- Definisikan checklist staging dan evidence yang harus disimpan.
- Dokumentasikan ownership insiden Crawler System vs OneBox.
- Handoff ke OneBox: RI-16 dan RI-17.

Urutan rekomendasi:

Fase A - Contract foundation
VOC-CS-01 -> VOC-CS-02

Fase B - Security dan integrity
VOC-CS-03 + VOC-CS-04 dapat berjalan paralel setelah VOC-CS-01

Fase C - Operability
VOC-CS-05 setelah contract dan auth cukup jelas

Fase D - Proving dan rollout
VOC-CS-06 -> VOC-CS-07

Garis MVP integration-ready:

VOC-CS-01 + VOC-CS-02 + VOC-CS-03 + VOC-CS-04 + VOC-CS-06

Reliability dan runbook tetap wajib sebelum production, walaupun dapat menyusul demo internal.

======================================================================
7. OUTPUT YANG HARUS DIBUAT
======================================================================

Simpan hasil ke folder:

markdowns/04-implementation-plans/crawler-system/implementation-plan-crawler-system/

Minimal file:

00_INDEX.md
VOC-CS-01_api-contract-fixture.md
VOC-CS-02_delta-sync-pagination.md
VOC-CS-03_service-auth.md
VOC-CS-04_tenant-dedup-integrity.md
VOC-CS-05_reliability-observability.md
VOC-CS-06_contract-test-onebox-simulation.md
VOC-CS-07_deployment-runbook.md

Jika task dipecah karena >5 MD, gunakan suffix yang jelas, misalnya:

VOC-CS-03A_service-credential-foundation.md
VOC-CS-03B_service-auth-enforcement.md

00_INDEX.md wajib berisi:

1. tujuan paket plan;
2. scope in dan scope out;
3. tabel task, estimasi MD, dependency, owner, reviewer, dan task OneBox yang dibantu;
4. dependency graph sederhana;
5. urutan MVP, staging, dan production;
6. decision log berisi pilihan final, alasan, konsekuensi, dan blocker eksternal yang benar-benar tersisa;
7. guardrail lintas task;
8. total estimasi MD tanpa menyembunyikan pekerjaan test/docs;
9. cara developer memperbarui status dan evidence setelah task selesai.

======================================================================
8. FORMAT WAJIB SETIAP DOKUMEN TASK
======================================================================

Gunakan format berikut secara konsisten:

# VOC-CS-XX - Nama Task (X MD)

Metadata:

- Status plan: draft/ready/blocked
- Owner: Codex / developer Crawler System
- Self-review: Codex, termasuk cross-check contract terhadap kebutuhan OneBox
- Consumer validator: Claude/engineer OneBox hanya untuk verifikasi kompatibilitas saat implementasi, bukan pemberi keputusan teknis utama
- Estimasi: X MD, wajib <=5
- Dependency: task sebelumnya atau keputusan lead
- Mendukung task OneBox: RI-XX

## 1. Tujuan

Jelaskan hasil bisnis dan teknis yang dihasilkan task ini.

## 2. Definition of Done

Gunakan checklist yang observable. Hindari kata seperti "sudah optimal" tanpa ukuran.

## 3. Kondisi Existing Terverifikasi

- Tulis temuan [verified] dengan exact file path dan simbol/method.
- Tulis [assumption] hanya jika belum dapat diverifikasi sendiri.
- Tulis [blocked] hanya jika memerlukan keputusan atau akses eksternal.

## 4. Scope

Pisahkan In Scope dan Out of Scope supaya developer tidak melebar ke OneBox atau UI.

## 5. Prasyarat dan Dependency

Sebutkan keputusan, data sample, migration sebelumnya, dan task dependency.

## 6. Kontrak Sebelum dan Sesudah

Untuk perubahan API, tampilkan:

- method dan URL;
- auth header;
- query parameter dengan tipe/default/constraint;
- contoh request;
- contoh response sukses;
- contoh error;
- ordering dan pagination semantics;
- aturan nullable dan datetime/timezone;
- compatibility impact.

Untuk task non-API, jelaskan state/data flow sebelum dan sesudah.

## 7. File Target

Gunakan tabel:

| Path | Status | Alasan |
|---|---|---|
| exact/path.py | [ubah]/[baru]/[baca-saja] | fungsi file |

Jangan menulis wildcard sebagai satu-satunya file target. Temukan file aktual.

## 8. Perubahan Data dan Migration

Jika ada perubahan schema:

- model before/after;
- nama constraint/index;
- data audit sebelum migration;
- langkah upgrade;
- langkah downgrade;
- strategi untuk data existing;
- risiko lock/downtime;
- verification query.

Jika tidak ada migration, tulis eksplisit "Tidak ada perubahan schema".

## 9. Langkah Implementasi

Tulis langkah bernomor dan granular. Setiap langkah harus menyebut:

- apa yang diubah;
- file dan fungsi/class target;
- algoritma/validasi;
- edge case;
- expected intermediate result.

Skeleton kode pendek boleh diberikan untuk bagian yang rawan salah, tetapi jangan menulis implementasi penuh atau membuat API fiktif tanpa verifikasi.

## 10. Security dan Tenant Isolation

Jelaskan authentication, authorization, company_id source, secret handling, redaction, dan test kebocoran tenant.

## 11. Test Plan

Wajib mencakup:

- unit test;
- service/repository test;
- API integration test;
- negative/security test;
- migration test bila ada;
- regression test endpoint existing;
- fixture yang dipakai.

Sebutkan exact test file target, command repo yang benar, dan expected result. Jangan mengarang command; verifikasi konfigurasi test di repo.

## 12. Verifikasi Manual dan Handoff OneBox

Berikan curl/PowerShell/WSL command yang aman, tanpa secret nyata. Sertakan expected status dan potongan response. Jelaskan evidence yang dikirim ke engineer OneBox.

## 13. Observability

Sebutkan log event, field log, metric minimum, correlation ID, dan data yang wajib di-redact.

## 14. Rollout dan Rollback

Jelaskan urutan migration/deploy, feature flag bila perlu, compatibility window, smoke test, rollback aplikasi, dan downgrade migration.

## 15. Risiko dan Mitigasi

Prioritaskan risiko kehilangan delta, duplicate, tenant leak, breaking contract, secret leak, dan migration data existing.

## 16. Temuan dan Deviasi

Catat perbedaan antara task awal, dokumentasi, schema, dan codebase aktual.

## 17. Handoff dan Open Questions

Pisahkan:

- keputusan teknis yang sudah diambil beserta alasan;
- blocker bisnis/akses eksternal yang benar-benar tidak dapat diputuskan dari codebase;
- informasi yang dibutuhkan dari OneBox;
- output yang harus dikonsumsi Claude/engineer OneBox;
- hal yang tetap menjadi tanggung jawab Crawler System.

## 18. Breakdown Estimasi

Pecah estimasi per 0.5 atau 1 MD. Total wajib <=5 MD dan sudah termasuk coding, test, review, dokumentasi, serta buffer kecil. Jika tidak muat, pecah task.

======================================================================
9. DEFINITION OF READY UNTUK SETIAP PLAN
======================================================================

Sebuah plan baru boleh diberi status ready jika:

- semua file target telah diverifikasi ada atau jelas berstatus [baru];
- kondisi existing didukung bukti file/simbol;
- tidak ada keputusan arsitektur tersembunyi;
- dependency dan task OneBox terkait disebut;
- request/response contract lengkap bila menyentuh API;
- tenant isolation dan security dibahas;
- test command dan expected result dapat dijalankan;
- rollout dan rollback tersedia;
- total estimasi <=5 MD;
- developer dapat mengerjakan tanpa membaca seluruh percakapan chat.

Jika syarat tidak terpenuhi, gunakan status draft atau blocked. Jangan memberi status ready hanya karena dokumennya panjang.

Review user bukan syarat Definition of Ready. Agent wajib melakukan self-review dan mengambil keputusan teknis terbaik berdasarkan bukti yang tersedia.

======================================================================
10. ATURAN STATUS DAN BUKTI
======================================================================

Gunakan penanda:

- [verified] untuk fakta yang sudah dibaca dari source code, test, schema, atau output command;
- [assumption] untuk dugaan yang belum bisa dibuktikan;
- [blocked] untuk keputusan lead, credential, network access, atau kontrak OneBox yang belum diberikan.

Untuk [verified], sertakan file path dan simbol. Line number boleh ditambahkan tetapi jangan menjadi satu-satunya bukti karena dapat berubah.

Jangan:

- menandai rancangan ERD sebagai schema existing;
- menganggap ApiClient sudah ada sebelum memeriksa model/migration;
- menyebut updated_since sudah ada hanya karena tertulis di DFD;
- menganggap Review.updated_at cukup untuk late AI analysis tanpa membuktikan update propagation;
- mengubah scope menjadi pengerjaan OneBox;
- menyalin credential dari .env ke dokumen;
- menulis nama lama sistem untuk artifact baru, kecuali path repo existing memang masih memakai nama lama.

======================================================================
11. CARA KERJA YANG DIHARAPKAN
======================================================================

1. Audit seluruh dokumen dan kode wajib secara read-only.
2. Buat ringkasan temuan baseline dan daftar gap.
3. Finalkan decomposition task sehingga tidak ada task >5 MD.
4. Tulis 00_INDEX.md.
5. Tulis seluruh dokumen task mengikuti urutan dependency.
6. Lakukan cross-check antar dokumen:
   - nama endpoint konsisten;
   - auth model konsisten;
   - cursor/watermark konsisten;
   - field response konsisten;
   - migration tidak ganda;
   - dependency tidak melingkar;
   - estimasi tidak melebihi 5 MD.
7. Jalankan pemeriksaan akhir untuk memastikan tidak ada file target OneBox yang masuk sebagai [ubah]/[baru].
8. Lakukan self-review terhadap security, tenant isolation, backward compatibility, dependency, dan total MD.
9. Laporkan daftar file yang dibuat, total MD, keputusan final, blocker eksternal yang tersisa, dan task pertama yang harus dikerjakan developer.

Mulai dengan audit codebase. Jangan langsung menulis plan berdasarkan prompt ini. Setelah audit, buat paket implementation plan lengkap di folder yang ditentukan.
```

---

## Cara Pakai

1. Buka Codex pada root repository VoC Crawler System.
2. Paste seluruh prompt di atas.
3. Izinkan akses baca ke repo OneBox hanya jika agent perlu memverifikasi consumer contract. Ownership edit OneBox tetap di Claude/engineer OneBox.
4. Gunakan 00_INDEX.md sebagai urutan kerja developer. Keputusan teknis di dalamnya sudah harus dipilihkan oleh agent, bukan menunggu review user.
5. Setelah keputusan lead berubah, perbarui `MUST_READ.md` atau dokumen keputusan terlebih dahulu agar seluruh plan tetap sinkron.
