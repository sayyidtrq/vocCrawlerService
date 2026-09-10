# OneBox Local Dev — Setup & Troubleshooting Guide (untuk Intern)

> Panduan setup environment OneBox lokal (WSL + Docker Swarm) + cara resolve error yang sering muncul saat checkout branch baru & build image.
> Ditulis dari pengalaman setup nyata — semua error di bagian Troubleshooting itu beneran kejadian, bukan teori.
> Environment: WSL Ubuntu (distro `Ubuntu22.04-Swoole`), path repo: `/var/www/html/onecloud`.

---

## 0. TL;DR — Alur Cepat

Kalau environment udah pernah jalan dan lu cuma mau kerja di branch baru:

```bash
cd /var/www/html/onecloud

# a. pastikan MySQL nyala (paling sering kelupaan)
sudo service mysql start          # atau start container DB-nya

# b. amankan config lokal, pindah branch
git stash push -m "local config" -- onecloud/app/config/development.php onecloud/app/config/local.php
git checkout develop && git pull origin develop
git checkout -b feature/DNGO19-XXXX_Deskripsi-Fitur
git stash pop

# c. siapkan image + hapus stack lama + deploy stack branch ini
docker tag ciptadra/onecloud:<image-yg-ada> ciptadra/onecloud:<base-version>   # kalau perlu (lihat §3.4)
docker stack rm dev_<suffix-branch-lama>                                        # kalau ada yg nyangkut port
./dev.sh local up

# d. masuk container + jalankan server
./dev.sh local enter
./swoole-dev.sh
```

Kalau ada yang error, lompat ke **§5 Troubleshooting**.

---

## 1. Konsep Penting (baca ini biar ngerti kenapa error muncul)

### 1a. Ini Docker Swarm, bukan compose biasa
Service dijalankan sebagai **swarm stack**. Cek yang jalan pakai `docker service ls` (bukan cuma `docker ps`).

### 1b. Nama stack diturunkan dari nama BRANCH git
Script `dev.sh` + `path.sh` bikin nama stack `dev_<SUFFIX>`, di mana `SUFFIX` = hasil "normalisasi" nama branch:

| Branch git | SUFFIX | Nama container webapp |
|---|---|---|
| `develop` | `develop` | `dev_develop_webapp` |
| `hotfix/1.118.1` | `1_118_1` | `dev_1_118_1_webapp` |
| `feature/DNGO19-3346_Media-Crawler...` | `DNGO19-3346` | `dev_DNGO19-3346_webapp` |

**Konsekuensi:** tiap kali lu ganti branch, `dev.sh` nyari container dengan nama beda. Kalau stack buat branch itu belum di-deploy → error (lihat §5).

### 1c. Kode di-bind-mount
Kode app di-mount dari host ke dalam container. Artinya: **edit kode langsung kebaca tanpa rebuild image**. Image cuma nyediain runtime (PHP + extension + vendor).

### 1d. MySQL jalan terpisah
Swoole server konek ke MySQL. Kalau MySQL belum nyala → `Connection refused` (§5.1). MySQL **bukan** bagian dari stack webapp, jadi harus dipastikan nyala sendiri.

---

## 2. Perintah `dev.sh` (cheat sheet)

Format: `./dev.sh local <command>` (dijalankan dari `/var/www/html/onecloud`).

| Command | Fungsi |
|---|---|
| `up` | deploy stack untuk branch aktif + tunggu webapp siap + auto masuk |
| `enter` | masuk ke container webapp (as user biasa) |
| `root` | masuk ke container as root |
| `www` | masuk as www-data |
| `logs` | tail log service webapp |
| `stat` | status task stack |
| `down` | hapus stack branch aktif |

Di dalam container, jalankan server dev: `./swoole-dev.sh`

---

## 3. Setup Langkah demi Langkah

### 3.1 Nyalakan MySQL
Wajib duluan. Kalau lupa → error `Connection refused`.
```bash
sudo service mysql start
# verifikasi:
mysql -u root -p -e "SELECT 1"
```

### 3.2 Amankan config lokal sebelum pindah branch
Ada 4 file config yang lu ubah lokal dan **TIDAK BOLEH di-commit**:
`.env`, `.env.local`, `onecloud/app/config/development.php`, `onecloud/app/config/local.php`

`.env` & `.env.local` biasanya gitignored (aman sendiri). Yang tracked (muncul di `git status`) = `development.php` & `local.php` → stash dulu biar pindah branch mulus:
```bash
git stash push -m "local dev config" -- onecloud/app/config/development.php onecloud/app/config/local.php
```

> **Alternatif anti-ribet** (biar nggak stash-pop tiap ganti branch):
> ```bash
> git update-index --skip-worktree onecloud/app/config/development.php onecloud/app/config/local.php
> ```
> Setelah ini git "pura-pura nggak liat" perubahan lu di 2 file itu. Gotcha: kalau develop update file itu, lu nggak dapet update-nya (perlu `--no-skip-worktree` buat sync sesekali).

### 3.3 Pull develop & buat feature branch
```bash
git checkout develop
git pull origin develop
git checkout -b feature/DNGO19-XXXX_Deskripsi-Fitur     # nomor tiket dari Jira
git stash pop                                            # balikin config (kalau tadi stash)
```
> **Naming branch** ikut tiket Jira: `feature/<KODE-TIKET>_<Deskripsi-Pakai-Dash>`.
> Contoh: `feature/DNGO19-3346_Media-Crawler-Google-Business-Review`

### 3.4 Siapkan Docker image untuk branch ini
`./dev.sh local up` bakal nyari image `ciptadra/onecloud:<base-version>-<suffix>-<hash>`. Kalau nggak ada, dia fallback nyari base version, dan kalau tetep nggak ada → coba build (dan **build lokal-nya broken**, lihat §5.3).

Cek image yang lu punya:
```bash
docker images | grep ciptadra/onecloud
```
Kalau base version yang dibutuhkan branch (mis. `1.118.0-rc1`) nggak ada, tapi lu punya image lain (mis. `1.118.0-1_118_1-xxxx`), **retag** biar dipakai:
```bash
docker tag ciptadra/onecloud:1.118.0-1_118_1-700fe175a8c642c ciptadra/onecloud:1.118.0-rc1
```
> Aman buat lokal karena kode di-bind-mount (image cuma runtime). **Cara resmi (tanya tim):** kemungkinan image harusnya di-`docker pull` dari registry private, bukan di-build/retag. Konfirmasi ke lead/infra.

### 3.5 Deploy stack + masuk + jalankan
```bash
# hapus stack branch lama kalau masih nyangkut (lihat §5.4 soal port)
docker stack rm dev_<suffix-lama>

./dev.sh local up          # deploy + auto masuk
# atau kalau udah jalan, tinggal:
./dev.sh local enter

# di dalam container:
./swoole-dev.sh
```

---

## 4. Aturan Penting (jangan dilanggar)

1. **Jangan commit** `.env`, `.env.local`, `onecloud/app/config/development.php`, `onecloud/app/config/local.php`. Jangan `git add .` — add per-file.
2. **Jangan kerja/commit di branch `hotfix/*` atau `release/*`** yang bukan punya lu.
3. Satu tiket Jira = satu feature branch.
4. `docker stack rm` aman (nggak hapus data DB), tapi pastikan lu hapus stack yang bener.

---

## 5. Troubleshooting (error nyata + fix)

### 5.1 `getDbPool failed ... SQLSTATE[HY000] [2002] Connection refused`
**Penyebab:** MySQL belum nyala. (Ini "connection refused" = nggak ada yang dengerin di port DB, beda dari "access denied" yang berarti salah password.)
**Fix:**
```bash
sudo service mysql start
# lalu ulang ./swoole-dev.sh
```

### 5.2 `"docker exec" requires at least 2 arguments`
Muncul saat `./dev.sh local enter`.
**Penyebab:** stack untuk branch aktif belum di-deploy, jadi `docker ps -f name=dev_<suffix>_webapp` kosong → nama container ilang.
**Fix:** deploy dulu:
```bash
./dev.sh local up
```

### 5.3 `Version ... not found, building` lalu `./dev.sh: line 25: No such file or directory`
**Penyebab:** image base yang dibutuhkan branch nggak ada di lokal, script coba build, tapi jalur build-nya broken (`pushd onecloud` bikin path recursive-nya salah).
**Fix:** jangan build — sediakan image base-nya via retag (atau pull dari registry):
```bash
docker images | grep ciptadra/onecloud
docker tag ciptadra/onecloud:<tag-yg-ada> ciptadra/onecloud:<base-version-yg-dicari>
./dev.sh local up
```
(base version yang dicari kelihatan di baris `Finding version <base>-<suffix>-<hash>`.)

### 5.4 `port '8001' is already in use by service 'dev_<lama>_webapp' as an ingress port`
**Penyebab:** stack dari branch lama masih jalan dan masih pegang port. Nggak bisa ada 2 stack di port yang sama.
**Fix:** hapus stack lama, tunggu, ulang:
```bash
docker stack rm dev_<suffix-lama>       # mis. dev_1_118_1
docker service ls                       # tunggu sampai service lama hilang (~15-30s)
./dev.sh local up
```

### 5.5 Error soal nama database (unknown database `onecloud_..._<suffix>`)
**Penyebab:** `ONECLOUD_DB_NAME` diturunkan dari nama branch, jadi tiap branch nyari DB beda. DB yang di-restore mungkin cuma ada untuk satu nama.
**Fix:** pin nama DB di `.env.local` biar semua branch pakai DB yang sama:
```bash
grep ONECLOUD_DB_NAME .env .env.local
# kalau kosong, set ke DB yang udah ada isinya, mis:
# ONECLOUD_DB_NAME=onecloud_local
```

---

## 6. Kalau Masih Stuck
1. Cek `docker service ls` — service apa yang jalan/mati.
2. Cek `./dev.sh local logs` — log webapp.
3. Screenshot error + langkah yang udah dicoba, tanya di grup.

*Guide ini living document — kalau nemu error/solusi baru, tambahin ke §5.*
