# Menyambungkan staging OneBox ke Crawler Service

Brief untuk menyiapkan empat nilai yang dibutuhkan `VOC_BOOTSTRAP_CONNECTION_STAGING.sql`, sekarang setelah Crawler Service punya **dua server: dev dan prod**.

Semua perintah dan nama scope di dokumen ini dibaca langsung dari repo `hermina_crawler` (`scripts/manage_api_client.py`, `app/services/api_client_service.py`), bukan dari ingatan.

Dokumen pendamping: [`PEMULIHAN_DB_STAGING_1_123_0.md`](PEMULIHAN_DB_STAGING_1_123_0.md)

---

## Yang dibutuhkan

| Nilai | Dipakai di | Dari mana |
| --- | --- | --- |
| `@crawler_url` | `Connection.Url` | base URL server Crawler yang dipilih |
| `@token` | `Options.service_token` | `scripts/manage_api_client.py issue` |
| `@company` | `Options.company_id` | company staging di server tsb |
| cabang pertama | `Options.location` | sudah ada dari seed — lihat §5 |

---

## 1. Keputusan yang harus diambil lebih dulu: server mana

Ini bukan detail konfigurasi. Ini keputusan yang menentukan ke mana tulisan staging mendarat.

**Provisioning worklist adalah operasi TULIS.** Ia mendaftarkan lokasi di sisi Crawler, lalu lokasi itu masuk antrean crawl. Mengarahkan staging ke server prod berarti lokasi uji staging lahir di data produksi, ikut dijadwalkan, dan ikut memakan kuota crawl produksi.

| Pilihan | Konsekuensi |
| --- | --- |
| **Server dev** *(rekomendasi)* | Tulisan staging mendarat di data dev. Salah konfigurasi di staging tidak bisa merusak produksi. Datanya kelas uji, dan untuk memverifikasi rilis itu sudah cukup. |
| Server prod, company khusus staging | Data lebih nyata, tetapi isolasinya bergantung sepenuhnya pada `company_id` yang benar. Satu angka salah ketik dan staging menulis ke company produksi. |
| Server prod, company produksi | **Jangan.** Tidak ada pemisah sama sekali. |

**Rekomendasi: server dev.** Staging release 1.123 ada untuk membuktikan rilisnya jalan, bukan untuk memamerkan data sungguhan. Kalau nanti demo menuntut data Hermina asli, pindah ke prod dengan company khusus adalah perubahan satu baris `UPDATE` — dan saat itu verifikasi `whoami` di §4 berubah dari formalitas jadi keharusan.

> Apa pun yang dipilih, tulis pilihannya di tiket. Enam bulan lagi, "kenapa staging menarik data ini" adalah pertanyaan yang mahal kalau jawabannya tidak tercatat.

---

## 2. Company untuk staging

Di server yang dipilih, staging butuh `company_id` sendiri — bukan menumpang company yang sudah dipakai dev atau produksi.

Alasannya sama dengan alasan setiap pemisahan tenant di sistem ini: Crawler mengunci data per `company_id`, jadi company terpisah berarti lokasi, worklist, dan review staging tidak pernah tercampur dengan milik siapa pun.

Kalau company staging belum ada, buat dulu. Prosedurnya sama dengan yang dipakai saat membuat company Puskesmas.

---

## 3. Menerbitkan service token

Perintahnya, dijalankan di server Crawler yang dipilih:

```bash
python scripts/manage_api_client.py issue \
  --company-id <company_id staging> \
  --name "onebox-staging-1123" \
  --scope reviews:read \
  --scope crawl:read \
  --scope crawl:enqueue \
  --scope analysis:write
```

### Soal scope — ini yang paling mudah terlewat

`--scope` **default-nya hanya `reviews:read`**. Kalau dijalankan tanpa menyebut scope, token yang lahir cuma bisa membaca review. Layar Fetch Jobs akan tampak hidup, tombolnya bisa ditekan, dan crawl tidak pernah benar-benar mengantre — gagal yang paling lama ketahuan karena tidak ada yang terlihat rusak.

Empat scope yang dikenal sistem:

| Scope | Untuk |
| --- | --- |
| `reviews:read` | menarik review |
| `crawl:read` | membaca status batch & riwayat fetch |
| `crawl:enqueue` | memicu crawl / Fetch Jobs |
| `analysis:write` | menulis balik hasil analisis AI |

Sebutkan yang memang dibutuhkan. Kalau staging tidak memakai analisis AI, `analysis:write` boleh ditinggal — dan itu lebih baik daripada memberikannya "untuk berjaga".

### Token hanya ditampilkan sekali

Skripnya sendiri menulis itu:

```
Service token (shown once; copy it to the OneBox secret/config store):
```

Salin saat itu juga. Kalau hilang, tidak ada cara membacanya kembali — yang ada hanya `rotate`, dan itu menerbitkan token baru.

Jangan tempel token ke tiket, chat, atau berkas yang masuk git.

---

## 4. Verifikasi SEBELUM menarik data

```bash
docker exec <container-staging> php app/bootstrap.php \
  voice_of_customer_system whoami 985
```

Yang dipastikan: token ini memang milik company yang dimaksud.

Kalau jawabannya menunjuk company lain, **berhenti**. Kalau meleset dan ditolak, itu hasil yang baik. Yang berbahaya adalah kalau ia diterima oleh company yang salah — saat itu staging menulis worklist ke tenant orang lain, dan tidak ada yang menyadarinya sampai ada yang bertanya kenapa datanya aneh.

---

## 5. Cabang pertama — kemungkinan tidak perlu dibuat

Dua baris Connection yang sudah ada di staging (Id 985 & 986) **membawa metadata cabang yang masih sah**:

| Id | Cabang | Place ID |
| --- | --- | --- |
| 985 | Hermina Depok | `ChIJ3W4519YcaS4R5g-B41W8T_U` |
| 986 | HGA Depok | `ChIJtx6hk73raS4RGaf0GgVPPks` |

`external_place_id` adalah Place ID Google — **milik Google, bukan milik server Crawler**. Ia tetap benar di server mana pun. Jadi kalau dua cabang itu memang yang mau dipakai staging, tidak ada cabang baru yang perlu dibuat: skrip SQL-nya mempertahankan metadata ini dan hanya mengganti kredensial.

Yang **tidak** bisa dibawa adalah `TargetId` (`'4'` dan `'2'`) — itu id lokasi milik Crawler dev, dan tidak berarti apa-apa di server lain. Karena itu skrip SQL mengosongkannya dan menandai `provisioning='pending'`, supaya provisioning diulang terhadap server yang benar-benar dipakai.

Cabang lain ditambahkan lewat UI Lokasi setelah koneksi hidup, dan akan mewarisi kredensial dari baris ini.

---

## 6. Urutan eksekusi

1. Pilih server Crawler (§1) dan catat pilihannya
2. Pastikan company staging ada (§2), catat `company_id`
3. Terbitkan token dengan scope yang benar (§3), salin sekali itu
4. Isi empat nilai di `VOC_BOOTSTRAP_CONNECTION_STAGING.sql`, jalankan sampai blok "SESUDAH", **baca hasilnya**, baru `COMMIT`
5. `whoami` (§4) — berhenti kalau company-nya bukan yang dimaksud
6. Provisioning ulang supaya `TargetId` terisi
7. Fetch percobaan, lalu buka Dashboard VoC staging

---

## Prompt untuk Codex

> Aku perlu menyiapkan koneksi Crawler Service untuk staging OneBox release 1.123.
>
> Konteks: Crawler Service sekarang punya dua server, dev dan prod. Staging OneBox (`onecloud_rel`, SiteId 169) perlu disambungkan ke salah satunya. Provisioning worklist adalah operasi tulis — ia mendaftarkan lokasi di sisi Crawler — jadi pilihan servernya menentukan ke mana tulisan staging mendarat.
>
> Yang aku butuhkan darimu:
>
> 1. Konfirmasi base URL server dev dan server prod Crawler, beserta cara mengaksesnya (host, port, apakah lewat VPN/internal network).
> 2. Apakah sudah ada `company_id` khusus untuk staging di server dev? Kalau belum, langkah membuatnya.
> 3. Jalankan penerbitan service token di server dev untuk company staging:
>    ```
>    python scripts/manage_api_client.py issue \
>      --company-id <id> --name "onebox-staging-1123" \
>      --scope reviews:read --scope crawl:read --scope crawl:enqueue
>    ```
>    Catatan: `--scope` default-nya hanya `reviews:read`; tanpa `crawl:enqueue` layar Fetch Jobs akan tampak hidup tapi crawl tidak pernah mengantre. Token hanya ditampilkan sekali.
> 4. Kirimkan `company_id` dan `key_id`-nya lewat kanal biasa; **token-nya jangan lewat chat atau tiket**.
>
> Jangan jalankan apa pun di server prod untuk keperluan ini.

---

## Risiko

| Risiko | Dampak | Penanganan |
| --- | --- | --- |
| Staging diarahkan ke Crawler prod | lokasi uji lahir di data produksi, memakan kuota crawl | §1 — pilih dev; catat pilihannya |
| Token terbit tanpa `crawl:enqueue` | Fetch Jobs tampak jalan, crawl tidak pernah mengantre | sebut scope eksplisit di §3 |
| `company_id` salah | staging menulis worklist ke tenant lain | `whoami` di §4, sebelum menarik apa pun |
| `TargetId` lama dipertahankan | fetch menarik review lokasi lain, atau kosong tanpa error | SQL mengosongkannya; provisioning ulang |
| Token masuk git atau tiket | kredensial bocor permanen | jangan commit; `rotate` kalau terlanjur |
