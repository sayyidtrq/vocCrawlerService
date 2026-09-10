# Menaikkan VoC ke Produksi lewat release/1.123.0

Pemahaman dan to-do untuk PR ulang branch **3385, 3387, 3392, 3420** ke `release/1.123.0`, setelah review Agung Januar (September 2026).

Semua angka di dokumen ini dibaca langsung dari repo `onecloud`, bukan dugaan. Kalau ada yang berubah setelah dokumen ini ditulis, angkanya perlu dibaca ulang sebelum dipakai berargumen.

---

## Ringkasan satu paragraf

Empat branch VoC mau naik ke 1.123.0. PR 3385 dan 3387 ditolak dengan tiga catatan soal migrasi. Waktu ditelusuri, ketemu dua masalah lagi yang tidak disebut di review dan lebih berisiko: kredensial lokal ter-commit, dan branch feature yang tercemar merge dari release. Migrasi 1.123.0 sudah dikonsolidasi dari 23 folder jadi 1 folder berisi 6 berkas, terverifikasi 217/217 pernyataan SQL utuh. Agung lalu mem-patch `migration.sh generate` supaya migrasi baru masuk ke folder versi yang sudah ada — itu menjadikan aturan "satu versi satu folder" dijaga alat, bukan disiplin. Yang tersisa: menyusun branch PR bersih, mengujinya di lokal, lalu PR satu per satu dengan urutan yang benar.

---

# BAGIAN 1 — PEMAHAMAN

## 1.1 Konteks

| Branch | Tiket | Hubungan ke `release/1.123.0` |
| --- | --- | --- |
| `feature/DNGO19-3385_VOC-Master-Data-Locations` | Master Data Locations | bersih, 170 commit di depan |
| `feature/DNGO19-3387_VOC-Review-Manage-Actions` | Review Manage Actions | **tercemar** — release sudah ter-merge masuk |
| `feature/DNGO19-3392_VOC-Generate-Reports` | Generate Reports | bersih |
| `feature/DNGO19-3420_VOC-Fetch-Jobs-Crawl` | Fetch Jobs Crawl | bersih |

Keempatnya dicabang dari `feature/voc`, dan itu akar dari sebagian besar masalah di bawah.

## 1.2 Tiga catatan dari review

> 1. untuk satu versi baiknya dalam satu folder versi, tidak terpecah di beberapa folder timestamp
> 2. untuk satu table/ skema baiknya dalam satu file
> 3. untuk perbaikan data testing baiknya tidak dibuatkan migration
>
> — dan: "versi 1.123.0 terlalu banyak, sptnya ini hanya patch data di versi yg sama"

### Angkanya

`release/1.123.0` sendiri punya **0** folder `_1_123_0` — versinya belum tayang. Yang menumpuk adalah yang dibawa PR:

| Kondisi | Folder `_1_123_0` |
| --- | --- |
| release/1.123.0 sekarang | 0 |
| ditambah PR 3385 | 11 |
| ditambah PR 3387 | **23** |
| versi tayang terbanyak (`_1_118_0`) | 4 |

Kalimat "hanya patch data" itu harfiah benar. Dari **26 berkas migrasi** di PR 3387:

| Operasi | Berkas |
| --- | --- |
| CREATE / ALTER (skema) | 2 |
| INSERT / UPDATE (data) | 24 |

`Menu.php` sendiri muncul di **15 folder berbeda**.

## 1.3 Kenapa sampai terpecah — mekanismenya, bukan kelalaian

Phalcon mencatat migrasi yang sudah jalan di tabel `phalcon_migrations`, dan yang dicatat adalah **nama folder**, bukan nama berkas. Sekali folder tercatat, Phalcon tidak akan pernah menjalankannya lagi — menambah atau memperbaiki berkas di dalamnya **tidak berefek sama sekali**.

Ini sudah pernah menggigit dan tercatat di docblock migrasi kita sendiri:

> Versinya terlanjur tercatat di phalcon_migrations, sehingga memperbaiki isi file itu TIDAK menolong — Phalcon tidak akan pernah menjalankannya lagi. Karena itu perbaikannya dikirim sebagai versi baru, bukan menyunting versi lama.

Jadi tiap kali migrasi perlu diperbaiki **setelah** jalan di dev, folder baru adalah satu-satunya jalan. 23 folder itu akibat wajar dari mengembangkan sambil migrasinya sudah berjalan.

**Konsekuensi yang masih berlaku:** konsolidasi hanya bisa dilakukan selagi versinya **belum tayang**.

> **DIKOREKSI oleh hasil uji 3 September 2026.** Sebelumnya bagian ini menyarankan menghapus baris `phalcon_migrations` di dev lalu menjalankan ulang, dengan alasan "semua migrasi VoC idempotent". **Itu salah dan berbahaya.** Migrasi Menu memanggil `DELETE FROM Menu WHERE Code LIKE 'voc%'` lalu membangun ulang, sehingga menjalankannya ulang di dev akan menghapus menu milik branch lain. Lihat LAMPIRAN di akhir dokumen. Untuk dev, tandai versinya sebagai sudah diterapkan — jangan dijalankan.

## 1.4 Patch `migration.sh` dari Agung — dan batasnya

> perbaikan script migration generate sudah saya patch ke feature/voc. jd harusnya kedepan jika eksekusi generate pakai `./migration.sh local generate Log 1_124_0` sudah aman, akan masuk folder yg sudah ada
>
> bisa patch ke branch masing2: `git merge origin/hotfix/1.122.1`

**Yang ini selesaikan:** aturan 1 jadi dijaga alat. Tidak perlu lagi membuat folder timestamp manual; `generate` menaruh berkas ke folder versi yang sudah ada.

**Yang perlu diverifikasi (BELUM):** patch ini menyentuh *generate*, sedangkan jebakan `phalcon_migrations` ada di *runner* (`migrate.php` → `Phalcon\Migrations`). Dugaan kuat: jebakannya **tetap ada**, dan alur Agung aman justru karena contohnya memakai `1_124_0` — versi yang belum pernah jalan di mana pun. Perlu dibaca isinya sebelum disimpulkan.

**Yang tidak diselesaikan patch ini:** 23 folder 1.123.0 yang sudah terlanjur ada tidak ikut dirapikan. Konsolidasi manual tetap perlu.

**Peringatan soal cara memasangnya:** `git merge origin/hotfix/1.122.1` bentuknya **sama persis** dengan merge yang merusak tes lokal di 3387 — menarik branch lain ke dalam branch feature. Perlu dilihat dulu isi merge-nya. Kalau cuma `migration.sh`, ambil berkasnya saja:

```bash
git checkout origin/hotfix/1.122.1 -- onecloud/migration.sh
```

## 1.5 Lima temuan

| # | Temuan | Sumber | Status |
| --- | --- | --- | --- |
| 1 | Migrasi terpecah 23 folder, 24 dari 26 berkas cuma data | review | sudah dikonsolidasi |
| 2 | Data uji (`User.php`) dijadikan migrasi | review | dikeluarkan dari rilis |
| 3 | Release ter-merge ke dalam branch 3387 | audit repo | perlu branch PR baru |
| 4 | Kredensial lokal ter-commit | audit repo | dikecualikan dari PR |
| 5 | `build.yml` kelihatan menghapus entri tim lain | audit repo | bukan salah kita, dikecualikan |

### Temuan 3 — akar masalah tes lokal

Merge `release/1.123.0` ke branch 3387 (commit `b37baee834`) mengubah **154 berkas**, termasuk `.env`, `.env.devtele`, `.env.proxy-gateway`, `build.yml`, `onecloud/docker-compose.yml`, dan seluruh `docker/`.

`path.sh` membaca env berurutan: `.env` → `.env.$ONECLOUD_BRANCHROOT` → `.env.$1`. Satu berkas tertimpa nilai produksi sudah cukup merusak seluruh rantai, dan `build.sh local` berhenti bekerja.

### Temuan 4 — kredensial lokal

`onecloud/app/config/local.php` ter-commit di branch 3387 dengan **6 baris berubah** yang memuat password, host, dan username. Berkas itu ditandai `skip-worktree` justru supaya tidak pernah ikut.

Tiga berkas yang dilindungi: `.env.local`, `onecloud/app/config/development.php`, `onecloud/app/config/local.php`.

### Temuan 5 — build.yml, dan ini bukan salah kita

Commit `9d0ea6c344` (Agung Januar, 24 Juli 2026, "update build feature/voc") di `feature/voc`:

```diff
-feature/DNGO19-3252_ciptalife-source-broadcast:
-feature/DNGO19-3339_enhancement-customer-recognition-rs:
+feature/voc:
   analyze: false
```

Di jalur `feature/voc`, `3252` hanyalah key kosong satu baris — tidak pernah punya blok konfigurasi; yang memilikinya `3339`. Belakangan `release` mengembangkan `3252` jadi blok penuh secara terpisah. Akibatnya `git diff release...3385 -- build.yml` **terlihat** menghapus 32 baris, padahal branch itu tidak pernah memuatnya. Branch 3385 sekadar mewarisi karena dicabang dari `feature/voc`.

**Tindakannya:** jangan sertakan `build.yml` di PR fitur. Tidak perlu diperdebatkan.

### Bonus — empat branch saling tumpang tindih

| Perbandingan | Berkas berbeda |
| --- | --- |
| 3385 vs 3392 | 5 |
| 3385 vs 3420 | 13 |

Tapi ketiganya membawa **11 folder migrasi yang identik**. Artinya PR "Master Data Locations" juga berisi `reports.volt` dan `fetchjobs.volt` milik tiket lain, dan PR mana pun yang merge duluan membuat sisanya konflik.

## 1.6 Hasil konsolidasi migrasi

Satu folder, satu berkas per tabel:

| Berkas | Menggabungkan | Isi |
| --- | --- | --- |
| `Menu.php` | 15 migrasi | data menu VoC |
| `Reference.php` | 3 | data referensi |
| `Benefit.php` | 3 | katalog & pemberian benefit |
| `VocSchedule.php` | 2 | CREATE 2 tabel + ALTER-nya |
| `Ticket.php` | 1 | data tipe tiket |
| `MessageContent.php` | 1 | template pesan |
| ~~`User.php`~~ | — | **dikeluarkan**, akun uji (aturan 3) |

**23 folder / 26 berkas → 1 folder / 6 berkas.**

Digabung secara mekanis oleh `/root/voc-merge-migrations.py`: isi tiap langkah dipindah apa adanya, hanya const dan metode privat yang bentrok (`CODE`, `AKTIF`, `resolveAnchor`, `copyAudience`) diberi akhiran timestamp asalnya. Urutan `up()` mengikuti urutan folder aslinya — menu anak menempel pada induk yang dibuat langkah sebelumnya.

| Pemeriksaan | Hasil |
| --- | --- |
| Pernyataan SQL terbawa utuh | 217 / 217 |
| Lolos `php -l` | 6 / 6 |
| Nama const/metode masih kembar | 0 |
| Dijalankan lawan database | **belum** |

`User.php` disimpan ke `/root/voc-akun-uji/User.php` — di luar repo, supaya akun uji masih bisa dibuat manual tanpa ikut tayang.

## 1.7 Koreksi yang sudah dibuat

Dua hal yang sempat salah dan sudah diperbaiki, dicatat supaya tidak dipakai berargumen dalam bentuk lamanya:

1. **"release/1.123.0 punya 23 folder"** — salah. Release punya **0**; 23 itu yang ditambahkan PR 3387.
2. **"3385 menghapus blok 33 baris milik tim lain"** — overstated. Lihat temuan 5.

---

# BAGIAN 2 — KEPUTUSAN

| Keputusan | Alasan |
| --- | --- |
| **Satu folder** untuk seluruh migrasi 1.123.0 | mengikuti arahan Agung, dan sekarang didukung `migration.sh generate` |
| Folder versi dibuat lewat `migration.sh generate`, bukan tangan | supaya penamaannya kanonik, bukan timestamp karangan |
| Branch PR baru dibuat **dari release**, kode disalin ke atasnya | arah ini tidak pernah bisa membawa `.env` atau riwayat merge |
| `build.yml`, `.env*`, `config/local.php`, `config/development.php` **tidak ikut** PR | config per-mesin dan milik bersama |
| `scriptdb/voc/*`, `docs/voc/*` tidak ikut | artefak kerja |
| Urutan PR: **3385 → 3387 → 3392 → 3420** | 3385 base feature-nya; sesuai instruksi senior |
| Tiap PR berikutnya di-rebase di atas release terbaru | mencegah konflik migrasi beruntun |

---

# BAGIAN 3 — TO-DO

Status: `[ ]` belum · `[~]` sebagian · `[x]` selesai

## Tahap 0 — Persiapan

- [x] **0.1** Audit 4 branch terhadap release (ancestor, migrasi, artefak, build.yml, .env)
- [x] **0.2** Tulis aturan migrasi & naik produksi di `00-start-here/README.md`
- [x] **0.3** Bangun generator konsolidasi migrasi + verifikasi 217/217 SQL
- [x] **0.4** Siapkan `/root/voc-pr-ulang.sh` dan uji `--dry`
- [ ] **0.5** `git fetch origin` — **harus dijalankan Sayyid**, sesi Claude menggantung di kredensial HTTPS
- [ ] **0.6** Baca patch `migration.sh` di `origin/hotfix/1.122.1`; pastikan apakah jebakan `phalcon_migrations` ikut teratasi
  - _blocked by 0.5_
- [ ] **0.7** Periksa isi `git merge origin/hotfix/1.122.1` sebelum dijalankan; kalau bawa `.env`/`build.yml`, ambil berkasnya saja
  - _blocked by 0.5_

## Tahap 1 — Branch PR 3385

- [ ] **1.1** Sesuaikan generator agar nama folder mengikuti hasil `migration.sh generate`, bukan `1786200000000000` karangan
  - _blocked by 0.6_
- [ ] **1.2** Jalankan `voc-pr-ulang.sh 3385 --dry`, periksa daftar berkas masuk/ditolak
- [ ] **1.3** Susun branch `feature/DNGO19-3385_pr2`
- [ ] **1.4** Periksa `git diff --cached`: pastikan tidak ada `.env`, `local.php`, `build.yml`, `scriptdb/`, `docs/`
- [ ] **1.5** Commit tanpa trailer `Co-Authored-By`
- [ ] **1.6** Uji di stack lokal: `voc-local-up.sh`, migrasi jalan, layar VoC kebuka
- [ ] **1.7** Push, buka PR ke `release/1.123.0`
- [ ] **1.8** Balas komentar review lama soal SIDEMENU → HEADERMENU

## Tahap 2 — Branch PR 3387

- [ ] **2.1** Tunggu 3385 ter-merge, lalu `git fetch` release terbaru
- [ ] **2.2** Susun `feature/DNGO19-3387_pr2` di atas release yang sudah berisi 3385
- [ ] **2.3** Pastikan migrasi 3387 masuk ke folder versi yang **sama**, bukan folder baru
- [ ] **2.4** Di dev: `DELETE FROM phalcon_migrations WHERE version LIKE '%\_1\_123\_0'` lalu jalankan ulang migrasi
- [ ] **2.5** Uji lokal, push, PR

## Tahap 3 — Branch 3392 dan 3420

- [ ] **3.1** Tentukan berkas mana milik tiket mana — 3392 beda 5 berkas, 3420 beda 13 berkas dari 3385
- [ ] **3.2** Susun PR 3392 di atas release terbaru
- [ ] **3.3** Susun PR 3420 di atas release terbaru
- [ ] **3.4** Pastikan tidak ada folder migrasi baru yang lahir dari keduanya

## Tahap 4 — Verifikasi

- [ ] **4.1** Jalankan migrasi gabungan lawan database sungguhan (lokal dulu, lalu dev)
- [ ] **4.2** Bandingkan hasil akhir tabel `Menu` sebelum vs sesudah konsolidasi — harus identik
- [ ] **4.3** Pastikan `VocSchedule` dan `VocScheduleRun` terbentuk dengan kolom lengkap
- [ ] **4.4** Konfirmasi akun uji masih bisa dibuat manual dari `/root/voc-akun-uji/User.php`

## Utang lama yang ikut terbawa

- [ ] **U.1** Migrasi 3513 (`VocWilayah`) belum jalan di dev — tugas #162
- [ ] **U.2** Migrasi 3529 (kolom rating Google) belum jalan di dev — tugas #164
- [ ] **U.3** API key Google Maps ter-hardcode di `dashboard.volt`, perlu dirotasi bukan cuma dipindah — tugas #89

---

## Risiko

| Risiko | Dampak | Penanganan |
| --- | --- | --- |
| Migrasi gabungan belum pernah jalan lawan DB | migrasi gagal di tengah, sebagian menu tidak terbentuk | tahap 4.1, jalankan di lokal dulu |
| Folder versi sudah tercatat di dev | berkas baru tidak pernah tereksekusi | `DELETE FROM phalcon_migrations`, lalu jalankan ulang |
| `git merge origin/hotfix/1.122.1` bawa berkas env | tes lokal rusak lagi | periksa isinya dulu; ambil per-berkas kalau perlu |
| Empat PR paralel dari basis sama | konflik migrasi beruntun | rebase berurutan, jangan paralel |
| Lokal MySQL 8 vs dev MySQL 5.7 | SQL lolos lokal tapi gagal di dev | migrasi sudah ditulis kompatibel 5.7; tetap uji di dev |

## Alat

| Perintah | Guna |
| --- | --- |
| `/root/voc-pr-ulang.sh <tiket> [--dry]` | susun branch PR bersih dari release + migrasi tergabung |
| `/root/voc-merge-migrations.py <src> <dst>` | gabungkan migrasi satu tabel jadi satu berkas |
| `/root/voc-git.sh <perintah git>` | git yang aman terhadap berkas `skip-worktree` |
| `/root/voc-local-up.sh` | hidupkan stack lokal tanpa build ulang |
| `./migration.sh <env> generate <Tabel> 1_124_0` | cara resmi bikin migrasi baru setelah patch Agung |

## Rujukan

- Aturan lengkap: `00-start-here/README.md`, bagian **Aturan Migrasi** dan **Aturan Naik ke Produksi**
- Konvensi migrasi internal: `onecloud/app/migrations/readme.md`

---

# LAMPIRAN — Hasil uji migrasi gabungan di DB lokal (3 September 2026)

Dijalankan lawan DB lokal `onecloud` (MySQL 8.0.46), dengan cadangan penuh 9 tabel lebih dulu.

## Yang berhasil

| Pemeriksaan | Hasil |
| --- | --- |
| 6 berkas dieksekusi berurutan (abjad) | **semua OK**, tanpa error |
| Waktu jalan | Menu 0,69 dtk; sisanya < 0,1 dtk |
| Duplikasi baris | **tidak ada** |
| Ketergantungan silang antar berkas | **nol** — semua penyebutan tabel lain hanya di komentar |

## Temuan penting: migrasi Menu bersifat MEMBANGUN ULANG, bukan menambal

`up()` langkah pertama memanggil `resetVocMenu()` yang menjalankan:

```sql
DELETE FROM Permission WHERE ObjectName='Menu' AND ObjectId IN (...voc...);
DELETE FROM Menu WHERE Code LIKE 'voc%';
```

Lalu seluruh menu dibuat ulang. Terbukti empiris: 23 menu VoC ber-Id 1469–1497 hilang, digantikan Id 1509+.

**Akibatnya di lingkungan yang SUDAH punya menu VoC:**

| | Sebelum | Sesudah |
| --- | --- | --- |
| Kode `voc_` unik | 23 | **22** |
| Permission untuk menu `voc_` | 133 | **88** |

Yang hilang: **`voc_ws_branch` (Workspace Cabang)** — menu itu dibuat oleh migrasi dari branch LAIN (DB lokal mencatat 29 versi `_1_123_0`, sedangkan 3387 hanya punya 23). Wipe menghapus semua `voc%`, lalu 15 langkah milik 3387 hanya membangun ulang yang dikenalnya.

## Artinya untuk deployment

| Lingkungan | Aman? | Alasan |
| --- | --- | --- |
| **Produksi** | **ya** | belum pernah punya menu VoC; folder jalan sekali, hasilnya benar |
| **Dev** | **TIDAK** | sudah punya menu dari branch 3513/3523/3529 yang akan ikut terhapus dan tidak dibangun ulang |

**Jangan jalankan folder `1786200000000000_1_123_0` di dev.** Keadaan dev sudah setara hasil akhirnya lewat 23 folder lama. Cukup tandai versinya sebagai sudah diterapkan:

```sql
INSERT INTO phalcon_migrations (version, start_time, end_time)
VALUES ('1786200000000000_1_123_0', NOW(), NOW());
```

Ini pola yang memang sudah didokumentasikan di `onecloud/app/migrations/readme.md`.

## Temuan sampingan yang perlu dilaporkan ke tim

**Runner migrasi mencetak password DB dalam teks polos.** Saat menjalankan `php app/migrate.php`, perintah `pt-online-schema-change` dicetak lengkap dengan `--password=<nilai asli>` ke stdout. Ini terjadi di setiap eksekusi migrasi — termasuk di log CI dan log deploy. Perlu dimasking di sisi tooling.

**`TARGET_VERSION` bukan pembatas.** Ia berarti "migrasi SAMPAI versi itu", bukan "hanya versi itu". Di DB lokal yang dibuat dari dump (bukan dari rantai migrasi), ia mencoba menjalankan migrasi lama seri 1_115/1_116 dan gagal di `pt-online-schema-change` karena user lokal tidak punya privilege `PROCESS`.

## Keadaan DB lokal sesudah uji

Dipulihkan penuh dari cadangan `bak_voc_20260903_043541_*`:

| | Nilai | Target |
| --- | --- | --- |
| Menu total | 472 | 472 |
| Kode `voc_` unik | 23 | 23 |
| `voc_ws_branch` | 1 | 1 |
| Permission total | 7353 | 7353 |
| Permission `voc_` | 133 | 133 |

Kolom `ReviewDateFrom` / `ReviewDateTo` yang ditambahkan migrasi ke `VocSchedule` dibiarkan ada (bersifat menambah, tidak merusak).

Satu efek samping di luar cadangan: percobaan pertama lewat `migrate.php` sempat menerapkan versi lama `1775114843000000_1_116_0` dan menulis setting `CopilotEnabled` ke sejumlah site sebelum berhenti.
