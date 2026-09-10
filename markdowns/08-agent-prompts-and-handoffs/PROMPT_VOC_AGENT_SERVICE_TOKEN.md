# Prompt untuk AI agent VoC System — SUDAH DIKIRIM & SELESAI

> **Status: CLOSED (2026-07-21).** VOC-CS-03 sudah diimplementasikan dan crawler
> sudah di-redeploy. `GET /api/integration/v1/whoami` dan `/reviews` terverifikasi
> hidup di env staging, termasuk permintaan tambahan whoami di bagian bawah prompt.
> Arsip — tidak perlu dikirim ulang. Langkah lanjutannya ada di
> `VOC_ONEBOX_LIVE_PULL.md` §7.

<details>
<summary>Isi prompt asli</summary>

> Konteks: OneBox sudah siap consume. Yang menahan hanya auth di sisi VoC.
> Salin blok di bawah ini ke agent yang pegang repo `herminaCrawler`.

---

Tolong implementasikan **VOC-CS-03 (Service-to-Service Auth dan Tenant Binding)** sesuai
spec yang sudah ada di repo: `markdowns/04-implementation-plans/crawler-system/implementation-plan-crawler-system/VOC-CS-03_service-auth.md`.

**Kenapa ini prioritas:** endpoint `GET /api/integration/v1/reviews` sudah jadi dan service
layer-nya (`app/services/integration_review_service.py`) sudah lengkap — keyset cursor,
watermark `sync_updated_at`, projection eksplisit. Satu-satunya yang bikin endpoint itu tidak
bisa dipakai adalah `require_service_principal()` di
`apps/api/app_api/routers/integration_reviews.py:48-64` yang masih melempar
`503 SERVICE_AUTH_NOT_READY`. `apps/api/app_api/service_auth.py` dan model `ApiClient`
belum ada sama sekali.

Selama itu belum jadi, OneBox terpaksa pakai `GET /api/reviews` dengan **email + password user
manusia** yang disimpan plaintext-ish di row `Connection` OneBox. Itu yang mau kita hilangkan.

**Yang OneBox butuhkan dari hasil pekerjaan ini (tolong pastikan kepenuhan):**

1. Bearer token opaque berformat `voc_<env>_<key_id>.<secret>` yang bisa dipakai langsung di
   header `Authorization` — tanpa login, tanpa refresh, tanpa expiry harian.
2. Token terikat mati ke satu `company_id`. Token company A **tidak boleh** bisa membaca
   review/location company B, termasuk lewat parameter `location_id` yang ditebak.
3. Scope `reviews:read` diberlakukan (403 `INSUFFICIENT_SCOPE` kalau kurang).
4. Ada cara menerbitkan token dari CLI, dan raw token ditampilkan **sekali** lalu tidak
   pernah masuk log.
5. `GET /api/auth/login` + `/api/auth/me` (JWT user) **tetap jalan** — FE dan jalur interim
   OneBox masih bergantung ke situ.

**Satu pertanyaan yang perlu dijawab balik ke saya:**
Setelah token diterbitkan, apa persisnya string yang harus saya paste ke config OneBox, dan
apakah `company_id` bisa saya verifikasi dari sisi OneBox tanpa harus buka DB VoC? Kalau
belum ada endpoint semacam `GET /api/integration/v1/whoami` yang mengembalikan
`{company_id, company_name, scopes}` untuk service token, tolong tambahkan — OneBox
memerlukannya untuk memvalidasi bahwa token yang dipasang di suatu SiteId benar-benar milik
tenant yang diharapkan, sebelum menarik satu baris pun.

Jangan ubah bentuk response `GET /api/integration/v1/reviews` — OneBox sudah dikodekan
terhadap contract v1 yang sekarang (`data[]`, `page.next_cursor`, `page.checkpoint_cursor`,
`page.has_more`).

---

</details>

## Hasil (2026-07-21)

Semua 5 poin acceptance terpenuhi. Yang berubah dari rencana awal: karena
`GET /api/integration/v1/whoami` **jadi disediakan**, guard tenant OneBox tidak lagi
di-skip di mode service — `assertTenant()` sekarang berlaku di kedua mode, plus
pengecekan scope `reviews:read` di depan. Itu perubahan kode kecil di OneBox, bukan
sekadar ganti `Connection.Options` seperti yang diperkirakan di bawah.

- Bentuk response `/api/integration/v1/reviews` tidak berubah — `fetchPage()` jalan apa adanya.
- Mode `user` tetap dipertahankan sebagai fallback debugging.
