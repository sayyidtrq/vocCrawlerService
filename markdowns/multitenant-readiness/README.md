---
title: Multi-Tenant Readiness — Index
aliases:
  - MT Index
  - Multi-Tenant Readiness
tags:
  - voc
  - multitenant-readiness
  - index
status: living
updated: 2026-10-21
owner: Sayyid
decision: opsi-D-push-worklist
branch: feature/multitenant-readiness
related:
  - "[[01-PLAN]]"
  - "[[02-DESIGN]]"
  - "[[03-IMPLEMENTATION]]"
  - "[[04-OPEN-QUESTIONS]]"
  - "[[BRAINSTORM-multi-tenant-voc]]"
  - "[[SPEC-multi-tenant-opsi-c]]"
  - "[[MEETING_NOTES_AGUNG_VoC-Sync]]"
  - "[[MUST_READ]]"
---
# Multi-Tenant Readiness — Index

> [!abstract] Navigasi
> [[README|Index]] · [[01-PLAN|Plan]] · [[02-DESIGN|Design]] · [[03-IMPLEMENTATION|Implementation]] · [[04-OPEN-QUESTIONS|Open Questions]]

Folder ini adalah **satu-satunya tempat** untuk status kesiapan multi-tenant (multi-site) VoC.
Dokumen lama tetap ada sebagai sumber, tapi kalau bertentangan, folder ini yang dipakai untuk
pekerjaan baru — **kecuali ADR**, yang tetap otoritas tertinggi (lihat `integrations/MUST_READ.md`).

---

## Ringkasan

> [!summary] Posisi per 2026-10-21
> **Model:** OneBox adalah source of truth dan control panel. Satu site = satu company. Tenant hidup/mati karena
> **paket VoC** diaktifkan/dimatikan di OneBox; saat aktif, OneBox memanggil crawler untuk mendaftarkan tenant dan
> membuat token, lalu token disimpan di Connection dan tampil di Setup Parameter. **Semua panggilan satu arah
> OneBox → crawler (opsi D):** OneBox mengirim (push) snapshot worklist memakai token tenant; crawler tidak
> memegang kredensial OneBox. Crawler **tanpa setup manual** dan membagi worker antar tenant dengan
> **weighted round robin**. Apify dipakai lewat satu akun platform yang anonim bagi tenant; biaya dicatat per tenant.
>
> **Kondisi kode crawler:** lapisan data sudah multi-tenant (`company_id` di semua tabel, token per company),
> tapi config & orkestrasi masih satu tenant (`ONEBOX_SITE_ID`/`ONEBOX_COMPANY_ID`, CLI manual, antrean FIFO).
> Ada bahaya laten refresh lintas tenant yang harus diamankan sebelum site 177 diberi token
> ([[02-DESIGN#2.4 Bahaya laten yang sudah ada hari ini|Design §2.4]]).
>
> **Belum diverifikasi:** kode OneBox (repo sedang disiapkan) — sebagian hal sudah diimplementasi di sana (Q-31).
> **Dev:** site 169 (utama) dan site 177 (testing).

## Isi folder

| File | Isi | Kapan dibaca |
|---|---|---|
| [[01-PLAN]] | Tujuan, scope, fase, urutan, gerbang keputusan, status per fase | Mau tahu "kita di mana & berikutnya apa" |
| [[02-DESIGN]] | Kondisi sekarang (as-is) vs target (to-be), kontrak API, model data, aturan, risiko | Mau tahu "bentuknya seperti apa & kenapa" |
| [[03-IMPLEMENTATION]] | Task `MT-xx` per sisi, file yang disentuh, acceptance, test matrix | Mau mulai ngoding |
| [[04-OPEN-QUESTIONS]] | Register pertanyaan terbuka `Q-xx` + jawaban | Mau menjawab / mengecek apa yang masih belum jelas |

## Penanda yang dipakai

| Penanda | Arti |
|---|---|
| `[code]` | Diverifikasi dengan membaca kode di repo ini (path:line disebut) |
| `[doc]` | Diambil dari dokumen existing (nama file disebut) — belum tentu sesuai kode |
| `[asumsi]` | Dugaan yang belum dibuktikan — jangan dijadikan dasar keputusan |
| `Q-xx` | Merujuk pertanyaan terbuka; tautan langsung: `[[04-OPEN-QUESTIONS#Q-07]]` |
| `MT-xx` | Merujuk task di [[03-IMPLEMENTATION]] |

Status task: `todo` · `wip` · `done` · `blocked` (selalu sebut `Q-xx` penghambatnya) · `dropped`.

---

## Protokol update (wajib diikuti)

Dokumen ini sengaja dibuat untuk **terus diperbarui** dengan jawaban dari pertanyaan terbuka.

1. **Menjawab pertanyaan:** di [[04-OPEN-QUESTIONS]], isi blok *Jawaban* di heading `Q-xx`
   (tulis juga sumbernya: siapa / meeting / tanggal), ubah *Status* di papan jadi `answered`, pindahkan
   barisnya ke tabel "Sudah terjawab", dan perbarui properti `open_count` / `answered_count`.
2. **Propagasi:** buka panel **Backlinks** di catatan Q itu, atau cari `Q-07` (Ctrl+Shift+F) di folder ini.
   Ganti teks bersyarat ("tergantung Q-07") dengan keputusannya. Task yang tadinya `blocked` → `todo`.
3. **Keputusan arsitektur** (mengubah boundary, kontrak API, atau model kredensial) → buat ADR baru di
   `markdowns/decisions/` (kandidat: `ADR-0006-multi-tenant-mechanism.md`), lalu tautkan dari sini.
4. **Pertanyaan baru** → tambah baris `Q-xx` berikutnya (jangan pakai ulang nomor), tautkan dari bagian
   dokumen yang memicunya.
5. **Catat di Changelog** di bawah: tanggal, apa yang berubah, Q/MT yang terdampak.
6. Ubah properti `updated` (dan `status` bila berubah) di frontmatter file yang disentuh.

---

## Sumber yang disintesis

| Dokumen | Peran | Catatan |
|---|---|---|
| `decisions/BRAINSTORM-multi-tenant-voc.md` (2026-07-28) | Asal analisis opsi A/B/C | Header masih "eksplorasi, belum keputusan" walau spec sudah memilih C |
| `decisions/SPEC-multi-tenant-opsi-c.md` | Rancangan Opsi C | "Disetujui untuk diimplementasikan · belum ada kode" |
| `decisions/MEETING_NOTES_AGUNG_VoC-Sync.md` §3.1, §3.2, item terbuka #1 | Konfirmasi 1 deployment; spec **perlu revisi mekanisme** | Tanggal meeting ± akhir Juli 2026 |
| `decisions/ADR-0001/0002/0003` | Boundary OneBox ↔ Crawler | OneBox = SoR, pull worklist, antrean durable |
| `integrations/SAYYID_TASK_BREAKDOWN.md` task 5 / `SAYYID_TASK_VALIDATED.md` 5.5 | Test multi-account/company/site (Critical, Not Started) | |
| `integrations/EPIC_BACKLOG.md` E7 | "Multi-Tenant Onboarding — tinggal dipecah jadi story" | |
| `decisions/REVISI_CEO_07-08-2026.md` | Uji stabilitas banyak company crawling bersamaan; dashboard per-site | Kebutuhan bisnis |
| Kode `dev` @ `7021cd0` | Kondisi nyata | Lihat [[02-DESIGN#2. Kondisi sekarang (as-is)\|02-DESIGN §2]] |

Dokumen yang **tidak dipakai** (superseded): `integrations/implementation-plan-onebox/RI-06_tenant-mapping.md`.

---

## Changelog

| Tanggal | Perubahan | Terkait |
|---|---|---|
| 2026-10-21 | Folder dibuat. Sintesis brainstorm + spec + meeting Agung + audit kode `dev`. 24 pertanyaan terbuka dicatat. Bahaya laten refresh worklist lintas-tenant ditemukan. | semua |
| 2026-10-21 | Jawaban Sayyid: model diganti ke provisioning paket VoC + OneBox control panel + weighted round robin + nol setup manual. 13 Q terjawab, Q-06 di-drop, Q-25–Q-31 ditambah. Design/Plan/Implementation ditulis ulang; ID task MT dinomori ulang. | Q-01–Q-31 |
| 2026-10-21 | Keputusan **opsi D**: OneBox push snapshot worklist (`PUT /worklist`, berversi, atomik), crawler tanpa kredensial OneBox — amandemen ADR-0003 D1. Q-07 & Q-16 terjawab oleh desain, Q-27 di-drop, Q-32 (queue OneBox) & Q-33 (`snapshot_version`) ditambah. MT-12/34/43 `dropped`, MT-35 baru. | Q-03, Q-07, Q-16, Q-27, Q-32, Q-33 |
| 2026-10-21 | Perubahan desain Apify: satu akun platform, anonim bagi tenant, tanpa rotasi/top-up per tenant. Q-11 terjawab, Q-34 (batas akun bersama) ditambah. | Q-11, Q-34, MT-41 |
| 2026-10-21 | MT-03 putaran 1 (baca kode OneBox): `VocWorklist::forSite` siap dipakai ulang, **tidak ada outbox** untuk panggilan keluar, "paket VoC" = 6 benefit terpisah, token per Connection. Q-31/Q-32 partial; Q-35, Q-36 ditambah. | Q-31, Q-32, Q-35, Q-36, MT-03 |
| 2026-10-21 | **MT-02 selesai** (kode): guard `WorklistTenantMismatchError`; 5 test baru; full suite 249 lulus, 2 gagal pra-ada, 0 regresi. Belum di-commit. | MT-02, T9 |
