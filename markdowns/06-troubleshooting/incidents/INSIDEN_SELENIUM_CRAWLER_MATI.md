---
title: "Insiden — Selenium Crawler tidak bisa start"
date: 2026-08-26
selesai: 2026-08-27
type: incident
project: Voice of Customer
status: SELESAI — penyebab ditemukan dan diperbaiki, penarikan terbukti pulih
dampak: seluruh penarikan ulasan berhenti sekitar satu hari, semua company
tags:
  - voc
  - crawler
  - selenium
  - incident
---

# Insiden — Selenium Crawler tidak bisa start

> [!success] Selesai 27 Agustus 2026
> Penyebabnya **kunci profil Chromium yang tertinggal**, bukan display dan
> bukan versi. Dilepas, dan penarikan langsung pulih — dua kali berturut-turut
> dengan ulasan yang benar-benar masuk.

**Host:** `192.168.1.3:8000` — Hermina Review Intelligence, env `staging`
**Ditemukan:** 26 Agustus 2026 · **Diperbaiki:** 27 Agustus 2026

---

## Gejala

```json
{
  "status": "failed",
  "total_fetched": 0,
  "error_message": "Selenium browser failed to start. Please check Chrome and ChromeDriver installation.",
  "metadata": { "headless": false }
}
```

Gagal **instan** (~3 detik), konsisten, lintas lokasi, lintas company, bahkan
pada target satu ulasan.

---

## Penyebab sebenarnya

`/app/.selenium-profile/` menyimpan tiga penanda "sedang dipakai":

```
SingletonCookie -> 4999589813831738688
SingletonLock   -> 62f498dec439-3828
SingletonSocket -> /tmp/org.chromium.Chromium.BKcQTp/SingletonSocket
```

`SingletonLock` menyebut **host `62f498dec439` PID `3828`** — container yang
sudah tidak ada. Chromium menolak profil yang penandanya menyebut proses lain:

```
The profile appears to be in use by another Chromium process (3828)
on another computer (62f498dec439). Chromium has locked the profile
so that it doesn't get corrupted.
```

**Kenapa bertahan berhari-hari dan kebal restart:** profilnya ada di named
volume `selenium-profile`, jadi penandanya hidup lebih lama daripada container
yang membuatnya. Restart justru mengganti hostname container, dan penanda lama
makin pasti dianggap milik "komputer lain".

---

## Perbaikan

```bash
docker exec hermina-crawl-worker bash -lc 'rm -f /app/.selenium-profile/Singleton*'
docker exec hermina-review-api  bash -lc 'rm -f /app/.selenium-profile/Singleton*'
```

Hanya berkas `Singleton*`, **bukan profilnya** — profil itu menyimpan sesi dan
cookie Google yang membuat halaman ulasan bisa dibuka tanpa verifikasi
berulang. Menghapus seluruh profil menukar satu masalah dengan masalah lain
yang lebih sulit dilihat.

Tidak perlu restart, tidak perlu ubah env, tidak perlu deploy ulang.

---

## Bukti pulih

Dua penarikan nyata lewat jalur yang dipakai layar Fetch Jobs
(OneBox dev → `Voc/crawlStart` → antrean Crawler → worker):

| Batch | Lokasi | Hasil |
|---|---|---|
| `f06bbb60` | HGA Depok | `completed` · fetched 3 · **inserted 2** · duplicate 1 · failed 0 |
| `5b672f4b` | Hermina depok | `completed` · fetched 3 · **inserted 3** · duplicate 0 · failed 0 |

Yang dipakai sebagai bukti bukan status hijaunya, melainkan **ulasan yang
benar-benar masuk**. Status sukses dengan nol ulasan adalah kegagalan yang
menyamar, dan pemantau pertama insiden ini pernah tertipu persis begitu.

---

## Dugaan yang TERBANTAH — supaya tidak diulang

| Dugaan awal | Kenyataan |
|---|---|
| `selenium_headless: false` tanpa display | **Salah untuk jalur ini.** Worker berjalan di bawah `xvfb-run`, Xvfb hidup di `:99`, dan prosesnya memang punya `DISPLAY=:99` |
| Chrome dan ChromeDriver beda versi | **Salah.** Keduanya Chromium 151.0.7922.169 |
| Kebanyakan menarik 39 Puskesmas sekaligus | **Salah.** Gagal juga pada target 1 ulasan di lokasi lain. Batch 39 Puskesmas justru sempat `partial_failed` 1030/1950 — sebagian besar berhasil |
| Kuota company habis | **Salah.** Gagal sebelum satu ulasan pun disentuh |

Dokumen versi 26 Agustus menempatkan "headless tanpa display" sebagai dugaan
terkuat. Itu keliru — dan keliru karena bukti display baru bisa diperiksa
setelah ada akses shell; sebelumnya seluruh penalaran bertumpu pada
`metadata.headless: false`, yang memang benar tetapi bukan penyebabnya.

---

## Yang MASIH terbuka: `/api/fetch-jobs` tetap gagal

Kedua container tidak sama:

| Container | Menjalankan | Xvfb | DISPLAY |
|---|---|---|---|
| `hermina-crawl-worker` | di bawah `xvfb-run` | jalan `:99` | `DISPLAY=:99` |
| `hermina-review-api` | `uvicorn` langsung | **tidak jalan** | **tidak ada** |

`POST /api/fetch-jobs` dilayani container **API**, jadi ia mencoba Chromium
non-headless tanpa layar dan tetap gagal — mayat `[chromium] <defunct>` di
sana adalah sisa tiap percobaan.

Layar OneBox tidak memakai jalur itu (ia lewat antrean ke worker), jadi ini
tidak menghalangi siapa pun hari ini. Tetapi ia perangkap: apa pun yang kelak
memanggil endpoint sinkron itu akan gagal tanpa sebab yang terlihat.

### Headless SUDAH DICOBA — dan dikembalikan

`SELENIUM_HEADLESS=true` disetel di `.env`, kedua container dibuat ulang, lalu
diuji. Hasilnya **jangan diulang**:

| | Jalur sinkron `/api/fetch-jobs` | Jalur worker (dipakai layar) |
|---|---|---|
| `headless=false` | gagal — browser tidak start | **completed**, ulasan masuk (2 dan 3) |
| `headless=true` | browser START, tetapi Google membalas *"Google Maps is showing a limited view"* | **retry_wait**, nol ulasan |

Headless memang menyembuhkan container API — pesan galatnya berubah dari
"browser failed to start" menjadi "limited view", bukti bahwa Chromium
akhirnya jalan. Tetapi Google memperlakukan sesi headless berbeda dan menolak
menyajikan daftar ulasan penuh, dan efeknya **menular ke worker yang tadinya
bekerja**.

Menukar satu jalur yang tidak dipakai siapa pun dengan satu jalur yang dipakai
setiap hari bukan perbaikan. `.env` dikembalikan ke `false`, container dibuat
ulang, dan penarikan diverifikasi jalan kembali (batch `28c0e941` —
`completed`, fetched 3, failed 0).

Cadangan nilai lama ada di `~/herminaCrawler/.env.bak.sebelum-headless`.

> [!note] Nama service-nya `api` dan `crawl-worker`
> `docker compose up -d --force-recreate api worker` **gagal tanpa mengubah
> apa pun** — "worker" bukan nama service, dan container tetap memegang env
> lama sementara `.env` sudah berubah. Yang benar:
> ```bash
> cd ~/herminaCrawler && docker compose up -d --force-recreate api crawl-worker
> ```

### Kalau jalur sinkron itu memang perlu dihidupkan

Jalan yang benar bukan headless, melainkan **memberi container API display
sendiri** — jalankan `uvicorn` di bawah `xvfb-run` seperti worker, sehingga
kedua container berjalan non-headless dengan syarat yang sama. Itu perubahan
pada entrypoint/compose, bukan pada satu baris env, dan belum dikerjakan.

---

## Pencegahan kambuh

Kunci ini akan tertinggal lagi setiap kali container mati saat Chromium masih
hidup. Yang menghentikan pola itu bukan mengingatnya, melainkan
membersihkannya di awal:

```bash
# di entrypoint container, sebelum worker/api dijalankan
rm -f /app/.selenium-profile/Singleton*
```

Aman dijalankan berulang: kalau tidak ada proses yang benar-benar memakai
profil, penanda itu memang sampah; kalau ada, ia dibuat ulang seketika.

---

## Pelajaran

**Kegagalan ini cepat dan senyap.** Ia mengembalikan HTTP 200 dengan
`status: failed` di badan, jadi pemantauan yang hanya melihat kode HTTP akan
melaporkan semuanya sehat.

Dan alasannya tidak pernah sampai ke layar: OneBox menerima `error` dari
Crawler tetapi membuangnya saat memetakan batch, sehingga Riwayat Fetch hanya
bisa menulis "Gagal". Satu-satunya cara mengetahui penyebabnya adalah
memanggil Crawler sendiri lewat curl — yang berarti tidak seorang pun di luar
developer bisa menindaklanjuti penarikan yang gagal.

Sudah diperbaiki di branch `feature/DNGO19-3523_VOC-Review-Manage-Action-Improvement`
(commit `e823b87f75`): `crawlHistoryAction` meneruskan `alasan`, dan layar
menampilkannya di bawah status.

Aturan memantau endpoint ini:

> Sebuah penarikan hanya berhasil kalau field `status` **benar-benar ada**,
> nilainya bukan `failed`, **dan** `total_inserted` lebih besar dari nol.

---

## Tautan

- [[VOC_CRAWLER_SERVICE_CONFIG]] — konfigurasi, token, dan tenant Crawler
- [[VOC_SCHEDULER_TIDAK_JALAN]] — insiden lain dengan pola "gagal tanpa suara"
