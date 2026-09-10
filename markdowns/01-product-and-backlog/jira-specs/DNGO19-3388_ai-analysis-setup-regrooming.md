# DNGO19-3388 - AI Analysis Setup

> **Dokumen:** Product re-grooming dan UI/UX specification  
> **Produk:** Voice of Customer di OneBox  
> **Status:** Ready for refinement -> ready for development setelah kontrak disetujui  
> **Tanggal:** 21 Agustus 2026  
> **Rujukan keputusan:** `ADR-0004-fast-ingestion-labeling-on-demand-ai.md`, `PLAN_FAST_INGEST_LABELING_ON_DEMAND_AI.md`, `JIRA_TICKETS_CORRECTED.md`, dan `LABELING_rule-first-strategy.md`

---

## 1. Ringkasan Keputusan Re-grooming

`DNGO19-3388` adalah **halaman policy/configuration**, bukan halaman operasi AI dan bukan dashboard insight.

Tujuan fitur ini adalah agar admin OneBox dapat menentukan, untuk setiap `Connection` VoC, apakah AI boleh dipakai dan versi struktur hasil AI mana yang diterima OneBox. Konfigurasi itu disimpan aman di `Connection.Options`, kemudian dikirim melalui worklist ke Crawler System. Crawler System tetap menjadi pemilik pemilihan model/provider, prompt runtime, batching, retry, inferensi, dan token usage.

Keputusan ini menggantikan scope Jira lama yang meminta admin memilih `model`, `prompt_version`, dan `threshold`. Ketiganya **tidak ditampilkan dan tidak disimpan oleh OneBox** karena akan menciptakan dua sumber konfigurasi, membingungkan pengguna, dan membuat kontrak lintas service rapuh.

### 1.1 Batas ownership

| Area | OneBox | Crawler System |
|---|---|---|
| Mengaktifkan/menonaktifkan analisis untuk Connection | Owner | Menghormati policy dari worklist |
| `output_schema_version` | Owner | Menghasilkan response sesuai versi yang didukung |
| Model/provider LLM | Tidak ditampilkan | Owner |
| Prompt dan parameter inferensi | Tidak ditampilkan | Owner |
| Queue, retry, concurrency, token usage | Menampilkan status/usage yang diterima pada feature lain | Owner |
| Label sentiment awal | Owner melalui `Service\Ruling` / program native existing | Tidak menggantikan |
| Summary, urgency, recommended action | Menyimpan dan memakai hasil valid | Menghasilkan saat analysis dijalankan |

---

## 2. Problem yang Diselesaikan

### 2.1 Kondisi mock saat ini

Mock `#/voc/analysis` berjudul **AI Analysis Operations** mencampur daftar hasil review, filter, ringkasan sentiment, tombol menjalankan antrean, pemilihan model, batas batch, dan coverage dalam satu layar. Bentuk ini tidak cocok untuk `3388` karena:

| Masalah | Dampak produk | Keputusan desain |
|---|---|---|
| Model terlihat sebagai setting OneBox | Admin merasa bertanggung jawab memilih model Crawler | Hapus model dari OneBox |
| Tombol `Analyze pending queue` membuat AI terlihat otomatis | Bertentangan dengan ADR-0004: AI on-demand, tidak memblokir ingestion | Pindahkan ke backlog execution/bulk analysis |
| KPI Total/Positif/Netral/Negatif adalah data operasi, bukan setup | Tidak membantu admin menyimpan policy Connection | Hapus dari setup page |
| Filter review dan tabel review berada di halaman setup | Terlalu banyak konteks sekaligus | Kelola Review tetap menjadi tempat memilih review |
| Coverage 80% dapat terlihat sehat walau ada job gagal | Menyederhanakan kondisi operasional yang kompleks | Jangan tampilkan sampai analysis queue dan status batch tersedia |
| Right rail berisi tindakan eksekusi | Membuat halaman penuh, fokus pengguna tidak jelas | Gunakan detail konfigurasi yang ringkas |

### 2.2 Prinsip produk

1. **Raw review tetap masuk meskipun AI mati.** `ai_enabled=false` tidak menghentikan crawl, discovery delta, ingestion, labeling native, atau Kelola Review.
2. **Setup menjawab satu pertanyaan:** "Apakah Connection ini diizinkan meminta AI analysis dengan kontrak output yang mana?"
3. **Hasil AI bukan pengganti rule bisnis.** `Service\Ruling` tetap berjalan pada pipeline OneBox untuk klasifikasi/routing deterministik.
4. **Tidak ada angka yang tidak bisa ditindaklanjuti.** KPI eksekusi/coverage hanya muncul setelah data queue dan history benar-benar tersedia.
5. **Satu sumber kebenaran per Connection.** Policy hanya ditulis oleh halaman setup dan dibaca melalui worklist.

---

## 3. Scope dan Non-scope

### In scope DNGO19-3388

- daftar Connection VoC dan status policy AI masing-masing;
- detail konfigurasi `ai_enabled` dan `output_schema_version` per Connection;
- default aman untuk Connection lama;
- persist non-destructive ke `Connection.Options`;
- payload worklist yang membawa policy AI;
- validasi struktur output AI yang diterima OneBox;
- tampilan status hasil AI yang valid, pending, failed, skipped, atau invalid;
- penerapan `Service\Ruling` pada pipeline bisnis tanpa rule engine baru.

### Out of scope DNGO19-3388

- memilih model, provider, prompt version, temperature, threshold inferensi, atau batch size;
- menjalankan single/bulk AI analysis dari UI;
- antrean asinkron, progress job, retry, cancellation, dan dead-letter queue;
- halaman AI Insights, dashboard coverage, report, dan token metering;
- optimasi Ollama/local LLM atau kualitas prompt kategori;
- membuat rule baru di luar `Service\Ruling` existing.

> Single/bulk selection dan progress analysis akan menjadi feature berikutnya setelah API analysis job asynchronous tersedia. Sementara itu action analysis per review tetap berada di detail review, bukan di halaman setup.

---

## 4. User dan Job-to-be-done

| User | Tujuan | Keputusan yang dibuat |
|---|---|---|
| Admin VoC/site | Mengendalikan apakah satu kanal/lokasi boleh memakai AI | Aktif/nonaktif AI untuk Connection tertentu |
| Admin integrasi | Menjaga kontrak payload OneBox-Crawler konsisten | Memilih versi schema output yang didukung |
| Operations manager | Memastikan review tetap bisa ditindaklanjuti saat AI tidak tersedia | Memahami bahwa disable AI tidak menghentikan crawl dan review workflow |
| Developer/support | Mendiagnosis hasil AI yang tidak dapat dipakai | Melihat schema version dan status validasi tanpa membuka raw credential |

**User story utama:**

> Sebagai Admin VoC, saya ingin mengatur izin AI untuk setiap Connection agar review dari cabang yang relevan dapat dianalisis sesuai kontrak yang didukung, tanpa mengganggu crawling dan pengelolaan review ketika AI dimatikan atau sedang bermasalah.

---

## 5. Information Architecture dan Screen Map

```text
Pengaturan
  -> Voice of Customer
      -> AI Analysis Setup                         [DNGO19-3388]
          -> Daftar Connection AI
              -> Konfigurasi Connection
                  Tab 1: Konfigurasi
                  Tab 2: Kontrak Output

Voice of Customer
  -> Kelola Review
      -> Detail Ulasan
          -> Action "Analisis AI"                 [feature execution berikutnya]

Voice of Customer
  -> AI Insights / Riwayat Analisis               [out of scope 3388]
```

### Keputusan tab

Hanya ada **dua tab** pada detail setup.

| Tab | Tujuan | Isi | Status |
|---|---|---|---|
| `Konfigurasi` | Mengubah policy AI per Connection | switch `ai_enabled`, schema version, pesan dampak, tombol simpan | MVP 3388 |
| `Kontrak Output` | Membuat ekspektasi Crawler dan OneBox transparan | tabel field, tipe, enum, perilaku invalid, ownership | MVP 3388, read-only |
| `Riwayat perubahan` | Audit siapa mengubah policy kapan | audit event khusus | Tidak dibuat pada 3388; jangan tampilkan tab kosong |
| `Penggunaan / Coverage` | Membaca performa dan konsumsi AI | job status, token, success/failure | Tidak dibuat pada 3388; menjadi bagian Insights/operations |

---

## 6. Screen Specification

## 6.1 Screen A - Daftar Connection AI

**Route usulan:** `#/voc/settings/ai` atau bagian `AI Analysis` di dalam `#/voc/settings`.

Tujuan layar ini adalah memilih Connection yang ingin dikonfigurasi, bukan menganalisis review.

### Header

- Breadcrumb: `Pengaturan / Voice of Customer / AI Analysis Setup`.
- H1: `Pengaturan Analisis AI`.
- Subteks: `Atur izin analisis dan kontrak hasil AI untuk setiap koneksi Voice of Customer.`
- Satu kontrol konteks site pada shell OneBox tetap digunakan; jangan membuat site selector kedua.
- Tidak ada tombol `Refresh Data` generik. Gunakan icon refresh kecil di toolbar tabel bila diperlukan untuk reload daftar Connection.

### KPI / summary yang ditampilkan

Gunakan **maksimum tiga summary tile kecil**, bukan lima KPI operasi seperti mock lama. Semua angka harus berasal dari data konfigurasi yang tersedia.

| Tile | Nilai | Definisi | Tindakan |
|---|---|---|---|
| AI aktif | `n dari total Connection` | Jumlah Connection yang policy `ai_enabled=true` | Filter tabel ke aktif |
| Belum dikonfigurasi | `n Connection` | `Options` tidak memiliki policy AI dan sedang memakai default aman | Filter tabel ke perlu setup |
| Versi kontrak | `v1` | Versi schema output yang didukung OneBox saat ini | Buka tab Kontrak Output |

Jangan tampilkan `Total Review`, sentiment mix, coverage, token usage, atau jumlah job di screen ini karena semua itu adalah indikator operasi/insight dan belum memiliki lifecycle analysis asynchronous yang final.

### Tabel Connection

| Kolom | Data | Perilaku |
|---|---|---|
| Connection | `Connection.Name` | Judul utama; klik membuka detail konfigurasi |
| Lokasi | Nama Location/target yang terhubung | `-` bila Connection tidak location-scoped |
| Source | `MediaId` / provider yang ramah dibaca | Contoh `Google Business Review` |
| Analisis AI | `Aktif`, `Nonaktif`, atau `Belum dikonfigurasi` | Status pill; bukan toggle inline agar tidak ada perubahan tanpa konfirmasi/simpan |
| Kontrak output | `v1` atau `Default v1` | Default ditampilkan jelas untuk Connection legacy |
| Aksi | Icon tombol settings dengan tooltip `Konfigurasi AI` | Membuka Screen B |

### Filter dan state

- Filter cepat: `Semua`, `AI aktif`, `AI nonaktif`, `Belum dikonfigurasi`.
- Search: nama Connection atau lokasi.
- Pagination mengikuti komponen DataTable OneBox existing.
- Empty state: `Belum ada Connection Voice of Customer pada site ini.` dengan CTA ke setup Connection, bukan CTA membuat model AI.
- Jika user tidak punya permission untuk mengubah setup, baris tetap dapat dilihat namun tombol konfigurasi disabled dengan tooltip yang menjelaskan permission yang dibutuhkan.

### Key action placement

- Action utama berada pada tiap baris (`Konfigurasi AI`) karena policy bersifat per Connection.
- Tidak ada tombol global `Aktifkan semua AI`; terlalu berisiko dan tidak sesuai scope tenant/Connection.

---

## 6.2 Screen B - Detail Konfigurasi AI per Connection

**Route usulan:** `#/voc/settings/ai/{connectionId}` atau detail drawer/modal dari Screen A jika pola OneBox existing lebih kuat ke modal.

Untuk pengaturan yang perlu dibaca ulang dan memiliki dua tab, **halaman detail** lebih disarankan daripada modal. Modal cepat penuh, sulit ditautkan, dan tidak baik untuk menjelaskan kontrak output.

### Header konteks

```text
Pengaturan Analisis AI / RSU Hermina Depok
Google Business Review  |  Connection #1039  |  Site 169
```

Tampilkan Connection name, source, lokasi, dan Site sebagai konteks read-only. Jangan menampilkan token, password, base URL, model, atau prompt.

### Tab 1 - Konfigurasi

#### Section: Status Analisis AI

| Elemen | Bentuk | Perilaku |
|---|---|---|
| `Aktifkan analisis AI` | Toggle switch + label status | Nilai yang akan disimpan ke `Connection.Options.ai_enabled` |
| Penjelasan state aktif | Helper text | `Review tetap masuk dan dapat dikelola; AI hanya tersedia saat pengguna menjalankan analisis.` |
| Penjelasan state nonaktif | Warning/info callout ringan | `Crawl, ingestion, labeling native, dan Ticket workflow tetap berjalan. Permintaan analisis baru ditolak.` |

Toggle **tidak langsung menyimpan**. Perubahan membuat halaman dirty dan membutuhkan tombol Simpan agar pengguna tidak salah mengubah policy ketika berpindah Connection.

#### Section: Kontrak Output

| Elemen | Bentuk | Perilaku |
|---|---|---|
| `Versi output` | Select single-value | Saat ini hanya `v1`; gunakan select agar future-compatible, tetapi disable/readonly jika memang hanya ada satu versi didukung |
| Status dukungan | Pill `Didukung` | Berdasarkan registry schema OneBox, bukan input bebas pengguna |
| Ringkasan | Link `Lihat field yang diharapkan` | Mengarah ke tab Kontrak Output |

Jangan gunakan input bebas untuk schema version. Nilai hanya boleh berasal dari allowlist OneBox (`v1` saat MVP).

#### Section: Penerapan

Tampilkan card read-only untuk menjelaskan alur kerja. Ini bukan konfigurasi tambahan.

```text
Review masuk -> labeling native OneBox -> review dapat dikelola
                         |
                         +-> jika AI aktif dan pengguna meminta analisis
                             Crawler mengembalikan enrichment sesuai schema v1
```

#### Footer action sticky

| Action | Jenis | Aturan |
|---|---|---|
| `Simpan perubahan` | Primary button | Disabled sampai ada perubahan valid; menulis policy secara atomik |
| `Batal` | Secondary text/button | Mengembalikan form ke nilai tersimpan; tampilkan confirmation hanya jika ada perubahan belum disimpan |
| `Kembali ke daftar` | Link/back icon | Jika dirty, gunakan confirm leave |

Success feedback: toast `Pengaturan AI untuk {Connection} diperbarui.`  
Failure feedback: inline alert di atas form dengan pesan aman dan correlation/request ID bila ada. Jangan membocorkan credential Crawler.

### State Connection legacy

Apabila `Connection.Options` belum memiliki block AI:

```json
{
  "ai_enabled": false,
  "output_schema_version": "v1"
}
```

UI menampilkan badge `Belum dikonfigurasi` dan info:

> Connection ini menggunakan default aman. Analisis AI nonaktif sampai admin menyimpan konfigurasi.

Default ini harus dipakai pada read maupun write path. Saat admin menyimpan, hanya key AI yang ditambahkan atau diperbarui; seluruh opsi existing harus tetap utuh.

---

## 6.3 Tab 2 - Kontrak Output

Tab ini read-only dan merupakan satu-satunya "table" di halaman detail. Fungsinya menyamakan ekspektasi admin, support, dan developer tanpa menjadikan admin editor prompt/model.

### Tabel kontrak output schema `v1`

| Field | Tipe | Wajib | Nilai/format yang diizinkan | Dipakai OneBox untuk | Fallback bila tidak valid |
|---|---:|:---:|---|---|---|
| `analysis_status` | string | Ya | `not_requested`, `pending`, `processing`, `completed`, `partial`, `failed`, `skipped`, `invalid_output` | Menentukan badge dan action lanjutan | `invalid_output` |
| `sentiment` | string | Ya saat `completed` | `positive`, `neutral`, `negative`, `mixed`, `unknown` | Enrichment/display; tidak menggantikan label native secara otomatis | `unknown` |
| `urgency` | string | Ya saat `completed` | `low`, `medium`, `high`, `critical`, `unknown` | Prioritas tindak lanjut setelah mapping disetujui | `unknown` |
| `issue_category` | string | Ya saat `completed` | taxonomy Crawler yang disepakati; fallback `other` | Mapping CategoryId/ringkasan isu | `other` + warning terstruktur |
| `summary` | string | Ya saat `completed` | non-empty, plain text | Ringkasan di detail review/Ticket | Tidak ditampilkan sebagai hasil final |
| `recommended_action` | string | Ya saat `completed` | non-empty, plain text | Usulan tindakan pada detail review/Ticket | Tidak ditampilkan sebagai hasil final |
| `analyzed_at` | ISO-8601 datetime | Ya saat `completed` | timestamp UTC | Freshness/audit tampilan | Kosong; status tetap non-final |
| `error` | object/string tersanitasi | Wajib saat `failed`/`invalid_output` | code + safe message; tanpa token/prompt/raw credential | Pesan error dan retry feature berikutnya | `ANALYSIS_RESULT_INVALID` |
| `schema_version` | string | Ya | `v1` | Validasi compatibility | Tolak hasil sebagai `invalid_output` |

### Callout rule-first

> `Service\Ruling` OneBox tetap melakukan klasifikasi deterministik untuk routing/kategori/prioritas pada pipeline bisnis. Hasil AI adalah enrichment dan tidak boleh mengganti rule secara diam-diam.

---

## 7. General Flow dan State

### 7.1 Save policy dan propagasi worklist

```text
Admin membuka daftar Connection
  -> memilih satu Connection
  -> OneBox membaca Connection.Options
  -> opsi tidak ada? tampilkan default aman
  -> admin mengubah ai_enabled / schema version
  -> OneBox validasi allowlist dan permission
  -> merge key AI ke Connection.Options (tanpa menghapus key lain)
  -> OneBox menandai worklist berubah
  -> Crawler mengambil worklist berikutnya
  -> Crawler memakai policy tersebut saat menerima enqueue analysis berikutnya
```

### 7.2 Review ingestion ketika AI aktif maupun nonaktif

```text
Crawl selesai
  -> raw review tersimpan di Crawler
  -> OneBox pull discovery delta
  -> raw review/Ticket existing di-upsert
  -> Service\Ruling/native labeling berjalan
  -> review dapat dikelola
  -> AI disabled? selesai
  -> AI enabled? tetap selesai, menunggu user meminta analysis
```

### 7.3 Hasil analysis yang masuk kembali

```text
OneBox menerima enrichment untuk identity review yang ada
  -> validasi schema version + field wajib + enum
  -> valid? update enrichment review/Ticket existing idempotently
  -> invalid/failed? simpan/tampilkan analysis_status yang sesuai
  -> jangan create Ticket baru
  -> jangan ubah review backfill menjadi review live
```

### 7.4 Status yang harus terlihat konsisten

| Status | Makna | Tampilan UI | Aksi pada 3388 |
|---|---|---|---|
| `not_requested` | Belum diminta user | Muted badge `Belum dianalisis` | Tidak ada action di setup |
| `pending` | Sudah masuk antrean | Info badge `Menunggu` | Ditampilkan pada review di feature berikutnya |
| `processing` | Sedang diproses | Info/progress | Ditampilkan pada review di feature berikutnya |
| `completed` | Output schema valid | Success badge `Selesai` | Detail review dapat membaca enrichment |
| `partial` | Sebagian bulk batch selesai | Warning badge | Feature queue berikutnya |
| `failed` | Analysis gagal | Danger badge + safe message | Feature retry berikutnya |
| `skipped` | Sengaja tidak dianalisis, misalnya AI disabled | Neutral badge | Tidak dianggap error crawl |
| `invalid_output` | Response tidak sesuai contract | Danger badge + correlation info | Tidak dianggap `completed` |

---

## 8. Data Contract dan Persistensi

### 8.1 Struktur `Connection.Options`

Gunakan merge JSON non-destructive. Nama key final yang disarankan:

```json
{
  "mock": false,
  "location_map": {"8": 1703},
  "ai_enabled": true,
  "output_schema_version": "v1"
}
```

Gunakan dua key flat di atas sebagai kontrak final 3388 agar identik dengan backlog dan payload worklist. Saat save, lakukan merge JSON non-destructive: jangan menghapus `mock`, `location_map`, auth mapping, atau option provider lain.

Resolver compatibility yang wajib tersedia:

1. Baca `Options.ai_enabled`; bila tidak ada gunakan `false`.
2. Baca `Options.output_schema_version`; bila tidak ada gunakan `v1`.
3. Saat save, validasi dua key tersebut lalu merge ke JSON existing tanpa mengubah key lain.

> Catatan implementasi: perubahan struktur key perlu dicatat sebagai ADR kecil bila tim memilih bentuk berbeda. Yang tidak boleh berubah adalah semantik default aman dan policy per Connection.

### 8.2 Worklist payload

Crawler hanya menerima policy yang dibutuhkan, tanpa credential OneBox maupun credential user.

```json
{
  "company_id": 3,
  "onebox_connection_id": 1039,
  "onebox_location_id": 1703,
  "kind": "location",
  "active": true,
  "ai_enabled": true,
  "output_schema_version": "v1"
}
```

Kontrak harus mempertahankan boolean sebagai boolean dan schema version sebagai string. Jangan mengirim `model`, `prompt_version`, `threshold`, password, API key, atau service token pada worklist.

### 8.3 Validation boundary

| Titik | Validasi |
|---|---|
| Form OneBox | User memiliki permission, `enabled` boolean, schema dari allowlist |
| Persistensi OneBox | JSON existing valid dan key lain tidak berubah |
| Worklist response | Field `ai_enabled` boolean dan `output_schema_version` terisi default |
| Crawler sebelum execution | Tenant + Connection active + AI policy enabled sebelum menerima job analysis |
| OneBox saat menerima output | Version supported, status valid, field wajib dan enum sesuai schema |

---

## 9. Detailed Product Backlog

### P0 - Contract dan policy foundation

| ID | Task | Owner utama | Detail / DoD |
|---|---|---|---|
| 3388-01 | Kunci ownership dan schema `v1` | Sayyid + BE OneBox + Crawler | ADR/contract menyatakan OneBox tidak memilih model; daftar field/enum/fallback final tersedia |
| 3388-02 | Buat policy resolver Connection legacy | BE OneBox | Resolver membaca `ai_enabled`/`output_schema_version` yang ada atau missing option dan menghasilkan default `false` + `v1` |
| 3388-03 | Persist policy non-destructive | BE OneBox | Update `Connection.Options` hanya merge `ai_enabled` dan `output_schema_version`; automated test membuktikan `location_map` dan option existing bertahan |
| 3388-04 | Tambahkan policy pada worklist | BE OneBox + Crawler | Payload memiliki `ai_enabled` boolean dan `output_schema_version`; Crawler dapat membaca default safely |
| 3388-05 | Registry validator output `v1` | BE OneBox | Output unsupported/invalid diberi status `invalid_output`, tidak dipakai sebagai completed |

### P1 - Setup UI

| ID | Task | Owner utama | Detail / DoD |
|---|---|---|---|
| 3388-06 | Buat daftar Connection AI | FE OneBox | Summary 3 tile, filter state, table 6 kolom, empty/loading/error states |
| 3388-07 | Buat detail Konfigurasi | FE OneBox + BE OneBox | Toggle AI, schema allowlist, legacy notice, dirty state, save/cancel/leave protection |
| 3388-08 | Buat tab Kontrak Output | FE OneBox | Tabel schema `v1`, callout rule-first, no editable model/prompt fields |
| 3388-09 | Role/permission handling | BE + FE OneBox | Read-only dan disabled CTA mengikuti role existing; tidak ada security hanya dari hide button |
| 3388-10 | Polish responsive/accessibility | FE OneBox | Keyboard toggle/select, label associated, status tidak hanya warna, mobile layout tetap terbaca |

### P1 - Pipeline bisnis dan QA

| ID | Task | Owner utama | Detail / DoD |
|---|---|---|---|
| 3388-11 | Verifikasi entry point `Service\Ruling` | BE OneBox | Bukti class, input, output, SiteId scope, dan urutan terhadap ingest tercatat; tidak membuat engine baru |
| 3388-12 | Guard AI disabled | BE OneBox + Crawler | Crawl/ingest/ruling sukses saat AI off; request analysis baru ditolak dengan error terstruktur |
| 3388-13 | Contract test worklist + response | BE OneBox + Crawler | Test bool/string/default/version mismatch dan tenant isolation |
| 3388-14 | UAT checklist | QA + PM | Semua state normal, legacy, disabled, invalid output, permission denied diuji pada site dev |

### Explicitly deferred

| Item | Kenapa ditunda | Target backlog |
|---|---|---|
| Single/bulk analyze | Membutuhkan durable async analysis API dan idempotency job | Enhance AI Analysis |
| Progress bar analysis | Harus berasal dari jumlah item batch nyata, bukan simulasi | Enhance AI Analysis |
| Retry failed item | Bergantung analysis queue | Enhance AI Analysis |
| Token/coverage dashboard | Memerlukan metering dan lifecycle job yang final | AI Insights / Reporting |
| Model/prompt controls | Ownership Crawler dan berisiko konfigurasi ganda | Crawler admin/internal ops bila diperlukan |

---

## 10. Acceptance Criteria yang Direvisi

1. Admin berwenang dapat melihat daftar Connection VoC dan status policy AI masing-masing.
2. Admin dapat mengaktifkan/menonaktifkan AI per Connection melalui save explicit.
3. Admin hanya dapat memilih `output_schema_version` dari daftar version yang didukung OneBox; pada MVP hanya `v1`.
4. UI tidak menampilkan model/provider, prompt runtime, threshold inferensi, batch size, atau credential Crawler.
5. Update tidak menghapus key `Connection.Options` lain.
6. Connection legacy tanpa policy AI tampil sebagai `Belum dikonfigurasi` dan menggunakan `AI nonaktif`, schema `v1`.
7. Worklist mengirim `ai_enabled` (boolean) dan `output_schema_version` (string) tanpa credential.
8. AI nonaktif tidak menghentikan crawl, raw ingestion, native labeling, Kelola Review, atau Ticket workflow.
9. Output Crawler yang tidak sesuai schema tidak pernah ditampilkan sebagai `completed`.
10. `Service\Ruling` existing tetap dipakai dan berhasil berjalan tanpa bergantung pada AI enabled.
11. Semua UI memiliki loading, empty, permission denied, save success, validation error, dan failed API state yang jelas.
12. Tidak ada KPI operasi, queue action, atau progress palsu pada halaman setup.

---

## 11. QA Scenario Matrix

| Scenario | Setup | Expected result |
|---|---|---|
| Connection baru, AI aktif | Save `enabled=true`, `v1` | Worklist membawa AI policy aktif; raw crawl flow tidak berubah |
| AI dinonaktifkan | Save `enabled=false` | Crawl dan ingest tetap sukses; analysis baru tidak boleh dieksekusi |
| Connection legacy | Opsi AI tidak ada | UI menampilkan default aman dan tidak error |
| Save policy | Options sebelumnya berisi provider mapping | Key provider tetap identik setelah update |
| Schema invalid | Crawler mengirim version tidak dikenal | Result status `invalid_output`; tidak mengubah Ticket menjadi complete |
| Enum invalid | Urgency/sentiment di luar allowlist | Result tidak dipakai sebagai final; error aman terlihat |
| AI output valid | Crawler kirim schema `v1` lengkap | Review/Ticket existing menerima enrichment idempotently |
| Rule-first saat AI off | Ingest review baru | Ruling/native labeling dan Ticket workflow tetap bekerja |
| Permission read-only | User tanpa edit permission | Data bisa/tidak bisa dilihat sesuai policy; save tidak dapat dipanggil hanya dari browser |
| Responsive | Width desktop/tablet/mobile | Table scroll/pagination aman; form satu kolom di mobile |

---

## 12. Reference Design dan Riset

Pilihan UI didasarkan pada pola aplikasi administrasi ber-data, bukan pola "AI dashboard" generik:

- [Material Design - Data tables](https://m2.material.io/design/components/data-tables.html): tabel harus mendukung scanning, filtering, selection state yang jelas, pagination, dan progress indikator saat operasi tabel berjalan.
- [Microsoft Fluent - Wait UX](https://fluent2.microsoft.design/wait-ux): untuk proses lebih dari beberapa detik, tampilkan progres dan pesan yang jujur; spinner tidak cukup untuk operasi panjang.
- [NN/g - The Anatomy of a List Entry](https://www.nngroup.com/articles/list-entries/): prioritaskan atribut yang paling dibutuhkan user saat scanning list dan jangan membuat list penuh informasi sekunder.
- [Accessible Data Interfaces - Bulk selection](https://accessible-data-interfaces.com/accessible-data-tables-grid-systems/bulk-selection-batch-actions/): future bulk actions harus memakai selection count yang jelas, select-all indeterminate, dan toolbar kontekstual yang accessible.

Implikasi untuk OneBox:

- gunakan tabel Connection untuk administrasi policy;
- pakai tab read-only untuk kontrak, bukan card/dashboard berlebihan;
- simpan bulk toolbar dan progress real untuk feature execution setelah queue tersedia;
- jangan gunakan warna saja sebagai pembeda status; setiap pill harus punya teks;
- action utama muncul dekat entity yang dipengaruhi, yaitu Connection.

---

## 13. Handoff ke Development

Sebelum coding dimulai, tim harus mengonfirmasi tiga hal:

1. Bentuk canonical final di `Connection.Options`: key flat `ai_enabled` dan `output_schema_version`, dengan merge non-destructive terhadap option yang sudah ada.
2. Registry `output_schema_version` yang dimiliki OneBox, dengan `v1` sebagai satu-satunya nilai MVP.
3. Entry point dan bukti runtime `Service\Ruling` untuk ingest review, termasuk perilakunya ketika AI disabled.

Setelah itu implementasi dapat berjalan paralel:

```text
BE OneBox: policy resolver + persist + worklist + validator
FE OneBox: connection list + form konfigurasi + tab kontrak
Crawler: baca policy worklist + patuhi ai_enabled pada analysis request
QA: legacy/default, policy off, output invalid, rule-first, tenant isolation
```

Feature dianggap selesai bila admin bisa mengatur policy yang benar per Connection, Crawler menerima policy yang konsisten, dan raw review tetap dapat dikelola walau AI tidak aktif atau output AI tidak valid.
