# OneBox → VoC: Pindah dari Mock ke Pull Data Asli

> Tujuan: OneBox menarik review sungguhan dari VoC System, ter-scope ke tenant yang benar.

## 1. Kondisi sekarang (terverifikasi langsung ke API, 2026-07-21)

| Jalur | Status | Catatan |
|---|---|---|
| `GET /api/integration/v1/reviews` (service token) | **DIPAKAI** | tenant melekat pada token, keyset cursor |
| `GET /api/reviews` (JWT user) | fallback | scope tenant = `company_id` user yang login |

VOC-CS-03 sudah live dan crawler sudah di-redeploy (`/api/health` → `env: staging`).
Yang tersedia sekarang:

- `GET /api/integration/v1/whoami` → `{company_id, company_name, scopes}`
- `GET /api/integration/v1/reviews` → `{data, page:{limit,has_more,next_cursor,checkpoint_cursor,snapshot_at}, meta}`

**Keputusan:** `api_mode: "service"` jadi mode utama. Mode `"user"` tetap didukung sebagai
fallback, tapi jangan dipakai lagi di luar debugging — mode itu menuntut password user
manusia tersimpan di row `Connection`.

## 2. Risiko utama yang sudah ditutup

VoC menentukan tenant dari **kredensial**, bukan dari parameter yang dikirim OneBox. Artinya
binding tenant hanya sekuat isi row `Connection`: salah paste kredensial = review rumah sakit
lain masuk diam-diam ke SiteId ini, tanpa satu pun error.

`Options.company_id` **wajib** diisi. Sebelum menarik sebaris pun, provider memanggil
`whoami()` dan membandingkan `company_id`-nya. Mismatch → sync dibatalkan (abort, bukan
warning — data lintas-tenant yang sudah jadi Ticket jauh lebih mahal dibersihkan).

Guard ini berlaku di **kedua mode**. Mode service tidak dikecualikan: token yang dipasang di
suatu SiteId bisa saja milik tenant lain, dan hanya server yang tahu — jadi kita tanya.
Di mode service scope `reviews:read` ikut dicek di depan, supaya kekurangan scope tidak baru
ketahuan sebagai 403 di tengah paging setelah sebagian data masuk.

Isolasi sisi VoC juga diuji: `location_id` milik company lain (1, 3, 5, 6) dijawab
`LOCATION_NOT_FOUND` — sama persis dengan lokasi yang memang tidak ada, jadi tidak ada
kebocoran enumerasi.

## 3. Bentuk `Connection.Options` untuk mode live

```json
{
  "api_mode": "service",
  "service_token": "<voc_<env>_<key_id>.<secret> — ambil dari channel privat>",
  "company_id": 3,
  "mock": false,
  "page_size": 100,
  "max_pages": 20,
  "timeout": 30,
  "location_map": { "2": 1705, "4": 1706 }
}
```

| Key | Arti |
|---|---|
| `company_id` | **wajib.** company_id VoC yang seharusnya terpetakan ke SiteId ini |
| `service_token` | token opaque VoC. Rahasia — jangan pernah masuk dokumen/commit |
| `location_map` | location_id VoC → LocationId OneBox |
| `lookback_days` | hanya relevan di mode user (`0` = full pull tiap run). Mode service pakai cursor |

`Connection.Url` = base URL VoC. Di mode service, `UserId`/`Password` **tidak dipakai** dan
sebaiknya dikosongkan.

> Kredensial jangan ditulis di dokumen/commit. Kirim lewat channel privat.

## 4. Urutan menjalankan

```bash
C=$(docker ps -qf name=webapp)

# 1) Konektivitas dulu
docker exec $C php app/bootstrap.php voice_of_customer_system health <connId>

# 2) WAJIB: kredensial ini milik company mana?
docker exec $C php app/bootstrap.php voice_of_customer_system whoami <connId>

# 3) Baru tarik
docker exec $C php app/bootstrap.php voice_of_customer_system receive <connId>
docker exec $C php app/bootstrap.php voice_of_customer_system processpending <connId>
docker exec $C php app/bootstrap.php voice_of_customer_system analysis <connId>
```

Output `whoami` yang diharapkan (mode service):

```
connection : 1039
OneBox site: 169
api_mode   : service
token key  : voc_staging_<key_id>
VoC company: 3 (HGA)
expected   : 3
scopes     : reviews:read
STATUS     : OK — binding cocok
```

`token key` sengaja hanya bagian sebelum titik — secret-nya tidak pernah dicetak maupun
di-log.

Kalau `STATUS` bukan `OK` → **jangan lanjut `receive`**:

| STATUS | Artinya |
|---|---|
| `BELUM AMAN` | `Options.company_id` belum diisi |
| `MISMATCH` | token/kredensial milik company lain daripada yang diharapkan |
| `SCOPE KURANG` | token sah tapi tidak punya `reviews:read` — minta terbitkan ulang |

## 5. Verifikasi hasil (SQL)

```sql
-- harus 0
SELECT COUNT(*) AS bocor
FROM Ticket t
JOIN Message m   ON m.ObjectId = t.Id AND m.ObjectName = 'Ticket'
JOIN Connection c ON c.Id = m.ConnectionId AND c.ProviderId = 'PVD97'
WHERE t.SiteId <> 169;

-- sebaran per lokasi
SELECT l.Description AS lokasi, COUNT(*) AS jumlah, ROUND(AVG(t.Sentiment),2) AS rating
FROM Ticket t
JOIN Message m    ON m.ObjectId = t.Id AND m.ObjectName = 'Ticket'
JOIN Connection c ON c.Id = m.ConnectionId AND c.ProviderId = 'PVD97'
LEFT JOIN Location l ON l.Id = t.LocationId
WHERE t.SiteId = 169
GROUP BY l.Description;
```

## 6. Hasil run pertama — mode user (terverifikasi 2026-07-20)

VoC dijangkau lewat LAN di `http://192.168.1.3:8000` — reachable dari dalam container webapp.
(`10.13.13.90` alamat WireGuard **tidak** reachable dari mesin dev ini; pakai IP LAN saja.)

```
connection 1039 (TargetId=4)  sync done: fetched=25 inserted=15 deduped=10 skipped=0 failed=0
connection 1040 (TargetId=2)  sync done: fetched=50 inserted=45 deduped=5  skipped=0 failed=0
processpending: 15 + 45   applyAnalysis: 15 + 45 ticket updated
```

| Lokasi | Tiket | Rating rata2 | Ada summary | Ada kategori | Prioritas tinggi |
|---|---|---|---|---|---|
| Hermina Depok | 25 | 4.40 | 25 | 25 | 1 |
| HGA Depok | 50 | 3.22 | 48 | 48 | 16 |

- `bocor_ke_site_lain` = **0** — tidak ada tiket PVD97 di luar SiteId 169.
- `deduped` > 0 di run pertama = review yang `review_hash`-nya sudah masuk dari fixture mock.
  Dedup `ensureMessage` bekerja.
- 2 tiket HGA tanpa summary bukan bug: di VoC keduanya masih `analyzed=false`.
  LocationId tetap ter-backfill; summary sengaja dibiarkan null.

### Catatan tenant di data dev

User `test@gmail.com` → `company_id=3 (HGA)`, dan company itu memiliki **dua** lokasi:
`id=2 HGA Depok` dan `id=4 Hermina Depok`. Jadi kedua Connection memang sah memakai
kredensial yang sama. Jangan simpulkan dari nama Connection saja — selalu cek `whoami`
plus daftar lokasi milik company tersebut.

## 7. Pindah ke mode service (VOC-CS-03)

Perilaku contract v1 sudah diverifikasi langsung ke API sebelum Connection diubah:

| Yang diuji | Hasil |
|---|---|
| filter `location_id` bertahan lintas halaman cursor | ya — halaman ke-2/3 (cursor saja) tetap 1 lokasi |
| `checkpoint_cursor` | **hanya** terisi di halaman terakhir (`has_more=false`) |
| jumlah baris | location 4 → 25, location 2 → 50 (identik dengan run mode user) |
| token tanpa/salah | `401 INVALID_SERVICE_TOKEN` |
| lokasi company lain | `LOCATION_NOT_FOUND` (tidak bocor) |

Ini penting karena `saveCursor()` hanya menyimpan checkpoint saat `has_more=false`.
Kalau VoC mengisi checkpoint di tengah siklus, review sisanya akan ter-skip permanen —
perilaku di atas memastikan itu tidak terjadi.

SQL migrasinya (isi token dari channel privat, **jangan** commit nilainya):

```sql
-- backup dulu, supaya rollback ke mode user cuma satu UPDATE
CREATE TABLE IF NOT EXISTS _bak_conn_voc AS
  SELECT Id, Url, UserId, Password, Options FROM Connection WHERE Id IN (1039,1040);

UPDATE Connection
SET Options = JSON_SET(Options,
      '$.api_mode',     'service',
      '$.service_token','<TOKEN>',
      '$.page_size',    100,
      '$.timeout',      30),
    UserId = '', Password = ''      -- mode service tidak memakai keduanya
WHERE Id IN (1039,1040);
```

Karena `review_hash` yang ditarik sama persis dengan yang sudah masuk lewat mode user,
run service pertama **seharusnya** `inserted=0 deduped=75` — itu tanda dedup dan
binding lokasi tetap konsisten lintas mode, bukan tanda sync gagal.
