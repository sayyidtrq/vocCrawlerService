# RI-11 — UI Detail Review (≤4 MD)

> Pattern: `app/views/Mediamonitoring/detail.volt` + action detail-nya [verified file ada]

## 1. Tujuan & DoD
Klik item di list (RI-10) → detail lengkap: reviewer, rating bintang, sentiment, urgency, issue category, summary, recommended action, teks penuh, link Google, waktu, lokasi, owner response (kalau ada). **Selesai kalau:** semua field mapping RI-01 yang ditampilkan sesuai nilai DB; tidak bisa akses detail milik site lain (IDOR check).

## 2. Prasyarat
RI-10.

## 3. File Target
| File | Status |
|---|---|
| `MediamonitoringController.php` → action `detailReviewAction($ticketId)` | [ubah — tambah action] |
| `app/views/Mediamonitoring/detailReview.volt` | [baru] |
| `app/views/Mediamonitoring/detail.volt` | [baca-saja] contekan |

## 4. Langkah
1. Pelajari action detail existing: cara ambil Ticket+Message+MessageContent join, cara render (modal? tab? full page?) — ikuti medium yang sama.
2. `detailReviewAction`: `Ticket::findFirst(['conditions'=>'Id=:id: AND SiteId=:site:', ...])` — **SiteId wajib di kondisi** (ini pagar IDOR). Join Message (RemoteId, From, Date) + MessageContent (Body, Meta decode).
3. View: layout dua kolom ala benchmark FE — kiri: teks review + owner response; kanan: panel analisa (sentiment, urgency, kategori, summary, recommended action) + reviewer info + link eksternal (`target="_blank" rel="noopener"`).
4. Field analisa dari Meta di-decode sekali di controller, dilempar sebagai array ke view (jangan decode di Volt).

## 5. Verifikasi
Buka detail milik site sendiri → lengkap; ganti Id di URL ke ticket site lain → ditolak/404; teks review dengan karakter aneh (emoji, `<script>`) tampil aman.

## 6. Risiko
IDOR (tertangani langkah 2); Meta null untuk review belum dianalisa → view harus toleran (tampilkan "belum dianalisa").

## 9. Estimasi (4 MD)
Hari 1: baca pattern detail. Hari 2: action + query. Hari 3: view. Hari 4: IDOR + edge case + polish kecil.
