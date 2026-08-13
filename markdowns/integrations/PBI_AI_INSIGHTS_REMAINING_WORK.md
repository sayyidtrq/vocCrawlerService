# Audit & PBI — AI Insights Read-only

**Tanggal audit:** 12 Agustus 2026<br>
**Sumber requirement:** `POSTMAN_AI_ANALYSIS_ENDPOINTS.md` dan scope/acceptance criteria AI Insights<br>
**Crawler yang diaudit:** `hermina-crawler` branch `fahri`, commit `a2838a7`<br>
**Consumer/UI yang diaudit:** `onecloud` branch `feature/voc`, commit `d25f46093a`

**Status implementasi:** selesai pada working tree lokal tanggal 12 Agustus 2026. Migration, contract Crawler, ingest OneBox, server filtering/status, UI Insight, dan deep-link Review Detail sudah diimplementasikan. Belum di-commit atau di-deploy.

## 1. Kesimpulan

Fondasi datanya sebagian besar sudah ada. Crawler sudah menyimpan dan mengirim hasil AI, sedangkan OneBox sudah memiliki query server-side yang mendukung paging, rentang tanggal, lokasi, urgency, kategori, status analisis, tenant/site isolation, serta Review Detail.

Yang belum selesai adalah **halaman Insight yang nyata**. Route dan menu `#/voc/insights` sudah ada, tetapi view masih memakai data hardcoded, filtering/paging di browser, tidak menampilkan seluruh field wajib, dan tidak membuka Review Detail. Selain itu, status gagal belum tersedia end-to-end karena Crawler hanya menulis kegagalan ke response/log sementara; kegagalan tidak dipersist dan tidak ikut tersinkron ke OneBox.

Solusi minimum: **gunakan ulang `Voc/reviewsData` dan `Voc/reviewDetail`; jangan membuat endpoint list baru.** Perubahan backend baru hanya diperlukan untuk mempersist dan menyinkronkan satu field `analysis_status` yang membedakan `pending`, `completed`, `failed`, dan `incomplete`.

## 2. Yang Sudah Selesai

| Kebutuhan | Status | Bukti implementasi | Catatan |
|---|---|---|---|
| Menyimpan urgency, kategori, summary, recommended action | Selesai | `app/db/models.py:407-438`; `app/services/analysis_service.py:177-192` | Hasil terbaru dipilih berdasarkan analysis ID tertinggi. |
| Crawler list mengembalikan field hasil AI | Selesai | `app/services/review_service.py:149-198`; `apps/api/app_api/schemas.py:84-130` | Field AI menempel pada setiap review. |
| Crawler Review Detail | Selesai | `apps/api/app_api/routers/reviews.py:71-90`; `app/services/review_service.py:59-72` | Detail di-scope ke company token. |
| Paging di server Crawler | Selesai | `apps/api/app_api/routers/reviews.py:30-68`; `app/services/review_service.py:123-134` | `OFFSET/LIMIT`, total, dan total_pages dihitung server. |
| Filter tanggal dan lokasi di Crawler | Selesai | `apps/api/app_api/routers/reviews.py:30-57`; `app/services/review_service.py:95-121` | Crawler belum menyediakan filter urgency/kategori pada route ini. |
| Tenant isolation di Crawler | Selesai | `apps/api/app_api/routers/reviews.py:42-46,81-85`; `app/services/review_service.py:69-70,119-121`; `tests/test_tenant_isolation.py:81-110` | `company_id` berasal dari user JWT, bukan query client. |
| OneBox menu dan route Insight | Selesai | `../onecloud/onecloud/app/migrations/1785398363272440_1_123_0/Menu.php:45-61,130-147`; `../onecloud/onecloud/public/js/routes.js:160-175` | Permission menu menyalin audience Media Monitoring. |
| OneBox server filtering lengkap | Selesai dan dapat dipakai ulang | `../onecloud/onecloud/app/controllers/VocController.php:2101-2245` | Sudah mencakup tanggal, lokasi, urgency, kategori, dan analysis_status. |
| OneBox server paging | Selesai dan dapat dipakai ulang | `../onecloud/onecloud/app/controllers/VocController.php:1337-1357,1501-1542,1607-1614` | Query memakai `LIMIT/OFFSET`; browser hanya meminta halaman aktif. |
| Site/tenant isolation di OneBox | Selesai dan dapat dipakai ulang | `../onecloud/onecloud/app/controllers/VocController.php:1350-1357,2101-2105,3193-3204` | List dan detail selalu memakai `getSiteId()`. |
| OneBox Review Detail | Selesai dan dapat dipakai ulang | `../onecloud/onecloud/app/controllers/VocController.php:3183-3302`; `../onecloud/onecloud/app/views/Voc/reviews.volt:1818-1847` | Sudah memuat hasil AI dan membedakan status legacy pending/analyzed/failed. |
| Halaman tidak menjalankan AI | Selesai secara struktur | `../onecloud/onecloud/app/controllers/VocController.php:199`; `../onecloud/onecloud/app/views/Voc/insights.volt:412-417` | Insight saat ini tidak memanggil trigger/rerun, tetapi juga belum membaca data nyata. |

## 3. Gap yang Diimplementasikan

Seluruh gap di bawah sudah ditutup pada working tree; kolom “Status saat ini” merekam kondisi sebelum implementasi untuk kebutuhan audit.

| Gap | Status saat ini | Hasil yang dibutuhkan |
|---|---|---|
| Data nyata di halaman Insight | `insights.volt:223-261` memakai branch, issue, alert, dan action queue hardcoded | Ambil data dari `Voc/reviewsData` dengan request GET. |
| Semua field wajib | Tabel mock hanya menampilkan kategori, urgency, dan rekomendasi; `reviewsDataAction()` membaca summary/action dari Ticket sehingga dapat kosong untuk review yang belum dieskalasi | Tampilkan urgency, kategori, summary, dan recommended action; gunakan Meta sebagai fallback untuk summary/action; field kosong diberi status, bukan dianggap final. |
| Filter yang disepakati | Insight tidak punya filter tanggal; filter lain menyaring array browser | Kirim rentang tanggal, lokasi, urgency, dan kategori ke server. |
| Paging server | `insights.volt:315-338` memakai `filter()` dan `slice()` | Gunakan `page`, `page_size`, `total`, dan `total_pages` dari `Voc/reviewsData`. |
| Final result only | Insight memakai mock tanpa status; flag `analyzed` Crawler hanya berarti analysis row tersedia, bukan hasil lengkap | Default request difilter server dengan `analysis_status=completed`; non-final hanya muncul bila user memilih status diagnostik. |
| Status gagal persisten | `AnalysisService` hanya menambah `failed/errors` pada response dan log (`app/services/analysis_service.py:138-154`) | Simpan status gagal pada review dan gerakkan sync watermark agar OneBox menerima perubahan. |
| Status field AI kosong | `_validate_result()` mengubah field enum kosong menjadi `unknown/other`, tetapi summary/action kosong menjadi string kosong (`app/services/analysis_service.py:267-298`) | Tandai sebagai `incomplete`; jangan tampilkan sebagai hasil final. |
| Status sampai ke OneBox | Contract integrasi hanya punya `analyzed` + hasil AI (`apps/api/app_api/integration_schemas.py:63-93`) | Tambahkan field additive `analysis_status`, lalu map ke MessageContent Meta. Penyebab teknis tetap di server log. |
| Akses Insight ke Review Detail | Baris mock tidak clickable (`insights.volt:353-365`) | Klik baris menuju Review page dan otomatis membuka detail review yang sudah ada. |
| Verifikasi otomatis gap baru | Belum ada test khusus filter urgency/kategori/status pada halaman Insight atau persistence failure | Tambah test kecil di batas Crawler contract dan OneBox controller. |

## 4. Product Backlog Item

### Judul

**AI Insights — daftar hasil analisis final dengan server filtering, paging, status, dan Review Detail**

### User Story

Sebagai user VoC, saya ingin membaca dan memfilter hasil analisis AI yang telah selesai, agar saya dapat memahami urgency, kategori, ringkasan, dan rekomendasi tindakan setiap review tanpa menjalankan proses AI dari halaman Insight.

### Nilai Bisnis

- Memisahkan hasil AI final dari layar proses/trigger analisis.
- Memungkinkan user menemukan insight relevan tanpa memuat seluruh review ke browser.
- Mencegah hasil gagal atau tidak lengkap disalahartikan sebagai output AI final.
- Menjaga isolasi data antar-tenant/site.

### In Scope

1. Menghubungkan `#/voc/insights` ke data nyata yang sudah tersimpan di OneBox.
2. Menampilkan urgency, kategori, summary, dan recommended action.
3. Filter server-side: rentang tanggal review, lokasi, urgency, kategori.
4. Paging server-side.
5. Default hanya menampilkan analysis status `completed`.
6. Status yang jelas untuk `pending`, `failed`, dan `incomplete` tanpa menampilkannya sebagai hasil final.
7. Navigasi dari hasil Insight ke Review Detail.
8. Tenant isolation berdasarkan company token di Crawler dan SiteId session di OneBox.
9. Persistence serta sinkronisasi status analysis dari Crawler ke OneBox.

### Out of Scope

- Trigger, rerun, atau scheduling analysis dari halaman Insight.
- Perubahan model, prompt, atau kualitas isi output AI.
- Edit manual hasil AI.
- Endpoint list Insight baru; `Voc/reviewsData` sudah memenuhi kebutuhan query.
- Duplikasi modal Review Detail di halaman Insight.
- Agregasi baru untuk KPI, risk score, top issues, atau alert; panel mock yang tidak didukung response existing dihapus dari halaman ini.

## 5. Perilaku Fungsional

### 5.1 Default halaman

- Saat halaman dibuka, client melakukan GET ke `Voc/reviewsData` dengan `analysis_status=completed`, `page=1`, dan `page_size` yang disepakati UI.
- Server hanya mengembalikan row `completed`; browser tidak melakukan filter final/non-final kedua.
- Urutan default adalah tanggal review terbaru.
- Empty state: “Belum ada hasil analisis final untuk filter ini.”
- Error state menyediakan tombol retry GET; tidak ada tombol trigger/rerun.

### 5.2 Kolom hasil

Setiap row final minimal menampilkan:

| Field UI | Sumber |
|---|---|
| Tanggal review | `review_time` |
| Lokasi | `location` |
| Reviewer / potongan review | `reviewer`, `review_text` |
| Urgency | `urgency` |
| Kategori | `category` |
| Summary | `summary` |
| Recommended action | `solution`/`recommended_action` |
| Status | `analysis_status` |

Nilai kosong pada salah satu field final wajib membuat row berstatus `incomplete`, bukan `completed`.

### 5.3 Filter

- `date_from` dan `date_to` memakai tanggal review, inclusive per hari.
- `location` memakai OneBox LocationId dari opsi server.
- `urgency` dan `category` memakai opsi server; jangan hardcode label kategori di browser.
- Perubahan filter mengembalikan page ke 1.
- Reset menghapus filter bisnis tetapi mempertahankan default final-only.
- Semua filter dikirim ke server; browser tidak memakai `Array.filter()` untuk menentukan dataset.

### 5.4 Paging

- Browser mengirim `page` dan `page_size`.
- Browser merender hanya `data` dari response aktif.
- Tombol previous/next mengikuti `page` dan `total_pages` server.
- Jumlah hasil memakai `total` server, bukan panjang array halaman.
- Browser tidak memakai `slice()` untuk paging dataset.

### 5.5 Status analysis

Status authoritative:

| Status | Arti | Perlakuan di Insight |
|---|---|---|
| `completed` | Semua field wajib final terisi | Tampil pada default final list. |
| `pending` | Belum ada percobaan/hasil final | Tidak tampil sebagai final; boleh dilihat lewat status diagnostik. |
| `failed` | Percobaan terakhir gagal | Tidak tampil sebagai final; badge “Analisis gagal”. |
| `incomplete` | Analysis row ada tetapi satu atau lebih field wajib kosong | Tidak tampil sebagai final; badge “Hasil belum lengkap”. |

Field wajib untuk penentuan `completed` adalah `urgency`, `issue_category`, `summary`, dan `recommended_action`. Nilai enum eksplisit `unknown`/`other` dianggap terisi; string kosong atau null membuat status `incomplete`.

Detail exception, URL provider, credential, prompt, dan raw response tetap hanya di server log. UI cukup menampilkan badge status; PBI ini tidak menambah field error karena requirement tidak meminta diagnosis provider dari halaman Insight.

### 5.6 Review Detail

- Klik row Insight mengubah hash ke `#/voc/reviews?detail_id=<MessageId>`.
- `reviews.volt` membaca `detail_id` setelah load lalu memanggil flow `openDetail()` yang sudah ada.
- Detail tetap diverifikasi dengan SiteId oleh `reviewDetailAction()`.
- Tidak membuat modal detail kedua di `insights.volt`.

## 6. Perubahan Teknis Minimum

### 6.1 Crawler (`hermina-crawler`)

1. Tambah satu kolom `analysis_status` pada `reviews` melalui Alembic: string, non-null, default `pending`, dibatasi ke `pending/completed/failed/incomplete`.
2. Backfill:
   - latest analysis dengan seluruh field wajib terisi → `completed`;
   - latest analysis dengan field wajib kosong → `incomplete`;
   - tanpa analysis row → `pending`.
   - kegagalan historis tetap `pending` karena detail error sebelumnya tidak disimpan.
3. Pada analysis success:
   - validasi kelengkapan hasil;
   - set `completed` atau `incomplete`;
   - update `sync_updated_at` dalam transaksi yang sama.
4. Pada exception:
   - set `failed` tanpa menyimpan raw exception pada review;
   - update `sync_updated_at` agar consumer menerima status terbaru.
5. Tambahkan `analysis_status` secara additive ke:
   - response `/api/reviews` dan `/api/reviews/{id}`;
   - frozen integration v1 item tanpa mengubah field existing.
6. Pertahankan `analyzed` untuk backward compatibility; consumer baru memakai `analysis_status` sebagai status authoritative.

### 6.2 OneBox ingest (`onecloud`)

1. Map `analysis_status` dari payload Crawler ke `MessageContent.Meta` pada `VocProvider`.
2. Legacy fallback:
   - jika field baru belum ada dan `analyzed=true`, anggap `completed` hanya bila seluruh field wajib terisi;
   - jika field baru belum ada dan `analysis_error` legacy terisi, anggap `failed`; selain itu `pending`.
3. Update `buildReviewFilter()` dan `reviewFilterOptions()` untuk `completed`, `failed`, `incomplete`, dan `pending`; `analyzed` boleh tetap menjadi alias legacy untuk `completed`.
4. Kembalikan `analysis_status`, `summary`, dan `recommended_action` secara eksplisit dari `reviewsDataAction()` dan `reviewDetailAction()`; untuk review tanpa Ticket, ambil summary/action dari Meta.
5. Jangan menyalin raw response atau secret Crawler ke Meta/browser.

### 6.3 OneBox Insight UI (`onecloud`)

1. Ganti array mock di `insights.volt` dengan GET `Voc/reviewsData`.
2. Hapus client-side dataset filtering/paging (`filter`, `sort`, `slice`) dan hapus panel KPI/risk/top-issues/alert hardcoded yang bukan bagian scope list.
3. Tambahkan filter tanggal dan status analisis; isi lokasi/urgency/kategori/status dari `locations` dan `filter_options` response.
4. Render semua field wajib dan status.
5. Gunakan `analysis_status=completed` sebagai default final-only.
6. Tambahkan link row ke detail flow yang sudah ada melalui `detail_id`.
7. Refresh hanya mengulangi GET aktif; tidak pernah memanggil endpoint analysis.

## 7. Acceptance Criteria Terukur

### AC1 — Read-only

**Given** user membuka atau me-refresh Insight<br>
**When** request dikirim<br>
**Then** hanya endpoint GET list/detail yang dipanggil dan tidak ada call ke `/analysis/pending`, `/rerun`, atau endpoint trigger lain.

### AC2 — Hasil final lengkap

**Given** review berstatus `completed`<br>
**When** tampil di list<br>
**Then** urgency, kategori, summary, dan recommended action tersedia dan terbaca.

### AC3 — Filter server-side

**Given** user memilih kombinasi rentang tanggal, lokasi, urgency, dan kategori<br>
**When** filter diterapkan<br>
**Then** parameter dikirim ke `Voc/reviewsData` dan seluruh row response memenuhi kombinasi filter tersebut.

### AC4 — Paging server-side

**Given** hasil lebih banyak dari page_size<br>
**When** user membuka halaman berikutnya<br>
**Then** browser meminta page berikutnya ke server dan tidak memegang dataset lengkap untuk melakukan `slice()`.

### AC5 — Tenant isolation

**Given** dua user dari SiteId/company berbeda<br>
**When** keduanya membuka filter yang sama atau mencoba ID review tenant lain<br>
**Then** masing-masing hanya melihat tenant sendiri dan akses silang menghasilkan not found/empty tanpa membocorkan keberadaan data.

### AC6 — Review Detail

**Given** satu row Insight<br>
**When** row diklik<br>
**Then** Review page terbuka dan otomatis menampilkan detail untuk MessageId tersebut.

### AC7 — Pending bukan final

**Given** review berstatus `pending`<br>
**When** Insight dibuka dengan filter default<br>
**Then** review tidak muncul sebagai final result.

### AC8 — Failure jelas dan tersinkron

**Given** proses analysis gagal<br>
**When** sync consumer berikutnya selesai<br>
**Then** OneBox menerima `failed`, menampilkan badge “Analisis gagal”, tidak menampilkan row sebagai final, dan detail exception tetap hanya di server log.

### AC9 — Field kosong bukan final

**Given** analysis menghasilkan salah satu field wajib kosong<br>
**When** hasil disimpan dan disinkron<br>
**Then** status adalah `incomplete`, row tidak masuk default final list, dan UI menampilkan “Hasil belum lengkap” saat status tersebut dipilih.

### AC10 — Backward compatibility

**Given** consumer lama masih membaca `analyzed` dan field v1 existing<br>
**When** field status baru dirilis<br>
**Then** field lama tidak dihapus/diubah tipe dan response lama tetap dapat diparse.

## 8. Test Minimum

### Crawler

- Analysis success lengkap → `completed`, watermark berubah.
- Output kosong → `incomplete`, bukan final.
- Client AI exception → `failed`, raw exception tidak tersimpan pada review, watermark berubah.
- Tenant A tidak dapat membaca status review Tenant B.
- Integration response lama tetap valid dan `analysis_status` hadir secara additive.

### OneBox

- `reviewsDataAction` dengan seluruh kombinasi filter mengembalikan hanya data SiteId aktif.
- `analysis_status=completed` tidak mengembalikan pending/failed/incomplete.
- `analysis_status=failed` dan `incomplete` menghasilkan badge yang tepat.
- Page 2 benar-benar menjalankan query server page 2.
- Klik row membuka detail; ID milik site lain ditolak.
- Network assertion: halaman Insight tidak memanggil endpoint POST analysis.

## 9. Definition of Done

- Tidak ada data mock tersisa di `insights.volt`.
- Semua AC1–AC10 lulus.
- Migration Crawler dapat upgrade dan downgrade.
- Contract Crawler terdokumentasi di OpenAPI/Postman.
- Tidak ada raw AI response, credential, atau exception sensitif pada review, response, atau UI.
- Query list/detail tetap tenant-scoped.
- Test Crawler dan test OneBox terkait lulus di CI.
- UAT mencakup completed, pending, failed, incomplete, filter gabungan, paging, dan cross-tenant attempt.

## 10. Urutan Implementasi

1. Persist status di Crawler dan perluas contract integration secara additive.
2. Map status ke OneBox Meta dan update filter server existing.
3. Sambungkan Insight UI ke `reviewsDataAction`.
4. Sambungkan row ke Review Detail existing.
5. Jalankan test, update Postman/OpenAPI, lalu UAT tenant isolation.

## 11. Dependency

- DNGO19-3388 AI Analysis Setup.
- Data review/analysis dari Crawler.
- Struktur menu VoC DNGO19-3346 — implementasi menu saat ini sudah tersedia dan dapat dipakai.

## 12. Catatan Verifikasi

- Test Crawler terkait: **57 passed** (`test_mvp`, integration contract, delta-sync, tenant isolation).
- Alembic upgrade dan downgrade berhasil dirender sebagai PostgreSQL offline SQL.
- Ruff untuk file yang disentuh lulus dengan pengecualian aturan import/forward-reference yang sudah ada pada file legacy.
- JavaScript `insights.volt` dan `reviews.volt` lulus syntax check Node setelah placeholder Volt diganti saat pemeriksaan.
- Full suite: **76 passed, 9 failed**. Sembilan failure berada pada test crawl worker, konfigurasi Gemini lama, dan fake Selenium yang sudah tidak cocok dengan signature produksi; tidak menyentuh alur AI Insights.
- Runtime PHP/OneBox belum dijalankan karena binary PHP dan Docker daemon tidak tersedia pada environment ini; wajib smoke test di environment OneBox sebelum deploy.
