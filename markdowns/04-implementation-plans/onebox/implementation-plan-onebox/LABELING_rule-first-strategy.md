# Strategi Labeling: Rule-First, AI-Secondary (spec D11)

> Masalah yang dipecahkan: **klasifikasi pakai AI = boros token**. OneBox sudah punya rule engine untuk labeling — dokumen ini memetakan cara pakainya.
> Semua temuan di bawah **[verified]** dari kode, bukan asumsi.

---

## 1. Yang Sudah Ada di OneBox (hasil investigasi)

### 1a. Rule engine: `app/services/Ruling.php`
Engine aturan **per-site** yang jalan otomatis saat Ticket dibuat.

| Komponen | Isi |
|---|---|
| **Model** | `Rule` — kolom: `Name`, `Conditions` (JSON), `Actions` (JSON), `Enabled`, `Priority` (urutan), `Terminal` (stop kalau match), `RuleType` (`RLS1`), `SiteId` |
| **Entry point** | `$this->di->get('ruling')->apply($ticket, $message)` |
| **Dipanggil di** | `app/services/Ticketing.php:263` (otomatis saat `addTicket`) + `TicketController.php:1887` |

### 1b. Kondisi yang didukung (`evaluateConditions`)
```
field  : "Body" (isi pesan) | "Channel" (ConnectionId) | "Category" (Ticket.CategoryId)
         | nama kolom Message lain (mis. "Subject")
type   : "Contain" | "Equals" | "Not Contain"     ← semua pakai stripos (case-insensitive)
gabung : typecondition = "And" | "Or"
```
Bentuk JSON `Rule.Conditions`:
```json
{ "typecondition": "Or",
  "itemlist": [
    { "field": "Body", "type": "Contain", "text": "antri" },
    { "field": "Body", "type": "Contain", "text": "lama menunggu" }
  ] }
```

### 1c. Aksi yang didukung (`executeActions`) — ini kuncinya
```php
$ticket->{$action->field} = $action->text;   // BISA SET KOLOM TICKET APA PUN
```
Artinya rules bisa mengisi: `CategoryId` (kategori isu), `PriorityId` (urgensi), `StatusId`, `RegionId`, dll.
Plus aksi khusus: `AgentId` → tambah assignee · `OrganizationId` → tambah grup · `StatusId=TS7` → set `CloseDate`.

Bentuk JSON `Rule.Actions`:
```json
[ { "field": "CategoryId", "text": "CAT_WAKTU_TUNGGU" },
  { "field": "PriorityId", "text": "TP3" } ]
```

### 1d. Aset labeling lain yang tersedia
| Model | Guna |
|---|---|
| `Keyword` | daftar kata kunci per-site (`Code`, `Value`, `Enabled`, `IsActor`) — dipakai dropdown Mediamonitoring |
| `Tag` + `TagObject` | tagging polimorfik (`ObjectName`+`ObjectId`+`TagId`) — bisa nempel ke Ticket |
| `Service\TextService`, `Service\EntityService` | utilitas teks/entity |

---

## 2. Keputusan (D11): Rule-First, AI-Secondary

| Jenis label | Cara | Alasan |
|---|---|---|
| `issue_category` | **Rules** (`CategoryId`) | set kategori kecil & stabil (antri, dokter, fasilitas, biaya…) — deterministik |
| `urgency`/prioritas | **Rules** (`PriorityId`) | bisa diturunkan dari rating + kata kunci |
| Routing / assign tim | **Rules** (`AgentId`/`OrganizationId`) | tak perlu AI sama sekali |
| Flag patient-safety | **Rules** (kata kunci kritis) | harus deterministik & bisa diaudit — jangan gantung ke AI |
| `summary` | **AI (VoC)** | butuh generasi bahasa |
| `recommended_action` | **AI (VoC)** | butuh reasoning |
| Nuansa sentiment | **AI (VoC)** | rules lemah untuk sarkasme/campuran |

**Efek biaya:** review yang tertangkap rules **tidak perlu dikirim ke AI sama sekali** untuk kategorisasi. Sisakan token hanya untuk summary/rekomendasi — dan itu pun bisa dibatasi (lihat §4).

**Bonus:** kalau **D9 (Provider pattern) di-ACC**, labeling rules jalan **tanpa nulis kode apa pun** — `Ticketing::addTicket` sudah memanggil `ruling->apply()` otomatis.

---

## 3. Langkah Implementasi

### Step 1 — Kumpulkan taksonomi kategori (0.5 hari)
Ambil nilai `issue_category` nyata dari VoC:
```sql
SELECT issue_category, COUNT(*) FROM review_analysis GROUP BY issue_category ORDER BY 2 DESC;
```
Hasilnya jadi daftar kategori final (target: ≤10 kategori).

### Step 2 — Seed master `Category` per site (0.5 hari)
Insert kategori hasil Step 1 ke master Category OneBox untuk `SiteId` pilot. Catat `CategoryId` tiap kategori.
⚠️ Verifikasi dulu nama tabel/model Category & cara Mediamonitoring memakainya (RI-07 Step 1).

### Step 3 — Susun kamus kata kunci per kategori (1 hari)
Untuk tiap kategori, kumpulkan 5–15 kata kunci dari data review nyata (75 review lokal lu).
Contoh:
```
waktu_tunggu   → antri, antrian, menunggu, lama sekali, lelet
layanan_dokter → dokter, ramah, judes, tidak dijelaskan
fasilitas      → toilet, kotor, ac, parkir, kamar
biaya          → mahal, biaya, tagihan, bpjs
```
**Sumber terbaik: review yang sudah dianalisa AI** — pakai hasil AI untuk *menemukan* pola, lalu bekukan jadi rules. (Ini teknik standar: AI untuk bootstrap, rules untuk produksi.)

### Step 4 — Bikin row `Rule` per kategori (1 hari)
Satu Rule per kategori. Isi `Conditions`/`Actions` sesuai format §1b/§1c, set `SiteId` pilot, `RuleType='RLS1'`, `Enabled=1`, dan `Priority` (rule paling spesifik nomor kecil).
⚠️ Cek dulu apakah ada UI pengelola Rule di OneBox (kemungkinan ada di menu Pengaturan) — kalau ada, **pakai UI-nya**, jangan insert SQL mentah.

### Step 5 — Uji & ukur akurasi (0.5 hari)
Ambil 30 review yang sudah dilabeli AI sebagai ground truth. Jalankan ingest → bandingkan `CategoryId` hasil rules vs label AI.
Target realistis: **70–85% cocok**. Sisanya perbaiki kata kunci, bukan tambah AI.

### Step 6 — Sisakan AI hanya untuk yang perlu (0.5 hari)
Di sisi VoC, pakai flag `ai_analysis_enabled` (D10) + kebijakan:
- Analisa AI **hanya** untuk review yang: rating ≤ 3, ATAU tidak match rule mana pun, ATAU teks > N karakter.
- Review positif pendek ("bagus", "mantap") → skip AI total. Ini biasanya porsi besar dan nol nilai analitis.

**Total: ±4 MD.**

---

## 4. Kenapa Ini Praktik yang Benar (bukan sekadar hemat)

1. **Deterministik & auditable** — kalau manajemen tanya "kenapa review ini masuk kategori X", rules bisa dijawab; AI tidak.
2. **Instan & gratis** — tanpa latensi panggilan API, tanpa biaya per-review.
3. **Bisa diubah non-engineer** — rules ada di DB; nanti tim ops bisa atur sendiri lewat UI.
4. **Tidak berhalusinasi** — kategori tak akan tiba-tiba muncul di luar daftar.
5. **AI tetap dipakai di tempat yang tepat** — generasi bahasa (summary/rekomendasi), bukan klasifikasi ke set tertutup.

**Rule of thumb industri:** kalau outputnya **set tertutup & kecil** (kategori, prioritas, routing) → rules/klasifikasi klasik. Kalau outputnya **teks bebas** (ringkasan, saran) → LLM.

---

## 5. Risiko & Batasan

| Risiko | Mitigasi |
|---|---|
| Kata kunci meleset (sarkasme, typo, singkatan) | Terima 70–85%; sisanya fallback ke AI atau label manual |
| `Contain` = substring polos → false positive (mis. "antri" match "antrian" ✓ tapi juga bisa kena kata lain) | Pilih kata kunci yang cukup panjang & spesifik; uji di Step 5 |
| Kategori baru muncul seiring waktu | Review kamus kata kunci berkala (bulanan) |
| Rules bertabrakan | Pakai `Priority` + `Terminal` di model `Rule` |

---

## 6. Ketergantungan
- **Butuh D9 (Provider pattern) di-ACC** supaya rules jalan otomatis. Kalau D9 ditolak dan balik ke task manual, harus panggil `ruling->apply($ticket, $message)` manual sebelum simpan Ticket.
- **Butuh D7** (issue_category → CategoryId) tetap berlaku.
- Terkait: [RI-02](RI-02_keputusan-arsitektur.md) D7/D9/D10/D11, [RI-07](RI-07_analysis-fields.md).
