# Two-Agent Workflow - Review Intelligence x OneBox

Tanggal: 2026-07-12  
Tujuan: mengoptimalkan kerja Claude Code dan Codex untuk integrasi Crawler System ke OneBox tanpa context miss, tanpa ngoding liar, dan tanpa nabrak codebase OneBox yang besar.

---

## 1. Ringkasan Konteks Saat Ini

### VoiceOfCustomer System

VoiceOfCustomer System adalah service VoiceOfCustomer + analysis berbasis FastAPI.

Peran VoiceOfCustomer System:

- crawl / fetch review,
- simpan review dan lokasi,
- jalankan AI analysis,
- expose REST API untuk ditarik OneBox.

Endpoint penting:

```txt
GET  /api/health
POST /api/auth/login
GET  /api/reviews
GET  /api/dashboard/overview
GET  /api/dashboard/critical-issues
GET  /api/dashboard/negative-reviews
GET  /api/openapi.json
```

Endpoint pull utama saat ini:

```txt
GET /api/reviews
```

Auth saat ini:

```txt
JWT Bearer user-based login
```

Auth service-to-service untuk OneBox belum final.

### OneBox / OneCloud

Berdasarkan markdown discovery dan read-only check WSL:

- OneBox code utama ada di:
  ```txt
  /var/www/html/onecloud/onecloud
  ```
- Monorepo/root workspace ada di:
  ```txt
  /var/www/html/onecloud
  ```
- Stack:
  ```txt
  Phalcon 5 + Swoole + Volt + MySQL + Redis + Gearman/RabbitMQ
  ```
- Branch WSL saat dicek:
  ```txt
  hotfix/1.118.1
  ```
- Ada local dirty config dari debugging:
  ```txt
  .env
  .env.local
  onecloud/app/config/development.php
  onecloud/app/config/local.php
  ```

Jangan commit perubahan config/debug tersebut ke feature integration.

---

## 2. Keputusan Arsitektur Yang Sedang Dipakai

Keputusan terbaru dari tasklist:

```txt
Data review VoiceOfCustomer System masuk ke Ticket existing,
lewat / menyerupai modul Mediamonitoring,
UI final berupa dashboard VOC,
pola ingest meniru SonarTask.
```

Jadi arah yang dipakai:

```txt
VoiceOfCustomer API  -> OneBox VoiceOfCustomerSystemClient
  -> VoiceOfCustomerSystemTask / sync task
  -> Ticket + Message + MessageContent existing
  -> Mediamonitoring / VOC dashboard
```

Bukan:

```txt
OneBox menjalankan Selenium sendiri
```

Bukan juga:

```txt
OneBox hanya proxy realtime tanpa persist
```

Kecuali nanti lead mengubah keputusan.

---

## 3. Pembagian Peran Agent

### Agent A - Claude Code

Claude Code berjalan di repo OneBox WSL.

Claude bertugas sebagai:

- OneBox codebase scout,
- OneBox implementation agent,
- pembaca pattern Phalcon/Swoole/Volt,
- pembuat discovery report,
- pembuat skeleton integration di OneBox setelah discovery cukup.

Claude boleh mengubah repo OneBox hanya setelah:

1. branch feature sudah benar,
2. scope task jelas,
3. file target sudah disebut,
4. Codex/user sudah tahu perubahan yang akan dibuat.

Claude jangan mengubah:

- env/config local yang berisi credential,
- branch hotfix/release,
- modul besar tanpa boundary jelas,
- migration sebelum field mapping dan keputusan persist final.

### Agent B - Codex

Codex berjalan di repo VoiceOfCustomer System.

Codex bertugas sebagai:

- source-of-truth VoiceOfCustomer System API,
- penjaga API contract,
- penyusun context handoff untuk Claude,
- reviewer rencana/diff Claude,
- pembuat mapping dan task breakdown,
- implementer perubahan backend VoiceOfCustomer System jika OneBox butuh API tambahan.

Codex boleh read-only ke OneBox WSL untuk memahami konteks, tetapi default ownership code OneBox tetap di Claude.

Codex bertanggung jawab untuk:

- update API docs,
- menambah endpoint/filter bila dibutuhkan, misalnya `updated_since`,
- menyiapkan service auth yang lebih cocok untuk OneBox jika diputuskan,
- memastikan response API stabil untuk integration.

---

## 4. Workflow Komunikasi 2 Agent

Gunakan dokumen sebagai handoff, bukan chat random yang gampang hilang.

### Artifact Utama

Di repo VoiceOfCustomer System:

```txt
markdowns/integrations/CLAUDE_CODE_ONEBOX_INTEGRATION_SUPERPROMPT.md
markdowns/integrations/ONEBOX_ONECLOUD_DEV_GUIDE.md
markdowns/integrations/REVIEW_INTELLIGENCE_TASKLIST.md
markdowns/integrations/TWO_AGENT_ONEBOX_INTEGRATION_WORKFLOW.md
```

Di repo OneBox, Claude sebaiknya membuat:

```txt
docs/VoiceOfCustomer-system-discovery.md
docs/VoiceOfCustomer-system-field-mapping.md
docs/VoiceOfCustomer-system-implementation-plan.md
```

Kalau OneBox tidak punya convention `docs/`, Claude harus pilih lokasi docs yang sesuai setelah discovery.

---

## 5. Phase Plan

### Phase 0 - Stabilkan Workspace

Owner: user + Claude  
Reviewer: Codex

Checklist:

- Pastikan OneBox jalan lokal.
- Jangan lanjut coding sebelum issue MySQL/dev env stabil.
- Pastikan tidak berada di branch `hotfix/1.118.1` untuk feature work.
- Catat dirty config lokal dan jangan commit.

Command read-only yang aman:

```bash
cd /var/www/html/onecloud
git status --short
git branch --show-current
```

Branch baru sebaiknya dari `develop`:

```bash
git checkout develop
git pull origin develop
git checkout -b feature/DNGO19-XXXX_Review-Intelligence-Integration
```

Ganti `DNGO19-XXXX` dengan tiket asli.

### Phase 1 - OneBox Discovery Update

Owner: Claude  
Reviewer: Codex

Claude harus memvalidasi:

- route/controller convention,
- `ControllerBase::getSiteId()`,
- `CiptalifeApi.php` sebagai pattern external REST client,
- `SonarTask.php` sebagai pattern ingest external API ke Ticket,
- `Ticket`, `Message`, `MessageContent`, `MessageUser`,
- Mediamonitoring list/detail/dashboard flow,
- menu / role permission flow.

Output:

```txt
docs/VoiceOfCustomer-system-discovery.md
```

Definition of done:

- Claude bisa menunjuk file target untuk client, task, mapping, UI.
- Claude bisa menjelaskan cara data VoiceOfCustomer System masuk ke `Ticket`.
- Claude bisa menjelaskan cara data tampil di Mediamonitoring/VOC.

### Phase 2 - Field Mapping

Owner: Claude + Codex  
Final decision: user/lead

Mapping awal:

| VoiceOfCustomer System field | OneBox candidate | Catatan |
|---|---|---|
| `location_id` | mapping table / config per `SiteId` | Butuh mapping tenant/location |
| `location` | `Ticket.LocationId` atau metadata | Butuh validasi model `Location` |
| `external_review_id` | `Message.RemoteId` atau dedup metadata | Candidate dedup key |
| `review_hash` | dedup metadata / custom field | Candidate dedup key paling stabil |
| `reviewer_name` | `Contact.Name` + `MessageUser` role author | Ikuti pola SonarTask author |
| `rating` | Ticket extra field / MessageContent / metadata | Perlu keputusan |
| `review_text` | `MessageContent.BodyText` + `Ticket.Subject/Content` | Subject dipotong pendek |
| `review_time` | `Message.Date` / `ReceiveDate` | ISO -> MySQL datetime |
| `sentiment` | `Ticket.Sentiment` | OneBox pakai integer/string perlu validasi |
| `issue_category` | category / tag / metadata | Perlu keputusan |
| `urgency` | priority / metadata | Mungkin map ke `PriorityId` |
| `summary` | `Ticket.Description` atau metadata | Perlu keputusan |
| `recommended_action` | `Ticket.Solution` atau metadata | Cocok ke Solution |
| `owner_response_text` | metadata / MessageContent extension | Optional |

Output:

```txt
docs/VoiceOfCustomer-system-field-mapping.md
```

### Phase 3 - Placeholder Client

Owner: Claude  
Reviewer: Codex

Target:

```txt
onecloud/app/library/VoiceOfCustomerSystemClient.php
```

Pattern:

- mirip `Library\CiptalifeApi`,
- `Logger::get('VoiceOfCustomerSystem')`,
- timeout eksplisit,
- credential dari config per environment,
- token caching minimal di instance/Redis jika mengikuti pattern existing,
- jangan log credential.

Method minimal:

```php
health()
login()
getReviews(array $params = [])
getDashboardOverview()
```

Mode awal:

- mock fixture dulu atau live-dev only,
- jangan langsung production behavior.

### Phase 4 - Manual Sync Task

Owner: Claude  
Reviewer: Codex

Target candidate:

```txt
onecloud/app/tasks/VoiceOfCustomerSystemTask.php
```

Pattern:

- meniru `SonarTask`,
- iterate config/mapping per `SiteId`,
- call VoiceOfCustomer System API,
- dedup by `SiteId + external_review_id` atau `SiteId + review_hash`,
- create `Ticket`,
- create `Message`,
- create `MessageContent`,
- update `Ticket.MessageId`,
- optionally create/find `Contact` for reviewer.

Jangan schedule otomatis dulu.

DoD:

- task bisa dipanggil manual,
- satu sample review menjadi Ticket,
- rerun tidak menghasilkan duplikat.

### Phase 5 - UI / VOC Preview

Owner: Claude  
Reviewer: Codex

Target:

- reuse Mediamonitoring jika memungkinkan,
- jangan bikin UI framework baru,
- Volt + existing layout/classes,
- mulai dari list/filter dulu, dashboard belakangan.

DoD:

- review hasil ingest tampil di UI,
- filter source/channel review tersedia,
- detail review menampilkan rating, sentiment, urgency, summary, recommended action.

---

## 6. Division of Labor Per Hari

### Claude Daily Loop

1. Baca file OneBox yang relevan.
2. Buat catatan discovery.
3. Kalau mau edit, tulis dulu file target + alasan.
4. Implement kecil.
5. Jalankan test/manual verification di OneBox.
6. Kirim diff summary ke user/Codex.

### Codex Daily Loop

1. Update context docs di VoiceOfCustomer System.
2. Review hasil discovery Claude.
3. Validasi API VoiceOfCustomer System terhadap kebutuhan OneBox.
4. Kalau ada API gap, implement di VoiceOfCustomer System.
5. Jaga tasklist dan field mapping tetap sinkron.
6. Bantu bikin report progress ke lead.

---

## 7. Risiko Utama

### Risiko 1 - Tenant Data Leak

OneBox multi-tenant via `SiteId`. Semua query/insert harus scoped.

Rule:

```txt
Tidak ada Ticket/Message review tanpa SiteId.
Tidak ada query VOC tanpa SiteId.
```

### Risiko 2 - Salah Branch

Saat read-only check, repo OneBox berada di:

```txt
hotfix/1.118.1
```

Feature integration jangan dikerjakan di branch ini.

### Risiko 3 - Dirty Config Kecommit

Ada local config dirty akibat setup/dev:

```txt
.env
.env.local
onecloud/app/config/development.php
onecloud/app/config/local.php
```

Jangan stage/commit file ini kecuali memang diminta.

### Risiko 4 - Scope Terlalu Besar

Mediamonitoring controller sangat besar. Jangan refactor.

Mulai dari:

- client,
- task manual,
- mapping,
- view kecil.

### Risiko 5 - VoiceOfCustomer System API Belum Cocok Untuk Sync

Gap yang mungkin perlu dikerjakan di VoiceOfCustomer System:

- `updated_since`,
- cursor pagination,
- service-to-service auth,
- endpoint list analysis terpisah,
- endpoint location mapping.

---

## 8. Prompt Lanjutan Untuk Claude Code

Paste ke Claude setelah superprompt awal:

```txt
Update context:

We now have a more concrete integration direction. Use OneBox existing Ticket and Mediamonitoring patterns instead of creating a totally separate module first.

Relevant OneBox patterns to inspect deeply:
- app/library/CiptalifeApi.php for external REST client style.
- app/tasks/SonarTask.php for external API ingest into Ticket + Message + MessageContent.
- app/models/Ticket.php, Message.php, MessageContent.php, MessageUser.php.
- app/controllers/MediamonitoringController.php and app/views/Mediamonitoring/* for list/detail/dashboard UI.
- app/views/Menu/mediamonitoring.volt and Menu/RoleMenu models for navigation.

Current target architecture:
VoiceOfCustomer System API -> VoiceOfCustomerSystemClient -> VoiceOfCustomerSystemTask manual sync -> Ticket/Message/MessageContent -> Mediamonitoring/VOC UI.

Important constraints:
- Always scope by SiteId.
- Do not work on hotfix/release branch. Create feature branch from develop after user approval.
- Do not commit dirty local config: .env, .env.local, app/config/development.php, app/config/local.php.
- Do not create migrations until field mapping is reviewed.
- Do not schedule jobs automatically until manual sync is proven.

Your next deliverable is not full code. First produce:
1. a file-target implementation plan,
2. a field mapping draft,
3. exact smallest placeholder implementation for VoiceOfCustomerSystemClient and a manual test path.
```

---

## 9. Current Recommended Next Step

Jangan mulai dari UI.

Mulai dari:

```txt
RI-01 Field mapping review VoiceOfCustomer System -> Ticket/Message
RI-03 Verify VoiceOfCustomer System API live from OneBox WSL
RI-04 VoiceOfCustomerSystemClient placeholder/live health + login + getReviews
```

Setelah itu baru:

```txt
RI-05 VoiceOfCustomerSystemTask manual ingest
```

