# RI-03 — Kesiapan API VoC System + Run Lokal (≤2 MD)

> Keputusan terkait: D1, D3 (lihat [RI-02](RI-02_keputusan-arsitektur.md))

## 1. Tujuan & Definition of Done
VoC System jalan lokal (Docker) dan **bisa di-curl dari dalam WSL OneBox**; kontrak API terdokumentasi; sample payload nyata tersimpan sebagai fixture.
**Selesai kalau:** `curl` health + login + reviews dari WSL sukses; file fixture `reviews_sample.json` tersimpan; API gap terkirim ke Codex.

## 2. Prasyarat & Dependency
- Docker Desktop jalan (distro `docker-desktop` sudah ada di WSL [verified]).
- Tidak butuh branch OneBox (belum menyentuh kode OneBox).

## 3. File Target
| File | Status |
|---|---|
| `hermina_crawler/docker-compose.yml` | [baca-saja] — cara run |
| `markdowns/07-data-and-seeding/field-mapping/implementation-plan/fixtures/reviews_sample.json` | [baru] |
| `markdowns/07-data-and-seeding/field-mapping/implementation-plan/api-contract-notes.md` | [baru] — catatan kontrak + base URL dev |

## 4. Langkah Implementasi
1. **Run VoC lokal:** `docker compose up -d` di repo `hermina_crawler`; cek `docker compose ps` + buka `http://localhost:<port>/api/docs`. Catat port aslinya. *(0.5 hari, termasuk beresin isu env)*
2. **Buat service user untuk OneBox (D3):** register/seed user khusus mis. `onebox-svc@internal` — via endpoint register/CLI seed yang ada. Simpan credential HANYA di catatan lokal (nanti masuk config per-env OneBox, bukan di-commit).
3. **Uji dari dalam WSL OneBox** (penting — membuktikan network path WSL→Windows host):
   ```bash
   wsl -d Ubuntu22.04-Swoole
   curl -s http://<host-ip>:<port>/api/health
   curl -s -X POST http://<host-ip>:<port>/api/auth/login -d 'username=onebox-svc@internal&password=***' -H 'Content-Type: application/x-www-form-urlencoded'
   curl -s 'http://<host-ip>:<port>/api/reviews?page=1&page_size=5&latest_first=true' -H 'Authorization: Bearer <token>'
   ```
   ⚠️ `localhost` di dalam WSL ≠ Windows host. Kalau gagal, pakai IP host dari `ip route | grep default` (gateway) atau `host.docker.internal`. Catat base URL final yang berfungsi → dipakai RI-04. `[assumption]` — wajib dites, jangan ditebak.
4. **Simpan fixture:** response reviews (≥3 item, minimal 1 yang `analyzed=true`) → `fixtures/reviews_sample.json`. Ini bahan mock RI-04.
5. **Kirim API gap ke Codex** (dari RI-01 §8): param `updated_since`; pastikan `review_hash` ikut di response; catatan unique global `review_hash`.

## 5. Cara Verifikasi
Ketiga curl di langkah 3 return 200 dari **dalam WSL**; fixture berisi field yang cocok dengan tabel mapping RI-01.

## 6. Risiko & Rollback
Networking WSL↔Windows host paling sering bikin buntu — alokasikan waktu; alternatif: jalankan crawler container di distro WSL yang sama. Rollback: `docker compose down`.

## 7. Temuan & Deviasi
(diisi saat eksekusi)

## 8. API Gap / Handoff ke Codex
Lihat Langkah 5. Tambahan: minta Codex freeze kontrak response `/api/reviews` (jangan rename field tanpa koordinasi) mulai sekarang.

## 9. Estimasi (2 MD)
Hari 1: langkah 1–3. Hari 2: langkah 4–5 + dokumentasi kontrak.
