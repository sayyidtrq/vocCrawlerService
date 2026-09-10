# RI-10 — UI List: Sumber "Review/VOC" di Mediamonitoring (≤4 MD)

> Keputusan terkait: D5 (MediaId). Pattern: `MediamonitoringController::listNewsAction` + `app/views/Mediamonitoring/listNews.volt` [verified ada]

## 1. Tujuan & DoD
Ticket review tampil sebagai list di modul Mediamonitoring, terfilter dari berita biasa. **Selesai kalau:** buka halaman → hanya review yang muncul (filter `MediaId` VoC / `ObjectName='Review'`), kolom menampilkan lokasi, rating, sentiment, waktu; pagination jalan; site lain tidak melihatnya.

## 2. Prasyarat
RI-05 (ada data). Branch sama.

## 3. File Target
| File | Status |
|---|---|
| `app/controllers/MediamonitoringController.php` | [ubah MINIMAL — hanya tambah action baru; JANGAN refactor, file 3000+ baris] |
| `app/views/Mediamonitoring/listReview.volt` | [baru] |
| `app/views/Mediamonitoring/listNews.volt` | [baca-saja] — contekan struktur |

## 4. Langkah
1. **Pelajari `listNewsAction`** (line ±68) end-to-end: parameter filter, query builder, cara render (partial via `getRender`?), DataTable/AJAX pattern — 0.5 hari baca murni. Catat: filter `searchtone` (sentiment), struktur `$params`.
2. **Action baru `listReviewAction`** — duplikasi terarah dari `listNewsAction` dengan tambahan `AND m.ObjectName='Review'` (atau `t.MediaId=<VoC>`) di WHERE — **jangan** mengubah query listNews existing. Semua kondisi tetap bawa `SiteId` [pola: `$this->getSiteId()`].
3. **View `listReview.volt`** — copy struktur listNews.volt, kolom disesuaikan: waktu, lokasi (LocationId→nama), rating (dari `MessageContent.Meta`), sentiment badge, potongan teks, tombol detail. Pakai kelas CSS yang sudah dipakai listNews (jangan bawa gaya baru).
4. **Rating dari Meta:** decode JSON Meta di query/PHP — kalau ternyata berat, tunda kolom rating ke RI-13 dan catat (kandidat argumen untuk kolom khusus ke lead).
5. Akses via `/Mediamonitoring/listReview` (routing otomatis by convention [verified]).

## 5. Verifikasi
Login staging-style role (Pimpinan/Kontributor) di dev: list muncul benar; user site lain → kosong; berita news biasa tidak tercampur; XSS check: review_text ter-escape di Volt (`{{ }}` auto-escape — pastikan tidak pakai `{{ ...|raw }}` untuk teks review... wajib, teks publik dari internet!).

## 6. Risiko
Mediamonitoring controller raksasa — disiplin "tambah, jangan ubah". Konflik asset/JS antar-tab modul — ikuti pola `IdTabNumber` kalau dipakai. **Keamanan:** review = konten publik tak terpercaya → escape semua output.

## 9. Estimasi (4 MD)
Hari 1: baca pattern. Hari 2: action + query. Hari 3: view + rating Meta. Hari 4: verifikasi role/tenant + rapikan.
