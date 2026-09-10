# DNGO19-3515 — VOC: Ticket Routing

Analisa pemahaman, top-down: dari gambaran besar ke detail kode. Ditulis dari
sudut pandang yang akan mengerjakan, di branch `feature/DNGO19-3515_VOC-Ticket-Routing`
(bercabang dari `feature/voc`).

## 1. Apa yang diminta (4 acceptance criteria)

1. Buat pemetaan kategori → unit penerima tiket, per site.
2. Saat review terklasifikasi diterbitkan jadi tiket, tiket itu otomatis
   dapat kategori, cabang (lokasi), dan penerima (unit) — tanpa campur tangan
   manual.
3. Kategori yang tidak ada pemetaannya tetap masuk ke unit default per site,
   diberi penanda, dan **tidak boleh menggagalkan pembuatan tiket**.
4. Satu review tidak boleh menerbitkan tiket ganda.

## 2. Gambaran besar: di mana ini hidup dalam sistem

VoC (Voice of Customer) menarik review dari Google Maps lewat Crawler,
menyimpannya sebagai `Message` di OneBox, lalu **manusia** memilih review mana
yang layak menjadi tiket kerja (`VocController::reviewEscalateAction()`).
Pembuatan tiket TIDAK melakukan INSERT sendiri — ia lewat pipeline tiket umum
OneBox yang sama dipakai channel lain (WhatsApp, email, dst), supaya tiket
hasil eskalasi review tunduk pada aturan yang sama seperti tiket lain: bisa
dilaporkan, bisa ditugaskan, dan (harusnya) bisa di-routing.

OneBox sendiri SUDAH punya mesin routing generik: `Service\Ruling`, dipakai
lewat tabel `Rule` (kondisi + aksi berbasis JSON, dievaluasi terhadap
`Body`/`Channel`/`Category` pesan). Aksi `OrganizationId` pada Rule adalah
mekanisme yang sudah ada untuk "tugaskan tiket ke sebuah unit/tim" — persis
konsep yang diminta AC1/AC2.

**Temuan inti (akar masalah kenapa fitur ini belum ada):** mesin Ruling
dijalankan **terlalu awal** di alur VoC. Urutan aktual saat ini:

```
reviewEscalateAction()
  └─ processing->processMessageById()
       └─ Ticketing::addTicket()
            └─ creatingTicket()
                 └─ Ruling::apply()   ← CategoryId TICKET MASIH KOSONG di sini
       (ticket sudah dibuat & tersimpan)
  └─ pastikanTipeMediaMonitoring()
  └─ applyAnalysis()                  (isi ulang analisa AI ke Meta review)
  └─ klasifikasiOtomatisTiket()       ← CategoryId BARU diisi di sini
       (tidak ada logika unit/assignee sama sekali)
```

Jadi kalaupun admin membuat Rule dengan kondisi `Category`, ia tidak akan
pernah cocok untuk tiket VoC — karena saat Ruling jalan, kategori tiket masih
`NULL`. Ini bukan bug Ruling, ini soal urutan panggilan yang spesifik ke jalur
VoC.

**Implikasi desain:** fitur ini TIDAK butuh mesin routing baru. Ia butuh satu
langkah routing baru yang dijalankan **setelah** `klasifikasiOtomatisTiket()`,
memakai kategori yang baru saja diketahui, dan menerapkan hasilnya dengan cara
yang sama seperti Ruling menerapkan aksi `OrganizationId` (menambah baris
`TicketGroup`).

## 3. Konsep domain — dipetakan ke model yang sudah ada

| Istilah PBI | Wujud di kode | Catatan |
|---|---|---|
| kategori | `Category` (SiteId, TypeId=`VocController::CATEGORY_TYPE_VOC`='TC1') | sudah dipakai `klasifikasiOtomatisTiket()` |
| unit penerima tiket | `Organization` dengan `TypeId='OT4'` ("Team"), scoped `SiteId` | dikonfirmasi lewat `OrganizationController` query team, sudah dipakai fitur lain (mis. AutoAssignment) |
| "tugaskan tiket ke unit" | baris baru di `TicketGroup` (`TicketId`, `GroupId`=Organization.Id) | field `Ticket->Groups` (virtual, hasMany ke TicketGroup), persis yang dipakai `Ruling::executeActions()` untuk aksi `OrganizationId` |
| cabang | `Ticket->LocationId` | field sudah ada di model Ticket; `findReview()` sudah menghasilkan LocationId lewat COALESCE Ticket.LocationId / Meta review — perlu dicek apakah ini sudah otomatis terisi saat create atau masih butuh sentuhan di alur eskalasi (lihat TODO). |
| unit default per site | **belum ada** wadahnya | perlu tempat baru — lihat §4 |
| pemetaan kategori→unit | **belum ada** wadahnya | perlu tempat baru — lihat §4 |

Tidak perlu entity "unit" baru. `Organization(TypeId='OT4')` sudah representasi
tim/unit penerima yang benar dan sudah dipakai sistem lain — konsisten dengan
model data yang ada, bukan konsep baru yang sejajar.

## 4. Keputusan desain: di mana pemetaan kategori→unit disimpan

Dua preseden yang sudah ada di VoC untuk menyimpan "setelan per site":

- **`VocRatingTarget`** (DNGO19-3507): satu ANGKA SKALAR per site, disimpan
  sebagai satu baris di tabel generik `Setting` (kunci `SiteId` + `Code`).
  Cocok untuk nilai tunggal.
- **`VocRatingLog`**: data yang secara alami BERBARIS-BARIS (satu baris per
  kejadian), dapat tabel migrasi sendiri (`app/migrations/*/VocRatingLog.php`).

Pemetaan kategori→unit itu **relasional, bukan skalar**: satu site bisa punya
banyak baris (satu per kategori), plus satu baris "default". Ini bentuknya
sama seperti `VocRatingLog`, bukan seperti `VocRatingTarget`.

**Rekomendasi: tabel/model baru**, misalnya `VocCategoryRouting`:

```
Id              (PK)
SiteId
CategoryId      (nullable — NULL berarti baris "unit default" site tsb)
GroupId         (Organization.Id, TypeId='OT4' — unit penerima)
Enabled
CreateDate, Creator, ModifyDate, Modifier
```

Kenapa bukan JSON di satu baris `Setting` (alternatif yang lebih murah): bisa
saja, tapi jadi susah di-query/diindeks per kategori, dan menyimpang dari pola
"data relasional dapat tabel sendiri" yang sudah konsisten dipakai VoC untuk
kasus `VocRatingLog`. Tabel baru juga membuat kolom `CategoryId`/`GroupId`
bisa dibaca lewat SQL biasa (join Category/Organization) untuk kebutuhan
laporan nanti. **Ini keputusan yang sebaiknya dikonfirmasi cepat ke Sayyid
sebelum menulis migrasi**, karena mengubah keputusan ini setelah UI dibangun
di atasnya lebih mahal daripada mengonfirmasi di awal.

## 5. Modul existing yang akan bersinggungan

- **`app/controllers/VocController.php`**
  - `reviewEscalateAction()` — titik penyisipan langkah routing baru, setelah
    `klasifikasiOtomatisTiket()`.
  - `klasifikasiOtomatisTiket()` — TIDAK diubah isinya, tapi return value-nya
    (label yang sudah diterapkan) jadi contoh pola untuk fungsi routing baru
    (dipakai lagi di `catatJejakReview()` untuk audit trail).
  - Perlu endpoint baru: CRUD pemetaan (list kategori+unit, simpan satu baris,
    hapus/nonaktifkan satu baris) — pola persis `ratingTargetSaveAction()`
    (create-or-update by `SiteId`+kunci, validasi, `jsonFail`/JSON sukses).
- **`app/services/Ticketing.php` / `app/services/Ruling.php`** — TIDAK diubah.
  Dipahami sebagai referensi pola (`executeActions()` untuk cara push ke
  `Ticket->Groups`, `classify()` untuk pola "hitung tanpa efek samping").
  Mengubah file ini berisiko mempengaruhi SEMUA channel tiket lain, bukan cuma
  VoC — makanya keputusan desain di §2 sengaja menghindarinya.
- **`app/models/Ticket.php`** — tidak perlu kolom baru; `Groups`/`LocationId`
  sudah cukup.
- **`app/models/TicketGroup.php`** — dipakai apa adanya untuk menyimpan hasil
  routing (insert baris baru `TicketId`+`GroupId`).
- **`app/controllers/OrganizationController.php`** — sumber pola query "daftar
  Team (`OT4`) per site" yang perlu dipakai ulang untuk dropdown unit di UI
  pemetaan.
- **Migration baru** — `app/migrations/<versi_baru>/VocCategoryRouting.php`
  (mengikuti pola migrasi VoC lain di folder yang sama, lihat
  `VocRatingLog.php`, `VocCategorySeed.php` sebagai contoh struktur).
- **Model baru** — `app/models/VocCategoryRouting.php`.
- **Layar Lokasi / Param Settings (task #152, `locations.volt`)** — task
  DNGO19-3507 lain yang sedang berjalan di branch `feature/voc` sedang
  menambah tab "Param Settings" di layar Lokasi. UI pemetaan kategori→unit
  BISA jadi tab baru di tempat yang sama (konsisten secara UX: "setelan VoC
  per site" satu tempat) — **perlu dicek ulang statusnya saat itu selesai**,
  supaya tidak dobel kerja dua fitur menyentuh file volt yang sama.

## 6. Preseden desain yang relevan untuk AC3 dan AC4

**AC3 — gagal jangan sampai gagalkan tiket.** `Ruling::apply()` sudah punya
pola ini persis: dibungkus try/catch, kalau meledak, error ditambahkan ke
`Ticket->Remarks` dan tiket TETAP dikembalikan (bukan dilempar ulang).
Langkah routing baru DNGO19-3515 harus ikut pola yang sama: dibungkus
try/catch di `reviewEscalateAction()` (persis seperti pembungkus di sekitar
`applyAnalysis()` dan `klasifikasiOtomatisTiket()` yang sudah ada di method
itu sekarang), dan kalau kategori tidak ada pemetaan, fallback ke baris
"default" (`CategoryId IS NULL`) lalu tulis penanda ke `Ticket->Remarks`
(pola yang sama persis dipakai Ruling untuk menandai kegagalan).

**AC4 — cegah tiket ganda.** Penjagaan yang ADA SEKARANG murni di level
aplikasi: `reviewEscalateAction()` memanggil `findReview()` yang melakukan
`LEFT JOIN` Message→Ticket lalu mengecek `$review->Id` (ini sebenarnya
`Ticket.Id` hasil join, bukan Message.Id — nama field membingungkan tapi
sudah dikonfirmasi dari SQL `findReview()`). **Tidak ada UNIQUE constraint di
level database** pada `Ticket.MessageId` (dicek di semua migrasi Ticket, tidak
ditemukan). Ini artinya baca-lalu-tulis: dua request yang datang nyaris
bersamaan (double-click, dua tab browser) bisa sama-sama lolos pengecekan
sebelum salah satu sempat membuat tiket — race condition murni, meski
peluangnya kecil karena tidak ada aksi bulk-escalate (hanya satu action
per-review yang ditemukan, tidak ada endpoint bulk).

Preseden `Ruling::classify()` juga relevan secara TIDAK LANGSUNG: ia dibuat
justru untuk menghindari efek samping berulang (assignee menumpuk) saat satu
proses dipanggil berkali-kali atas data yang sama — semangat yang sama yang
harus dipegang saat merancang guard AC4 (jangan sekadar mengecek di awal,
pastikan penciptaan tiket dan penandaan "sudah dieskalasi" terjadi atomik).

## 7. Yang belum terjawab / perlu dicek lebih lanjut

- Apakah `Ticket.LocationId` sudah otomatis terisi benar saat tiket lahir dari
  review (lewat `Ticketing::addTicket()`/`processMessageById()`), atau baru
  tampak benar di `findReview()` karena COALESCE ke Meta — perlu jejak kode
  lebih dalam di `Ticketing.php`/`processing` service sebelum diklaim "AC2
  bagian cabang sudah otomatis, tidak perlu disentuh".
- Struktur final `VocCategoryRouting` (§4) sebaiknya dikonfirmasi ke Sayyid
  sebelum migrasi ditulis.
- Mekanisme guard atomik AC4 (unique index sempit vs upsert dengan penanda
  "claimed") perlu dipilih satu — lihat TODO.md.
