# RI-12 — Dashboard VOC (≤5 MD)

> Pattern: `dashboardSentimen.volt`, `dashboard_content.volt`, `dataChartAction($type='sentiment')` di MediamonitoringController [verified ada], query agregat sentiment [verified line ±2086: `COUNT(DISTINCT CASE t.Sentiment WHEN -1/1/0 ...)`]

## 1. Tujuan & DoD
Dashboard VOC: kartu Negatif/Netral/Positif/Total (pola persis dashboard Berita), breakdown urgency (PriorityId), breakdown issue category (CategoryId), trend per waktu, daftar review kritis (urgency high / patient-safety). **Selesai kalau:** angka dashboard == hasil SQL manual; filter periode jalan; scoped site.

## 2. Prasyarat
RI-05 + RI-07 (CategoryId terisi). RI-10 (navigasi).

## 3. File Target
| File | Status |
|---|---|
| `MediamonitoringController.php` → `dashboardVocAction` + `dataChartVocAction` | [ubah — tambah action] |
| `app/views/Mediamonitoring/dashboardVoc.volt` | [baru] |
| `dashboardSentimen.volt` / `dashboard_content.volt` | [baca-saja] contekan |

## 4. Langkah
1. **Pelajari `dataChartAction`** (line ±2597) — sumber data kartu & chart existing; catat format response yang dikonsumsi JS-nya.
2. **Query VOC** = query sentiment existing + `AND m.ObjectName='Review'` (atau MediaId VoC):
   ```sql
   SELECT COUNT(DISTINCT CASE t.Sentiment WHEN -1 THEN t.Id END) AS Negative,
          COUNT(DISTINCT CASE t.Sentiment WHEN  1 THEN t.Id END) AS Positive,
          COUNT(DISTINCT CASE t.Sentiment WHEN  0 THEN t.Id END) AS Neutral,
          COUNT(DISTINCT t.Id) AS Total
   FROM Ticket t JOIN Message m ON m.Id = t.MessageId
   WHERE t.SiteId = :site AND m.ObjectName = 'Review' AND t.CreateDate BETWEEN :from AND :to;
   ```
   Variasi: `GROUP BY t.PriorityId` (urgency), `GROUP BY t.CategoryId` (issue), `GROUP BY DATE(t.CreateDate)` (trend).
3. **View:** susun dari komponen dashboard existing (kartu warna, chart) — chart pakai lib JS yang SUDAH dipakai dashboardSentimen (cek `<script>`-nya; jangan import lib baru). Benchmark visual: FE Next.js Hermina (`hermina-crawler-fe`) untuk komposisi panel — tapi komponen tetap punya Onebox.
4. **Panel "Review Kritis":** list top-N `PriorityId='TP1'` atau Meta `is_patient_safety_issue=true` → link ke detail RI-11. (Query Meta JSON boleh LIKE sederhana untuk MVP; catat sebagai kandidat kolom kalau lambat.)
5. Filter periode: ikuti pola filter existing dashboard (`date_preset` ala "Hari Ini" di UI staging).

## 5. Verifikasi
Cocokkan tiap angka kartu dengan SQL manual di DBeaver (data sama, WHERE sama); ganti site → angka berubah/kosong; periode kosong → nol semua, tanpa error.

## 6. Risiko
Query Meta (patient-safety) bisa lambat di data besar — MVP oke, tandai untuk optimasi; jangan bangun index dadakan tanpa diskusi. Chart lib versi lama — ikuti apa adanya.

## 9. Estimasi (5 MD)
Hari 1: baca pattern dashboard+chart. Hari 2: query + action. Hari 3–4: view + chart + panel kritis. Hari 5: pencocokan angka + filter periode.
