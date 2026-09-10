# DNGO19-3515 — To Do (Pengerjaan)

Dikerjakan bertahap. Setiap tahap sebaiknya jadi commit terpisah. Detail
alasan tiap keputusan ada di `PEMAHAMAN.md` — dokumen ini murni daftar kerja.

## Tahap 0 — Konfirmasi desain (sebelum menulis kode)

- [ ] Konfirmasi ke Sayyid: skema `VocCategoryRouting` (tabel baru) vs JSON di
  `Setting` (lihat PEMAHAMAN.md §4). Diasumsikan **tabel baru** kecuali
  dikoreksi.
- [ ] Konfirmasi: UI pemetaan jadi tab baru di layar Lokasi (bareng task
  #152 "Param Settings"), atau layar terpisah.
- [ ] Cek status task #152 (`locations.volt`) di `feature/voc` — kalau sudah
  merge, tab baru ditambahkan di atasnya; kalau belum, koordinasikan supaya
  tidak konflik file.

## Tahap 1 — AC1: Pemetaan kategori → unit, per site

- [ ] Model baru `app/models/VocCategoryRouting.php`
  (Id, SiteId, CategoryId nullable, GroupId, Enabled, CreateDate, Creator,
  ModifyDate, Modifier, ExpireDate — ikuti gaya model VoC lain).
- [ ] Migrasi baru `app/migrations/<versi>/VocCategoryRouting.php` (ikuti pola
  `VocRatingLog.php` sebagai referensi struktur file migrasi).
- [ ] Controller: endpoint baca (`categoryRoutingListAction` atau serupa) —
  kembalikan daftar Category (TypeId=`VocController::CATEGORY_TYPE_VOC`) site
  ini berdampingan dengan mapping-nya (kalau ada), plus daftar Team
  (`Organization` TypeId='OT4', SiteId ini) untuk dropdown, plus baris
  default saat ini.
- [ ] Controller: endpoint simpan (`categoryRoutingSaveAction`, POST) — pola
  create-or-update sama seperti `ratingTargetSaveAction()`: cari baris
  `SiteId`+`CategoryId`, update kalau ada, insert kalau belum. Validasi
  `GroupId` benar-benar Organization TypeId='OT4' milik site ini (jangan
  percaya id dari client mentah-mentah).
- [ ] Controller: endpoint simpan unit default (`CategoryId` NULL) — bisa
  endpoint sendiri atau parameter khusus di endpoint yang sama.
- [ ] Endpoint hapus/nonaktifkan satu baris mapping (set `Enabled=0`, bukan
  delete fisik — konsisten dengan pola Enabled-flag di model lain).
- [ ] UI: tab/panel baru untuk kelola pemetaan (tabel kategori + dropdown unit
  + tombol simpan per baris, atau form massal — sesuaikan dengan hasil
  konfirmasi Tahap 0).

## Tahap 2 — AC2: Terbitkan tiket dengan kategori, cabang, penerima otomatis

- [ ] Verifikasi dulu (baca kode, jangan asumsi): apakah `Ticket.LocationId`
  sudah terisi otomatis saat tiket lahir dari `processMessageById()` /
  `Ticketing::addTicket()`. Kalau belum, ini bagian dari AC2 juga (bukan cuma
  kategori & unit).
- [ ] Fungsi baru di `VocController`, mis. `terapkanRoutingKategori($ticketId,
  $siteId, $categoryId)`:
  - Cari `VocCategoryRouting` aktif untuk `SiteId`+`CategoryId`.
  - Kalau ada dan `GroupId` valid → insert baris `TicketGroup`
    (`TicketId`=$ticketId, `GroupId`=hasil mapping) — pola sama seperti
    `Ruling::executeActions()` aksi `OrganizationId`, tapi langsung tulis DB
    (bukan lewat `$ticket->Groups` array di memori, karena tiket sudah
    tersimpan duluan).
  - Kembalikan label/ringkasan hasil (untuk dipakai di `catatJejakReview()`,
    ikut pola `klasifikasiOtomatisTiket()` yang sudah mengembalikan `$label`).
- [ ] Panggil fungsi ini di `reviewEscalateAction()`, TEPAT SETELAH baris
  `klasifikasiOtomatisTiket()` (karena butuh `CategoryId` yang baru saja
  diisi di sana).
- [ ] Bungkus pemanggilan dengan try/catch mengikuti pola pembungkus
  `applyAnalysis()` di method yang sama — log warning, JANGAN
  menggagalkan response sukses pembuatan tiket.

## Tahap 3 — AC3: Kategori tanpa mapping → unit default + penanda, tidak gagal

- [ ] Di dalam `terapkanRoutingKategori()`: kalau tidak ada baris mapping
  untuk `CategoryId` tsb (termasuk kasus `CategoryId` masih kosong/belum
  terklasifikasi), fallback ke baris default site (`CategoryId IS NULL`).
- [ ] Kalau default pun tidak ada/disabled: JANGAN lempar exception yang
  menggagalkan tiket. Tiket tetap jadi, cukup tanpa `TicketGroup` baru, dan
  ditandai.
- [ ] Penanda: tulis ke `Ticket->Remarks` (append, pola sama seperti
  `Ruling::apply()` menandai kegagalan) — misal `"Routing: kategori tanpa
  pemetaan, memakai unit default"` atau `"Routing: unit default belum
  disetel"`. Pastikan bedakan dua kasus ini di teks penanda supaya jelas dari
  tiket kenapa ia tidak ke unit spesifik.
- [ ] Test manual: kategori sengaja tanpa mapping → tiket tetap terbit,
  `Remarks` berisi penanda, tidak ada 500/exception ke user.

## Tahap 4 — AC4: Cegah tiket ganda dari satu review

- [ ] Baca lebih dalam alur `processing->processMessageById()` /
  `Ticketing::addTicket()` untuk pastikan bagaimana `Ticket.MessageId`
  ditentukan (khususnya apakah kolom ini reused lintas channel dengan makna
  yang sama, sebelum memutuskan boleh tidaknya UNIQUE index blanket).
- [ ] Pilih salah satu mekanisme guard atomik (jangan hanya andalkan
  baca-lalu-tulis di `reviewEscalateAction()` seperti sekarang):
  - Opsi A: UNIQUE index sempit yang scoped VoC saja (mis. index gabungan
    yang hanya relevan untuk `TypeId` VoC (`TT3`) + `MessageId`), kalau MySQL
    mendukung partial/functional index di versi yang dipakai — cek versi
    MySQL dev (catatan lama: dev masih 5.7, lokal 8 — lihat task #90).
  - Opsi B: tabel/klaim kecil terpisah — insert baris "klaim eskalasi" dengan
    UNIQUE(`MessageId`) SEBELUM memanggil `processMessageById()`; kalau
    insert gagal (duplikat), tolak request dengan pesan yang sama seperti
    sekarang. Ini tidak menyentuh tabel `Ticket` yang dipakai channel lain.
  - Rekomendasi awal: Opsi B — risikonya lebih kecil karena tidak mengubah
    constraint tabel `Ticket` yang dipakai banyak fitur lain.
- [ ] Implementasikan guard terpilih di `reviewEscalateAction()`, di depan
  pemanggilan `processMessageById()`.
- [ ] Test manual: kirim dua request eskalasi untuk review yang sama secara
  nyaris bersamaan (dua tab / curl dua kali cepat) → pastikan hanya satu
  tiket yang terbit, request kedua dapat pesan "sudah menjadi tiket".

## Tahap 5 — Verifikasi end-to-end

- [ ] Jalankan stack lokal sesuai urutan wajib pindah branch (lihat memory
  `onebox-branch-switch-workflow`): down → build → up → `swoole-dev.sh`.
- [ ] Skenario uji manual di layar Ulasan VoC:
  1. Review dengan kategori yang SUDAH dipetakan → tiket dapat unit yang
     benar, `LocationId` benar, tidak ada tiket ganda meski diklik dua kali.
  2. Review dengan kategori TANPA pemetaan → tiket tetap terbit ke unit
     default + penanda di Remarks.
  3. Site TANPA unit default disetel sama sekali → tiket tetap terbit, tidak
     500, penanda menyebut "unit default belum disetel".
- [ ] Update task tracker (#154 selesai sudah, task berikutnya per tahap di
  atas jika mau dipecah lebih lanjut di tracker).

## Tidak termasuk scope (di luar 4 AC di atas)

- Mengubah `Service\Ruling`/`Ticketing.php` generik — sengaja dihindari, lihat
  PEMAHAMAN.md §5.
- Bulk-escalate banyak review sekaligus — tidak diminta PBI, dan saat ini
  memang belum ada endpoint-nya.
- Subsistem AutoAssignment/AgentMonitoring lama (`Org.TypeId IN ('SMS','OT4')`)
  — mirip secara konsep tapi tidak disebut PBI, tidak disentuh.
