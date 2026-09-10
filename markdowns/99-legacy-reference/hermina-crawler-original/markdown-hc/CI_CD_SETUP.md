# CI/CD Setup — Auto Build & Deploy Backend

Ditambahkan 7 Juli 2026. Menjawab kebutuhan: push ke `main` → image otomatis ke-build dan ke-deploy ke server private, tanpa `docker compose pull` manual di server.

## Apa yang sudah diimplementasikan

File baru:

| File | Fungsi |
|---|---|
| `.github/workflows/deploy.yml` | Workflow GitHub Actions: build image → push ke GHCR → deploy ke server private |
| `docker-compose.yml` (diubah) | Ditambah field `image: ghcr.io/sayyidtrq/herminacrawler:latest` di samping `build:` yang sudah ada |

Belum dikerjakan (butuh akses server private yang gua gak punya dari sesi ini — lihat bagian "Setup Manual Wajib"):

- Install & register self-hosted GitHub Actions runner di server private / jaringan kantor.
- Buat direktori deploy tetap (`/opt/hermina-crawler`) di server itu, `git clone` repo ke situ, isi `.env`.

## Cara Kerja Workflow

Trigger: setiap push ke branch `main` yang menyentuh path backend (`app/**`, `apps/**`, `alembic/**`, `Dockerfile`, dll — commit yang cuma ubah `markdowns/` TIDAK memicu build/deploy). Bisa juga dipicu manual lewat tab Actions → "Run workflow" (`workflow_dispatch`).

```text
push ke main (path backend berubah)
        |
        v
Job 1: build-and-push   (jalan di cloud, GitHub-hosted runner)
  - checkout kode
  - build image dari Dockerfile
  - push ke ghcr.io/sayyidtrq/herminacrawler
    tag: :latest  dan  :<git-sha>
        |
        v  (job 2 baru mulai kalau job 1 sukses)
Job 2: deploy           (jalan di self-hosted runner, DI JARINGAN KANTOR)
  - docker login ghcr.io
  - cd /opt/hermina-crawler
  - git fetch + git reset --hard origin/main   (sinkronkan docker-compose.yml dkk)
  - docker compose pull                        (tarik image baru dari GHCR)
  - docker compose up -d                       (restart container pakai image baru)
  - docker image prune -f                      (buang image lama biar disk gak penuh)
```

### Kenapa perlu 2 job, bukan 1?

GitHub-hosted runner (job 1) jalan di cloud publik — **tidak bisa** menjangkau server dengan IP private yang cuma reachable dari WiFi kantor. Makanya proses dipecah: build berat (butuh compiler, cache, dll) di cloud yang cepat & gratis, sedangkan job deploy yang beneran perlu akses ke jaringan kantor dijalankan oleh **self-hosted runner** — yaitu program kecil (`actions-runner`) yang diinstall di dalam jaringan kantor itu sendiri, yang "menelepon keluar" ke GitHub untuk mengambil job (arah koneksi keluar, jadi tidak perlu buka port masuk sama sekali).

### Kenapa job deploy tidak pakai `actions/checkout`?

`actions/checkout` defaultnya `git clean` dulu sebelum checkout — itu akan **menghapus file `.env`** di server (karena `.env` untracked/gitignored). Makanya job deploy cukup `cd` ke direktori yang sudah di-`git clone` sekali secara manual, lalu `git reset --hard origin/main` — command ini cuma menyentuh file yang di-track git, `.env` aman.

### Kenapa `image:` ditambah ke `docker-compose.yml` padahal sudah ada `build:`?

Supaya file compose yang sama bisa dipakai dua cara:
- **Lokal (dev)**: `docker compose build api` tetap build dari source seperti biasa.
- **Server (prod)**: `docker compose pull` tinggal narik image jadi dari GHCR, server itu **tidak perlu punya Dockerfile/source code ter-build** — cukup `docker-compose.yml` + `.env`.

## Setup Manual Wajib (sekali saja, dikerjakan di server private)

Ini bagian yang HARUS dikerjakan langsung di server (atau mesin lain di jaringan kantor yang bisa akses server itu) — gua gak punya akses shell ke sana dari sesi ini.

### 1. Buat direktori deploy tetap + clone repo

```sh
sudo mkdir -p /opt/hermina-crawler
sudo chown $USER:$USER /opt/hermina-crawler
git clone https://github.com/sayyidtrq/herminaCrawler.git /opt/hermina-crawler
cd /opt/hermina-crawler
cp .env.example .env
nano .env   # isi DATABASE_URL (Supabase), JWT_SECRET_KEY, dll — lihat CARA_JALANIN_DOCKER.md
```

### 2. Install & register self-hosted runner

Di GitHub: buka repo → **Settings → Actions → Runners → New self-hosted runner**, pilih OS server (biasanya Linux x64). GitHub kasih 4 command siap-pakai, contoh (token beda tiap kali, jangan pakai contoh ini):

```sh
mkdir actions-runner && cd actions-runner
curl -o actions-runner-linux-x64-<version>.tar.gz -L https://github.com/actions/runner/releases/download/v<version>/actions-runner-linux-x64-<version>.tar.gz
tar xzf actions-runner-linux-x64-<version>.tar.gz
./config.sh --url https://github.com/sayyidtrq/herminaCrawler --token <TOKEN_DARI_GITHUB>
```

Saat `config.sh` tanya label runner, boleh Enter (default) — workflow ini pakai `runs-on: self-hosted` tanpa label tambahan, jadi cukup label default.

Supaya runner tetap jalan sebagai service (survive reboot/logout):

```sh
sudo ./svc.sh install
sudo ./svc.sh start
```

Cek status: repo GitHub → Settings → Actions → Runners harus menampilkan runner ini dengan status hijau "Idle".

### 3. Docker permission untuk runner

User yang menjalankan runner service harus bisa jalanin `docker` tanpa sudo:

```sh
sudo usermod -aG docker $USER
# lalu logout/login ulang, atau restart service runner
```

### 4. Test end-to-end

Push perubahan kecil ke `main` yang menyentuh path backend (atau trigger manual via tab Actions → "Build and Deploy Backend" → Run workflow), lalu pantau:
- Tab **Actions** di GitHub — job `build-and-push` harus hijau, lalu job `deploy` jalan setelahnya.
- Di server: `docker compose ps` dan `docker compose logs -f api` untuk konfirmasi container ke-restart pakai image baru.
- `curl http://<ip-private>:8000/api/health` dari jaringan kantor.

## Package Visibility di GHCR

Image pertama kali di-push akan otomatis private (mengikuti visibility repo) dan terhubung ke repo `herminaCrawler`. Tidak perlu setting tambahan — job deploy login pakai `GITHUB_TOKEN` bawaan workflow yang otomatis punya akses baca ke package repo sendiri.

## Troubleshooting

**Job `deploy` gagal, error "runner offline" / job stuck "Waiting for a runner"**
Runner service mati atau belum ke-register. Cek `sudo ./svc.sh status` di server, atau tab Runners di GitHub.

**`docker compose pull` gagal "unauthorized" / "denied"**
Login GHCR di step sebelumnya gagal atau token expired mid-job (jarang). Re-run job dari tab Actions.

**Container jalan tapi masih versi lama**
Cek `docker compose images` — kalau tag `latest` tapi digest lama, kemungkinan `docker compose pull` gak jalan atau gagal silent. Cek log job deploy di tab Actions.

**`.env` hilang / ke-reset di server**
Jangan pernah pakai `actions/checkout` buat job deploy (lihat penjelasan di atas). Kalau ini kejadian, kemungkinan ada yang mengubah workflow untuk pakai checkout — cek `.github/workflows/deploy.yml` job `deploy` tidak punya step `actions/checkout`.
