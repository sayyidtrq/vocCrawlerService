# P0 - Google Maps Crawler Berhenti pada 5 Review

**Status:** akar masalah terbukti; hardening lokal selesai dan recovery profil menunggu login manual serta real-crawl verification
**Tanggal investigasi:** 11-14 September 2026
**Environment:** OneBox dev dan Crawler dev
**Severity:** P0 karena seluruh fetch manual dan terjadwal dapat menghasilkan sukses palsu

## 1. Ringkasan eksekutif

Crawler dev tidak kehabisan review dan bukan gagal karena target, scan limit,
worklist, database, atau koneksi OneBox. Google Maps hanya memberikan lima
review awal kepada profil Chromium yang sedang logout. Ketika crawler meminta
review berikutnya, Google menampilkan login wall, bukan batch review baru.

Engine lama tidak mengenali login wall tersebut. Setelah lima putaran tanpa
card baru, engine mengubah kondisi itu menjadi `no_new_review_cards`, lalu API
memublikasikannya sebagai `no_more_reviews`. Job menjadi `partial_success`,
batch menjadi `completed`, dan OneBox menampilkannya sebagai **Selesai**.

Jadi ada tiga kegagalan yang saling memperkuat:

1. **Operational state:** worker memakai Docker volume profil baru yang belum
   login.
2. **Application semantics:** auth wall dan pagination stall disamarkan sebagai
   akhir daftar yang normal.
3. **Deployment drift:** stack dev saat ini menjalankan branch eksperimen
   proxy, bukan branch `dev` canonical atau patch P0 ini.

## 2. Dampak

- Target 10 sampai 300 berhenti tepat pada lima review.
- Crawl delta hanya membaca lima review pertama dan terus menghasilkan
  duplikat pada run berikutnya.
- Crawl rentang tanggal dapat menghasilkan nol review karena urutan terbaru
  gagal dipasang dan hanya lima card awal yang diperiksa.
- Scheduler terlihat sehat walaupun coverage review tidak bertambah.
- Operator mendapat status hijau dan tidak diarahkan untuk memperbarui login.

Data yang sudah masuk tidak rusak. Masalahnya adalah under-fetch dan status
yang menyesatkan.

## 3. Bukti produksi dev

| Batch | Lokasi | Target | Scan limit | Terbaca | Sort | Stop reason |
|---|---|---:|---:|---:|---|---|
| `8149220a-f4b5-4b7f-85a7-03ec8742a27d` | LANUD Abdul Rachman Saleh | 300 | 3000 | 5 | gagal | `no_more_reviews` |
| `cbafccfe-a2c4-43cd-9eb3-c809afd438f2` | Hermina Bogor | 10 | 500 | 5 | gagal | `no_more_reviews` |

Probe Selenium read-only pada container yang sama membuktikan:

- tab `Ulasan` aktif;
- URL dan Place ID mengarah ke lokasi yang benar;
- kontainer scroll yang dipilih benar;
- `navigator.webdriver` sudah disembunyikan;
- card tetap 5 setelah JavaScript scroll, trusted wheel, dan tombol End;
- Google menampilkan modal **Login untuk menikmati fitur terbaik dari Google
  Maps**;
- di belakang modal terdapat kontrol `Lihat ulasan lainnya (25)`;
- screenshot probe disimpan sementara di container sebagai
  `/tmp/google-maps-runtime-probe.png`.

Audit ulang 14 September menemukan failure mode kedua pada runtime dev:

| Batch | Lokasi | Hasil | Attempt | Durasi | Error |
|---|---|---|---:|---:|---|
| `720b247f-62c2-4582-9b1f-3bef532bd8bf` | Hermina Bogor | gagal | 3/3 | sekitar 9 menit | `Review container was not found` |
| `50815e75-846b-4d8b-b186-c3aeca9bf3cd` | Bandung | gagal | 3/3 | sekitar 9 menit | `Review container was not found` |

Kegagalan ini terjadi sebelum loop pagination. Engine lama belum memeriksa
login wall pada jalur tersebut, sehingga error autentikasi permanen dapat
terlihat seperti perubahan DOM dan diulang tiga kali.

## 4. Akar masalah

### 4.1 Volume profil berubah saat checkout dipindahkan

Login manual sebelumnya disimpan di:

```text
herminacrawler_selenium-profile
```

Stack dev sekarang dijalankan dari project Compose `crawlerservice`, sehingga
Compose otomatis membuat dan memasang:

```text
crawlerservice_selenium-profile
```

Mount worker yang terbukti saat insiden:

```text
crawlerservice_selenium-profile -> /app/.selenium-profile
```

Volume baru berukuran sekitar 200 MB dan browser di dalamnya logout. Volume
lama berukuran sekitar 1.6 GB, tetapi probe terisolasi terhadap profil lama
macet lebih dari tiga menit. Volume lama tidak boleh langsung dipasang tanpa
validasi atau pembersihan.

### 4.2 Login wall tidak dianggap error

Crawler berhasil membuka panel ulasan dan membaca lima card awal. Saat kontrol
load-more diklik, Google membuka modal login. Kode lama hanya mencari teks
`limited view` atau `tampilan terbatas`, sehingga modal login baru lolos.

### 4.3 Status partial disederhanakan menjadi completed

Job dengan hasil kurang dari target menjadi `partial_success`, tetapi batch
tanpa job berstatus `failed` tetap menjadi `completed`. UI OneBox memakai status
batch itu dan menampilkan badge hijau. Detail `counts.partial_success` tidak
menjadi status utama.

### 4.4 Eksperimen proxy tidak menyelesaikan P0

Pada audit 14 September, server dev menjalankan branch `dev-testing-proxy`
commit `4fa5a9a`. Branch tersebut sudah mencakup proxy authenticated dan retry
untuk respons proxy `407`. API tetap healthy dan worker tetap hidup, tetapi
crawl Hermina Bogor dan Bandung masih gagal menemukan review container setelah
tiga attempt.

Dengan bukti tersebut, proxy **tidak berhasil menyelesaikan insiden ini**.
Eksperimen itu belum membuktikan bahwa seluruh penggunaan proxy tidak berguna;
ia hanya membuktikan bahwa mengganti egress tidak memulihkan pagination atau
review surface pada runtime yang diuji. Proxy tidak boleh dijadikan jalur utama
recovery sebelum profil autentik, branch deployment, dan readiness Google
dibuktikan sehat.

## 5. Dugaan yang sudah dibantah

| Dugaan | Hasil |
|---|---|
| OneBox tidak dapat menjangkau Crawler | Salah; API dan endpoint integrasi menerima request |
| Token atau scope salah | Salah untuk batch yang diperiksa; enqueue dan polling berhasil |
| Worklist belum sinkron | Salah; target berhasil ditemukan dan job dijalankan |
| Target atau `scan_limit` membatasi ke 5 | Salah; request 300/3000 tetap berhenti di 5 |
| Selector panel atau kontainer scroll salah | Salah; tab aktif dan kontainer yang benar terbukti dari DOM |
| `navigator.webdriver` adalah satu-satunya penyebab | Salah; sudah `null`, pagination tetap diblokir |
| Proxy menyelesaikan kegagalan crawl | Tidak pada pengujian ini; branch proxy tetap gagal setelah 3 attempt |

## 5.1 Pendekatan resolusi yang dipilih

Pendekatan saat ini memulihkan sistem dari lapisan paling deterministik, bukan
menambah variasi jaringan baru:

1. **Bekukan eksperimen proxy untuk P0.** Simpan branch sebagai bahan
   observasi, tetapi jangan deploy sebagai baseline acceptance test.
2. **Kembalikan dev ke branch canonical.** Merge patch P0, deploy commit yang
   diketahui, dan catat image digest agar kode yang diuji dapat direproduksi.
3. **Pulihkan profil browser yang benar.** Gunakan volume dev yang stabil,
   login Google manual melalui tunnel lokal, tutup browser setup, lalu pastikan
   hanya worker yang memakai volume tersebut.
4. **Fail fast dan jujur.** Login wall menjadi `GOOGLE_AUTH_REQUIRED` yang
   non-retryable. Error perubahan DOM tetap dibedakan sebagai kegagalan review
   surface, bukan akhir daftar review.
5. **Tambahkan source readiness.** Health API/database dipisahkan dari probe
   Google agar container healthy tidak disamakan dengan crawler siap bekerja.
6. **Buktikan end-to-end.** Jalankan probe DOM, crawl target 10 pada lokasi
   dengan lebih dari 10 review, pastikan lebih dari lima card terbaca, review
   masuk DB Crawler, lalu terimpor otomatis ke OneBox.
7. **Evaluasi proxy sesudah baseline pulih.** Proxy baru diuji ulang sebagai
   opsi mitigasi rate limit atau IP reputation dengan A/B test, bukan sebagai
   syarat login atau perbaikan selector.

## 6. Perbaikan kode pada branch P0

Branch lokal:

```text
codex/p0-google-maps-pagination
```

Perubahan:

1. `ReviewSourceError` membawa `code` dan `retriable`.
2. Login wall Google dideteksi pada setiap putaran dan segera setelah klik
   load-more.
3. Kondisi tersebut dikembalikan sebagai `GOOGLE_AUTH_REQUIRED`.
4. Worker menandai error autentikasi sebagai `failed` tanpa retry sia-sia.
5. Volume Selenium memiliki nama stabil melalui
   `SELENIUM_PROFILE_VOLUME` agar tidak berubah ketika folder/project Compose
   berganti nama.
6. `scripts/diagnose_google_maps_runtime.py` menyediakan probe DOM read-only.
7. Jalur pembukaan panel juga memeriksa login wall sebelum mengeluarkan error
   selector generik, termasuk limited view sebagai error non-retryable.

Verifikasi lokal:

```text
38 focused tests passed
155 full-suite tests passed, 2 skipped
```

## 7. Recovery server dev

Recovery ini membutuhkan login Google manual. Jangan mengirim password,
cookie, atau screenshot akun ke chat.

Sebelum recovery, kembalikan deployment dev ke commit/branch yang disepakati.
Pada audit 14 September server menjalankan `dev-testing-proxy` pada commit
`4fa5a9a`, dengan satu commit milik `origin/dev` belum masuk dan dua commit
eksperimen tidak ada di `origin/dev`. Jangan menganggap hasil tes branch ini
sebagai acceptance test branch `dev`.

### 7.1 Hentikan worker dan pastikan volume yang dipakai

```bash
cd /home/ubuntu/crawlerService
docker compose stop crawl-worker
docker compose ps
docker inspect "$(docker compose ps -q crawl-worker)" \
  --format '{{range .Mounts}}{{println .Name .Destination}}{{end}}'
```

Volume dev yang dipertahankan:

```text
crawlerservice_selenium-profile
```

### 7.2 Buka browser setup memakai volume yang sama

```bash
docker rm -f voc-chromium-profile-setup 2>/dev/null || true

docker run --rm \
  -v crawlerservice_selenium-profile:/profile \
  alpine sh -lc \
  'chown -R 1000:1000 /profile && rm -f /profile/SingletonLock /profile/SingletonCookie /profile/SingletonSocket'

docker run -d \
  --name voc-chromium-profile-setup \
  --shm-size=1g \
  --security-opt seccomp=unconfined \
  -e PUID=1000 \
  -e PGID=1000 \
  -e TZ=Asia/Jakarta \
  -e CHROME_CLI="/config/.config/chromium https://www.google.com/maps" \
  -p 127.0.0.1:3000:3000 \
  -p 127.0.0.1:3001:3001 \
  -v crawlerservice_selenium-profile:/config/.config/chromium \
  lscr.io/linuxserver/chromium:version-b0ddd401
```

Perintah setup memakai image browser pihak ketiga, memasang volume cookie
secara read-write, dan melonggarkan seccomp untuk container tersebut. Jalankan
hanya setelah image/digest disetujui owner infra. Jangan expose port 3000/3001
ke `0.0.0.0`; akses hanya melalui tunnel SSH. Alternatif yang lebih kuat untuk
produksi adalah image setup milik proyek dengan digest terkunci.

Di laptop, buka tunnel:

```bash
ssh -L 3000:127.0.0.1:3000 ubuntu@192.168.1.3
```

Buka `http://127.0.0.1:3000`, login manual, buka satu lokasi Google Maps,
masuk ke tab Ulasan, klik load-more, dan pastikan lebih dari lima card tampil.

### 7.3 Tutup browser setup dan hidupkan worker

```bash
docker stop voc-chromium-profile-setup
docker rm voc-chromium-profile-setup

docker run --rm \
  -v crawlerservice_selenium-profile:/profile \
  alpine sh -lc \
  'rm -f /profile/SingletonLock /profile/SingletonCookie /profile/SingletonSocket'

cd /home/ubuntu/crawlerService
docker compose up -d --force-recreate crawl-worker
docker compose ps
docker compose logs --since=2m crawl-worker
```

## 8. Acceptance gate P0

Perbaikan belum boleh disebut selesai hanya karena container healthy.

1. Probe dengan profil login tidak menampilkan login wall.
2. Lokasi dengan `place_review_count > 5` berhasil membaca lebih dari 5 card.
3. Crawl target 10 menghasilkan `matched >= 10`, atau stop reason yang jujur
   dan dapat ditindaklanjuti.
4. Custom date range wajib memiliki `sort_applied=true`; bila tidak, hasil
   tidak boleh disebut lengkap.
5. Logout profile menghasilkan `GOOGLE_AUTH_REQUIRED`, status `failed`, dan
   hanya satu attempt.
6. OneBox menarik hasil yang baru masuk tanpa tombol tarik manual.
7. Riwayat Fetch tidak menampilkan badge hijau untuk auth/pagination failure.

## 9. To-do lintas sistem

### Codex - Crawler System

- [x] Membuktikan login wall dengan probe DOM nyata.
- [x] Menambahkan error code dan non-retryable authentication failure.
- [x] Menstabilkan nama Docker volume profil.
- [x] Menambahkan unit dan integration test.
- [ ] Deploy branch P0 setelah review.
- [ ] Jalankan probe dan real crawl setelah login manual.
- [ ] Tambahkan metric/alert untuk rasio `scanned / place_review_count` yang
  abnormal.
- [ ] Pisahkan health API dari readiness source: API sehat tidak berarti akses
  Google sehat.
- [ ] Kembalikan server dev dari `dev-testing-proxy` ke branch canonical yang
  disetujui sebelum acceptance test.
- [ ] Tambahkan klasifikasi eksplisit untuk `REVIEW_SURFACE_NOT_FOUND` agar
  perubahan DOM tetap dapat dibedakan dari autentikasi.

### Claude - OneBox

- [ ] Tampilkan `GOOGLE_AUTH_REQUIRED` sebagai status gagal dengan instruksi
  operator, bukan `Selesai`.
- [ ] Jangan menentukan badge hanya dari `batch.status=completed`; periksa
  `counts.partial_success`, `counts.failed`, dan `stop_reason`.
- [ ] Untuk custom date range, tampilkan warning/error saat
  `sort_applied=false`.
- [ ] Tampilkan target, scanned, matched, inserted, duplicate, dan failed
  secara terpisah.

### Infra/operasional

- [ ] Tetapkan satu akun Google operasional dan owner rotasi sesi.
- [ ] Dokumentasikan expiry/login renewal dan pemeriksaan berkala.
- [ ] Gunakan volume berbeda untuk dev, staging, dan production.
- [ ] Jangan menjalankan dua worker dengan volume profil yang sama.
- [ ] Evaluasi sumber resmi/berlisensi untuk mengurangi ketergantungan pada
  DOM Google Maps yang mudah berubah.

## 10. Rollback

Perubahan kode dapat di-rollback dengan kembali ke image sebelumnya. Jangan
menghapus volume profil saat rollback. Data review dan job yang sudah ada tidak
perlu dipulihkan karena investigasi dan probe tidak menulis review baru.

## 11. Temuan sekunder

- Checkout server dev berada di `0ce28a5` dan satu commit di belakang
  `origin/dev` pada audit 11 September. Pada audit ulang 14 September, checkout
  sudah berubah menjadi branch `dev-testing-proxy` commit `4fa5a9a`, satu
  commit di belakang dan dua commit di depan `origin/dev`.
- API dan database tetap healthy, tetapi dua crawl terjadwal terakhir yang
  terlihat gagal setelah tiga attempt. Ini menegaskan `/api/health` belum
  layak dipakai sebagai readiness probe crawler.
- `.env` server memuat dua deklarasi `APP_ENV` (`local` dan `staging`). Health
  efektif melaporkan `staging`. Rapikan menjadi satu nilai supaya guard secret,
  logging, dan diagnosis environment tidak ambigu.
- Container PostgreSQL masih memiliki label working directory checkout lama
  `/home/ubuntu/herminaCrawler`, walaupun API/worker sekarang berasal dari
  `/home/ubuntu/crawlerService`. Jangan hapus container atau volume database
  sebagai bagian dari perbaikan profil.
- Endpoint `/api/health` hanya membuktikan API dan database. Ia tidak
  membuktikan login Google, selector, pagination, atau kemampuan crawl.

## 12. Addendum 14 September (sore) - login manual selesai, wall tetap muncul

**Status:** akar masalah §4.2 terbukti salah sebagian; `GOOGLE_AUTH_REQUIRED`
mendeteksi gejala yang benar tetapi menyimpulkan sebab yang keliru.

### 12.1 Konteks

Setelah §7 (recovery profil) dijalankan oleh anggota tim lain - login manual
Google selesai dilakukan melalui browser setup pada volume
`crawlerservice_selenium-profile` sesuai runbook - crawl percobaan ulang pada
`hermina-crawl-worker` (branch `dev` canonical, bukan `dev-testing-proxy`)
tetap gagal dengan kode yang sama:

```text
GOOGLE_AUTH_REQUIRED - "Google Maps requires a manual sign-in before more
reviews can be loaded."
```

Ini mematahkan asumsi §4.2 dan §5.1 poin 3 bahwa login ulang akan memulihkan
akses. Audit berikut membuktikan sesi sebenarnya sudah terautentikasi.

### 12.2 Bukti sesi benar-benar login

Diperiksa langsung pada volume `crawlerservice_selenium-profile` yang dipakai
`hermina-crawl-worker` (nama cookie saja, tanpa membaca nilai terenkripsi):

```text
.google.co.id | SID, HSID, SSID, SAPISID,
                __Secure-1PSID, __Secure-3PSID,
                __Secure-1PAPISID, __Secure-3PAPISID
```

Set cookie ini adalah penanda standar akun Google yang sudah login penuh,
bukan sekadar cookie consent/personalisasi. Login manual §7 terbukti berhasil
dan tersimpan pada volume yang benar.

### 12.3 Reproduksi langsung terhadap `hermina-crawl-worker` yang sedang berjalan

Probe read-mostly dijalankan di dalam container yang sama (driver factory asli
`SeleniumGoogleMapsReviewClient._create_driver`, profil asli, tanpa proxy),
mengulang persis alur `fetch_reviews` untuk lokasi Hermina Bogor:

1. `_open_review_panel` -> 5 kartu awal terbuka, `navigator.webdriver` = `None`.
2. `_apply_sort("newest")` -> `sort_applied = False` (regresi kedua yang belum
   ditelusuri, di luar cakupan addendum ini).
3. Klik pertama pada kontrol "Lihat ulasan lainnya" (`_advance_review_list`)
   -> `_raise_if_google_auth_wall` langsung menyala, `navigator.webdriver`
   tetap `None` tepat pada momen wall muncul.

Screenshot pada momen wall menunjukkan modal "Login untuk menikmati fitur
terbaik dari Google Maps" - dan pojok kanan atas Google Maps menampilkan
tombol **"Login"**, bukan avatar akun. Artinya Google merender halaman ini
sebagai sesi anonim sepenuhnya, walaupun cookie akun valid ada di profil yang
sama persis.

### 12.4 Kesimpulan

`navigator.webdriver` yang disembunyikan (patch CDP yang sudah ada di
`_create_driver`) tidak cukup. Selenium/chromedriver punya penanda otomasi
lain yang lebih dalam dan tidak disentuh oleh patch itu - antara lain variabel
`cdc_*` yang disuntik chromedriver ke setiap halaman, dan efek samping
perintah CDP `Runtime.enable` yang dipakai Selenium secara rutin untuk
`execute_script`/`find_element`. Ini adalah sinyal deteksi otomasi yang sudah
terdokumentasi luas (lihat §12.5), independen dari status login akun.

Google kemungkinan menilai sesi ini berisiko tinggi berdasarkan sinyal
transport otomasi tersebut, dan menurunkan tampilan ke mode anonim
(soft-wall) alih-alih memblokir langsung dengan captcha. Login ulang tidak
akan pernah memperbaiki ini karena akun bukan sebabnya.

**Dampak pada §5.1 dan to-do:** poin "Pulihkan profil browser yang benar"
(§5.1.3) dan item to-do "Deploy branch P0 ... Jalankan probe dan real crawl
setelah login manual" perlu direvisi. Login manual adalah prasyarat yang
valid tetapi tidak cukup; tanpa mengatasi fingerprint CDP, setiap siklus
re-login akan berakhir dengan `GOOGLE_AUTH_REQUIRED` yang sama.

### 12.5 Rujukan eksternal

- [How New Headless Chrome & the CDP Signal Are Impacting Bot Detection](https://datadome.co/threat-research/how-new-headless-chrome-the-cdp-signal-are-impacting-bot-detection/)
- [Is Chrome CDP Stealth? Browser Automation Detection Explained](https://scrapfly.io/blog/posts/chrome-cdp-stealth-browser-automation-detection-explained)
- [CDP Detection: How Anti-Bots Catch Runtime.enable](https://scrappey.com/qa/anti-bot/what-is-cdp-detection)
- [Detecting CDP in the wild: the Runtime.enable leak and the V8 patch war](https://blog.crawlex.net/blog/detecting-cdp-runtime-enable/)
- [nodriver and undetected-chromedriver: what they patch and why it eventually breaks](https://blog.crawlex.net/blog/nodriver-undetected-chromedriver/)

## 13. Rekomendasi mitigasi: fingerprint CDP

Konteks: ini crawler ulasan bisnis milik sendiri (cabang rumah sakit/mitra),
bukan usaha melewati proteksi pembayaran atau keamanan pihak ketiga - sejalan
dengan catatan yang sudah ada di `_create_driver`.

Tiga opsi, dari yang paling murah ke paling mahal:

1. **`undetected-chromedriver`** (rekomendasi langkah pertama). Drop-in
   subclass dari `selenium.webdriver.Chrome`; API `find_element`,
   `WebDriverWait`, `execute_script`, dll. tetap sama, sehingga hampir seluruh
   `selenium_google_maps_client.py` dan test yang ada tidak perlu berubah.
   Menambal variabel `cdc_*` dan beberapa penanda otomasi klasik lain secara
   otomatis. Risiko: proyek ini sudah dilaporkan makin sulit diandalkan untuk
   target anti-bot kelas berat (mis. Cloudflare tingkat lanjut) - tetapi wall
   Google Maps yang dihadapi di sini adalah soft-wall login, bukan captcha
   penuh, jadi kemungkinan besar cukup.
2. **Patch manual ala Patchright/rebrowser-patches** (opsi menengah bila (1)
   terbukti tidak cukup). Menghindari `Runtime.enable` sama sekali di level
   sumber, bukan sekadar menambal gejalanya. Perlu lebih banyak kerja
   integrasi karena bukan drop-in replacement penuh untuk Selenium.
3. **`nodriver`** (opsi paling tahan lama, paling mahal). Penerus
   undetected-chromedriver oleh pengembang yang sama; membuang chromedriver
   binary dan lapisan protokol WebDriver sepenuhnya, terbukti nol blokir pada
   benchmark anti-deteksi 2026. Tetapi API-nya async dan tidak kompatibel
   dengan Selenium - migrasi berarti menulis ulang seluruh
   `selenium_google_maps_client.py`, bukan swap satu fungsi. Simpan sebagai
   opsi eskalasi bila (1) gagal, bukan langkah pertama.

**Langkah berikutnya yang diusulkan:** implementasi opsi 1 di `_create_driver`
sebagai perubahan kecil dan reversibel, lalu ulangi reproduksi §12.3 pada
lokasi yang sama untuk membuktikan wall tidak lagi muncul sebelum menutup P0
ini sebagai selesai.
