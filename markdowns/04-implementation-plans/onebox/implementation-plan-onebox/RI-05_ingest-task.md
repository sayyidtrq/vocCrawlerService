# RI-05 — Job Ingest `VoiceOfCustomerSystemTask` (≤5 MD)

> Keputusan terkait: D1, D2, D4, D5, D8. Pattern rujukan: `app/tasks/SonarTask.php` [verified detail line 422–607]

## 1. Tujuan & Definition of Done
Task CLI yang menarik review dari VoC → dedup → tulis `Ticket` + `Message` + `MessageContent` (+ `Contact`) — dijalankan **manual** (belum scheduled).
**Selesai kalau:** (a) run pertama → N review jadi N Ticket dengan field benar; (b) **run kedua → 0 duplikat**; (c) semua row ber-`SiteId` benar; (d) transaksi rollback saat error di tengah.

## 2. Prasyarat & Dependency
RI-01 (mapping final), RI-04 (client), RI-06 (mapping site/lokasi — bisa paralel, minimal versi config). Branch: sama dengan RI-04.

## 3. File Target
| File | Status |
|---|---|
| `onecloud/app/tasks/VoiceOfCustomerSystemTask.php` | [baru] |
| `onecloud/app/models/{Ticket,Message,MessageContent,MessageUser,Contact}.php` | [baca-saja] |
| `app/tasks/SonarTask.php` | [baca-saja] — contekan utama |
| SQL manual: 1 row `Connection` pilot + master `Media`/`Category` seed (D5/D7) | [baru — dev DB dulu] |

## 4. Langkah Implementasi

### Step 0 — Seed master data dev (D2, D5) — jalankan & catat SQL-nya
1. Insert 1 row `Connection`: `Code='VoiceOfCustomer'`, `SiteId=<pilot>`, `Enabled=1`, `Name='VoC Google Review'`. Kolom lain contoh: lihat row `Code='Sonar'` existing di DB dev (`SELECT * FROM Connection WHERE Code='Sonar' LIMIT 1`). `[assumption→verifikasi]`
2. Insert MediaId "Google Review" ke master media — **temukan dulu tabelnya**: `grep -rn "MediaId" app/controllers/MediamonitoringController.php | head` + cek dropdown `getDropdownMediaOnline()` di ControllerBase untuk tahu sumber master. `[assumption]`

### Step 1 — Kerangka task (contek SonarTask)
```php
<?php
class VoiceOfCustomerSystemTask extends \Phalcon\Cli\Task
{
    public function onConstruct()
    {
        $this->log = \Library\Logger::get('VoiceOfCustomerSystem');
        $this->cfg = $this->config->voiceofcustomer->toArray();   // RI-04
        $this->SiteId = (int)$this->cfg['siteId'];                 // pilot site
        $this->client = new \Library\VoiceOfCustomerSystemClient($this->cfg);
    }

    // php app/boot.php voiceofcustomersystem sync   [assumption — samakan dgn cara invoke task existing]
    public function syncAction($pages = 1)
    {
        $page = 1;
        do {
            $resp = $this->client->getReviews(['page'=>$page, 'page_size'=>50, 'latest_first'=>true]);
            foreach (($resp['items'] ?? []) as $rev) { $this->ingestOne((object)$rev); }
            $page++;
        } while ($page <= min($pages, (int)($resp['total_pages'] ?? 1)));
    }
}
```

### Step 2 — `ingestOne()`: dedup → contact → ticket → message → content
Urutan & konstanta WAJIB meniru SonarTask (line 495–607) — perbedaan ditandai:
```php
private function ingestOne(object $rev): void
{
    // 1. DEDUP (pola SonarTask:422) — D1: RemoteId = review_hash
    $exists = Message::findFirst([
        'conditions' => 'RemoteId = :h: AND SiteId = :s:',
        'bind' => ['h' => $rev->review_hash, 's' => $this->SiteId],
    ]);
    if ($exists) return;                                  // idempotent

    $this->db->begin();
    try {
        // 2. CONTACT find-or-create by reviewer_name (+ profile url)
        //    pola SonarTask pakai $this->contact; kita per-reviewer:
        //    Contact::findFirst(Name+SiteId) ?: new Contact(SiteId, Name, Url=reviewer_profile_url, IsPerson=1)

        // 3. TICKET — samakan semua konstanta SonarTask KECUALI:
        //    Subject     = trim(substr(review_text, 0, 200)) . ' — ' . location
        //    Description = summary            (D4)  — dari analysis; null kalau belum analyzed
        //    Solution    = recommended_action (D4)
        //    Sentiment   = map: positive=>1, neutral=>0, negative=>-1, mixed=>0 (D8)
        //    PriorityId  = map urgency: high=>TP1, medium=>TP2, low/null=>TP2  (D4; kode final dari RI-01 L3)
        //    MediaId     = <MediaId VoC dari Step 0.2>  (D5)
        //    LocationId  = map via RI-06
        //    CategoryId  = map issue_category (RI-07; null dulu kalau RI-07 belum jalan)
        //    ContactId/Requestor/Creator dari contact langkah 2

        // 4. MESSAGE — samakan SonarTask KECUALI:
        //    ObjectName='Review', ConnectionId=<Connection VoC Step 0.1>,
        //    RemoteId=$rev->review_hash, Date/ReceiveDate=review_time (konversi TZ site!),
        //    From=reviewer_name
        //    lalu Ticket->MessageId = Message->Id (save ulang — pola SonarTask:595)

        // 5. MESSAGECONTENT — PENTING [verified]: Id = Message->Id (share PK, SonarTask:603)
        //    Body/BodyText = review_text
        //    Meta (JSON) = rating, sentiment asli+score, keywords, like_count,
        //                  is_potential_viral, is_patient_safety_issue, language,
        //                  reviewer_* ekstra, external_review_id   (D4)

        $this->db->commit();
    } catch (\Throwable $e) {
        $this->db->rollback();
        $this->log->error("ingest gagal {$rev->review_hash}: {$e->getMessage()}");
    }
}
```

### Step 3 — Jalankan manual di DB dev
Run → cek hasil (SQL di §5) → run ulang → cek tidak nambah.

## 5. Cara Verifikasi
```sql
SELECT t.Id, t.SiteId, t.Sentiment, t.PriorityId, t.MediaId, t.Description, m.RemoteId
FROM Ticket t JOIN Message m ON m.Id = t.MessageId
WHERE m.ObjectName='Review' AND t.SiteId=<pilot>;
-- run kedua: COUNT(*) tidak berubah  ← bukti idempotent
SELECT COUNT(*) FROM Message WHERE ObjectName='Review' AND SiteId=<pilot>;
```
Ekstra: matikan VoC di tengah sync → pastikan tidak ada Ticket "setengah jadi" (transaksi bekerja).

## 6. Risiko & Rollback
- **Data leak antar tenant** = risiko #1: setiap findFirst/new WAJIB bawa SiteId (checklist review diri sendiri sebelum commit).
- Timezone `review_time` (+07:00) vs kolom datetime MySQL — konversi eksplisit, jangan andalkan default server.
- Rollback dev: `DELETE` Ticket/Message/MessageContent hasil ingest via `m.ObjectName='Review'` + `RemoteId` (catat query-nya sebelum eksekusi massal).

## 7. Temuan & Deviasi (eksekusi 2026-07-14)

1. **SELESAI dengan bentuk D9 (Provider pattern), bukan task SonarTask-style.** File: `app/services/Provider/VoiceOfCustomerSystemProvider.php` (receive + rowReview + map + ensureMessage + applyAnalysis) + `app/tasks/VoiceOfCustomerSystemTask.php` (CLI manual: `receive`/`analysis`/`health`/`processpending`).
2. **Seed dev DB (sudah dijalankan, SQL di `$CLAUDE_JOB/tmp` — dicatat di sini):**
   - `Reference`: `PVD97 / Provider / VoiceOfCustomerSystem` (pola PVD96 Ciptalife).
   - `Connection` **Id 1039**: SiteId=169, MediaId='GBUSINESS', ProviderId='PVD97', Code='VOC', StatusId='CNS1', Options=`{"mock":true,"mock_file":"/tmp/voc_reviews_sample.json","page_size":50,"max_pages":10}`. Kolom `Url`/`UserId`/`Password` kosong — diisi saat live test (RI-03).
   - MediaId TIDAK bikin baru — reuse `GBUSINESS` (D5 revisi).
3. **Hasil smoke test (mock, 10 review real):**
   - Run 1: 10 Message + MessageContent (Meta lengkap) + Contact per reviewer → 10 Ticket (TT1/TS2/GBUSINESS, `Sentiment`=rating 1–5 otomatis dari Meta.star ✓).
   - `analysis`: 10 ticket ke-update — Description=summary, Solution=recommended_action, PriorityId=TP1(low)/TP2(medium) ✓.
   - Run 2: 10× "already ensured", total tetap 10/10 → **idempotent ✓**.
4. **Ticket dibuat ASYNC** oleh job `process` (broker RabbitMQ) — di dev tanpa worker aktif, message nyangkut `ObjectId=NULL`. Solusi dev: action `processpending <connId>` (proses sinkron). Di env dengan worker jalan, ini tidak perlu.
5. Dedup pipeline = `SiteId+MediaId+RemoteId` (bukan cuma RemoteId+SiteId seperti draft §Step 2) — bawaan `ensureMessage`, tidak perlu kode dedup sendiri.
6. Transaksi & rollback ditangani `ensureMessageAsync` (begin/commit/rollback per message) — tidak perlu transaksi manual di provider.
7. `Ticket.PriorityId` NULL saat dibuat `addTicket` — diisi pass kedua (`applyAnalysis`). `CategoryId` menunggu D7/RI-07 (nilai `issue_category` sudah aman tersimpan di Meta).
8. Cleanup dev (kalau mau reset): `DELETE` Ticket/Message/MessageContent/MessageUser via `Message.ConnectionId=1039` (catat urutan FK; jangan jalankan tanpa perlu).

## 8. API Gap / Handoff ke Codex
Pastikan `review_hash` + field analysis (sentiment, urgency, summary, recommended_action) ikut flat di item response (per sample superprompt §5.2 sudah ada — konfirmasi).

## 9. Estimasi (5 MD)
Hari 1: Step 0 (seed + verifikasi master) . Hari 2: kerangka task + dedup + Contact. Hari 3: Ticket+Message+Content + transform. Hari 4: idempotency & TZ test, perbaikan. Hari 5: buffer + cleanup log + catat temuan.
