# Onebox / OneCloud — Developer Guide & Hermina Integration Analysis

Tanggal: 2026-07-09
Ditulis berdasarkan eksplorasi langsung codebase di `\\wsl.localhost\Ubuntu22.04-Swoole\var\www\html\onecloud`
Status: hasil verifikasi codebase ditandai ✅, asumsi/perlu konfirmasi ditandai ⚠️

---

## Bagian 1 — Intro to Onebox

### 1.1 Apa itu Onebox (dari kacamata codebase)

Onebox (internal name: **OneCloud**) adalah platform **omnichannel customer engagement** multi-tenant. Bukti dari codebase: ada modul Ticket/Case, Agent, Helpdesk, Campaign, Broadcast, Communicator, dan integrasi channel yang sangat banyak (`Waba.php`, `Telegram.php`, `Facebook.php`, `Instagram.php`, `Tokopedia.php`, `Shopee.php`, `Bukalapak.php`, `Line.php`, `Twitter.php`, `Youtube.php`, dst di `app/library/`). Multi-tenancy di-handle lewat konsep **`siteId`** — hampir semua query dan controller di-scope per site/tenant (lihat `$this->getSiteId()` di `ControllerBase`).

Satu deployment bisa melayani banyak instance/klien — lihat folder `services/` di luar repo: `onebox.sh`, `batam.sh`, `dinkes.sh`, `dispenau.sh`, `psn.sh`, dll. Masing-masing punya config production sendiri di `app/config/production-*.php`.

### 1.2 Stack ✅

| Komponen | Teknologi |
|---|---|
| Framework | **Phalcon 5.9.3** (bukan Laravel!) — MVC framework berbasis C-extension |
| PHP | 8.4.11 |
| Runtime | **Swoole** via custom server `app/swoole-server.php` (bukan Octane); fallback klasik `public/index.php` |
| Template | **Volt** (template engine Phalcon, sintaks mirip Twig/Jinja) |
| Database | MySQL (Percona/Vitess/NDB tersedia di deploy scripts) |
| Cache/Session | Redis Cluster (`RedisClusterCache.php`, `RedisClusterSession.php`) |
| Queue/Worker | **Gearman** (`Gearman.php`, `GearmanBroker.php`, folder `Gearman/`) + RabbitMQ (`Rabbitmq.php`) |
| Background job | Phalcon CLI Tasks di `app/tasks/` (bootstrap: `app/boot.php`), scheduler via `scheduler.sh` / `docker-compose.scheduler.yml` |
| Logging | Monolog 3.9 via `Library\Logger` |
| CI/CD | Jenkins (banyak `Jenkinsfile.*` di root monorepo) |
| AI (sudah ada!) | `OpenAi.php`, `OpenAiAssistant.php`, `Chatgpt.php`, `Dialogflow.php` |

### 1.3 Peta repo — PENTING ✅

Path yang lu buka di WSL itu **monorepo/workspace**, bukan aplikasi:

```
/var/www/html/onecloud/              ← monorepo: deploy scripts, Jenkinsfiles, docker-compose, kube/
├── onecloud/                        ← ★ APLIKASI PHP UTAMA (di sinilah lu ngoding)
│   ├── app/
│   │   ├── controllers/             ← Controllers (flat + subfolder per namespace)
│   │   │   ├── ControllerBase.php   ← base class semua controller
│   │   │   ├── api/                 ← namespace Api\   
│   │   │   ├── report/              ← namespace Reports\
│   │   │   ├── dashboard/           ← namespace Dashboards\
│   │   │   └── helpdesk/            ← namespace helpdesk\
│   │   ├── models/                  ← Models (extend ModelBase)
│   │   ├── views/                   ← Volt templates, folder per controller (PascalCase)
│   │   │   └── layouts/             ← layout templates (apm.volt, header_default.volt, dll)
│   │   ├── library/                 ← ★ semua business logic & API client (namespace Library\)
│   │   ├── tasks/                   ← CLI tasks / background jobs (XxxTask.php)
│   │   ├── config/
│   │   │   ├── routes.php           ← router definition
│   │   │   ├── config.php           ← config utama
│   │   │   ├── services.php         ← DI container
│   │   │   ├── loader.php           ← autoloader
│   │   │   └── development.php, staging.php, production-*.php  ← config per environment
│   │   ├── swoole-server.php        ← entrypoint Swoole (production)
│   │   └── boot.php                 ← entrypoint CLI/tasks
│   ├── public/                      ← webroot, index.php (non-Swoole), assets css/js/img
│   ├── migrations/                  ← phalcon/migrations
│   └── tests/, features/            ← PHPUnit + Behat
├── onecloud-next/                   ← frontend Node/lerna terpisah (abaikan untuk kerja PHP)
├── services/                        ← deploy scripts per instance/klien
└── manage_menu.sql                  ← seed/manajemen menu sidebar (DB-driven)
```

---

## Bagian 2 — How to Code in OneCloud (MVC + Route)

### 2.1 Routing ✅

File: `app/config/routes.php`, pakai wrapper `Library\PhalconRouter`.

Pola dasarnya **convention-based**: `/{Controller}/{action}/{params}` otomatis ke `{Controller}Controller::{action}Action()`. Ada route group ber-namespace:

```php
// contoh nyata dari routes.php:
$router->add('/report/:controller/:action/:params', [
    'namespace'  => 'Reports',
    'controller' => 1,
    'action'     => 2,
    'params'     => 3,
]);

$router->add('/dashboard/:controller/:action/:params', [
    'namespace'  => 'Dashboards',
    ...
]);

$router->add('/api/:controller/:action/:params', [
    'namespace'  => 'Api',
    'version'    => 'v1',
    ...
]);
```

**Implikasi buat lu:** bikin `FooController` dengan `barAction()` → langsung bisa diakses di `/Foo/bar` tanpa nyentuh routes.php. Routes.php cuma perlu diubah kalau butuh prefix/namespace baru.

### 2.2 Controller ✅

- Lokasi: `app/controllers/NamaController.php`
- Wajib extend `ControllerBase` (yang extend `Phalcon\Mvc\Controller`)
- Method publik berakhiran `Action` = endpoint
- Helper penting dari base: `$this->getSiteId()` (tenant scoping — **selalu pakai ini**), `$this->view` (pass data ke view), `$this->request` (input), `$this->response`
- View otomatis resolve ke `app/views/{NamaController tanpa suffix}/{action}.volt`

### 2.3 Model ✅

- Lokasi: `app/models/NamaTabel.php`, extend `\ModelBase` (yang extend `Phalcon\Mvc\Model`)
- Dipakai tanpa namespace (contoh: `Product::find()`, `Ticket::findFirst()`)
- ORM Phalcon: `find()`, `findFirst()`, `save()`, `create()`, `update()`, `delete()`
- Contoh referensi: `app/models/Product.php`

### 2.4 View (Volt) ✅

- Lokasi: `app/views/{ControllerName}/{action}.volt` — **nama folder = nama controller PascalCase**
- Sintaks Volt: `{{ variable }}`, `{% if %}`, `{% for %}`, `{{ url('Controller/action') }}`
- Layout global: `app/views/index.volt` (root layout) + `app/views/layouts/` (apm.volt, header_default.volt, style-css.volt, dll)
- Render partial untuk AJAX: `$this->view->getRender('Folder', 'file', $data)` — pattern ini dipakai `ProductController::listProductAction()`

### 2.5 Menu / Sidebar ✅ (mekanisme) ⚠️ (detail kolom)

Menu sidebar **DB-driven**, bukan hardcode di template:
- Model: `app/models/Menu.php` + `app/models/RoleMenu.php` (menu di-assign per role)
- Seed/contoh SQL: `manage_menu.sql` di root monorepo
- Artinya page baru lu baru muncul di sidebar setelah insert row menu + mapping role. Cek struktur kolomnya di `Menu.php` dan contoh insert di `manage_menu.sql` sebelum eksekusi.

### 2.6 Library / Service Class ✅

Semua logic non-trivial dan **semua external API client** hidup di `app/library/` dengan namespace `Library\`. Contoh terbaik untuk dicontek: `CiptalifeApi.php` — external REST client dengan konstruktor credential, `login()` + token caching, timeout setter, dan Monolog logging.

### 2.7 Background Job / Scheduler ✅

- Task CLI: `app/tasks/NamaTask.php` extend `BaseTask`, dijalankan via `app/boot.php`
- Sudah ada preseden persis untuk use-case lu: `CrawlerTask.php`, `GbusinessTask.php`, `GoogleTask.php`
- Distribusi kerja berat: Gearman workers (`worker.sh`, `docker-compose.worker.yml`)

---

## Bagian 3 — End-to-End: Bikin Fitur "Review Monitor" (Mock Feature)

Contoh medium-level: page yang nampilin daftar review dari tabel lokal, dengan filter sentiment + detail via AJAX. Sengaja dibuat setema dengan tujuan akhir lu (Review Intelligence) supaya scaffold ini bisa dievolusi jadi fitur beneran.

> ⚠️ Sebelum mulai: bikin feature branch dulu (lihat Bagian 5). Jangan ngoding di `hotfix/1.118.1` (branch yang lagi aktif sekarang).

### Step 1 — Tabel + Model

SQL (jalankan di DB dev; atau lebih benar: bikin migration via `phalcon/migrations`, lihat folder `migrations/`):

```sql
CREATE TABLE review_monitor (
    id INT AUTO_INCREMENT PRIMARY KEY,
    site_id INT NOT NULL,                -- WAJIB: tenant scoping Onebox
    location_name VARCHAR(255),
    reviewer_name VARCHAR(255),
    rating TINYINT,
    review_text TEXT,
    sentiment VARCHAR(20),               -- positive|neutral|negative|mixed
    urgency VARCHAR(20),
    summary TEXT,
    review_time DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_site_sentiment (site_id, sentiment)
);
```

`app/models/ReviewMonitor.php`:

```php
<?php

class ReviewMonitor extends \ModelBase
{
    public $id;
    public $site_id;
    public $location_name;
    public $reviewer_name;
    public $rating;
    public $review_text;
    public $sentiment;
    public $urgency;
    public $summary;
    public $review_time;
    public $created_at;

    public function initialize()
    {
        $this->setSource('review_monitor');
    }
}
```

### Step 2 — Controller

`app/controllers/ReviewMonitorController.php`:

```php
<?php

class ReviewMonitorController extends ControllerBase
{
    // GET /ReviewMonitor  → render page utama
    public function indexAction()
    {
        $this->view->pageTitle = 'Review Monitor';
        // view otomatis: app/views/ReviewMonitor/index.volt
    }

    // GET/POST /ReviewMonitor/listReview → dipanggil AJAX, render partial
    public function listReviewAction()
    {
        $siteId    = $this->getSiteId();
        $sentiment = $this->request->get('sentiment', 'string', '');

        $conditions = 'site_id = :siteId:';
        $bind       = ['siteId' => $siteId];

        if ($sentiment !== '') {
            $conditions        .= ' AND sentiment = :sentiment:';
            $bind['sentiment']  = $sentiment;
        }

        $reviews = ReviewMonitor::find([
            'conditions' => $conditions,
            'bind'       => $bind,
            'order'      => 'review_time DESC',
            'limit'      => 50,
        ]);

        // render partial view (pattern sama seperti ProductController::listProductAction)
        $this->view->getRender('ReviewMonitor', 'listReview', ['reviews' => $reviews]);
    }

    // GET /ReviewMonitor/detail/{id} → JSON untuk modal detail
    public function detailAction($id = 0)
    {
        $this->view->disable();

        $review = ReviewMonitor::findFirst([
            'conditions' => 'id = :id: AND site_id = :siteId:',   // scoping wajib!
            'bind'       => ['id' => (int)$id, 'siteId' => $this->getSiteId()],
        ]);

        $this->response->setContentType('application/json');
        $this->response->setJsonContent(
            $review ? ['status' => 200, 'data' => $review->toArray()]
                    : ['status' => 404, 'message' => 'Review tidak ditemukan']
        );
        return $this->response;
    }
}
```

### Step 3 — Views

`app/views/ReviewMonitor/index.volt`:

```volt
<div class="page-header">
    <h3>{{ pageTitle }}</h3>
</div>

<div class="filter-bar">
    <select id="filterSentiment" class="form-control" style="width:200px">
        <option value="">Semua Sentiment</option>
        <option value="positive">Positive</option>
        <option value="neutral">Neutral</option>
        <option value="negative">Negative</option>
        <option value="mixed">Mixed</option>
    </select>
</div>

<div id="reviewListContainer">
    {# diisi via AJAX #}
</div>

<script>
function loadReviews() {
    $.get('{{ url("ReviewMonitor/listReview") }}',
        { sentiment: $('#filterSentiment').val() },
        function (html) { $('#reviewListContainer').html(html); }
    );
}
$('#filterSentiment').on('change', loadReviews);
$(function () { loadReviews(); });

function showDetail(id) {
    $.getJSON('{{ url("ReviewMonitor/detail") }}/' + id, function (res) {
        if (res.status === 200) {
            alert(res.data.summary || res.data.review_text); // ganti dengan modal template Onebox
        }
    });
}
</script>
```

`app/views/ReviewMonitor/listReview.volt` (partial):

```volt
<table class="table table-striped">
    <thead>
        <tr>
            <th>Waktu</th><th>Lokasi</th><th>Reviewer</th>
            <th>Rating</th><th>Sentiment</th><th>Review</th><th></th>
        </tr>
    </thead>
    <tbody>
    {% for r in reviews %}
        <tr>
            <td>{{ r.review_time }}</td>
            <td>{{ r.location_name }}</td>
            <td>{{ r.reviewer_name }}</td>
            <td>{{ r.rating }} ★</td>
            <td><span class="label label-{{ r.sentiment == 'negative' ? 'danger' : (r.sentiment == 'positive' ? 'success' : 'default') }}">{{ r.sentiment }}</span></td>
            <td>{{ r.review_text|slice(0, 80) }}...</td>
            <td><button class="btn btn-xs btn-info" onclick="showDetail({{ r.id }})">Detail</button></td>
        </tr>
    {% else %}
        <tr><td colspan="7">Belum ada data review.</td></tr>
    {% endfor %}
    </tbody>
</table>
```

> ⚠️ Class CSS di atas (`table-striped`, `label-danger`, dll) asumsi Bootstrap-style. Cek dulu view existing (mis. `app/views/Product/index.volt` atau `app/views/Dashboard/`) dan `app/views/layouts/style-css.volt` untuk tau kelas & komponen template yang benar-benar dipakai, lalu samakan.

### Step 4 — Route

**Tidak perlu.** `/ReviewMonitor`, `/ReviewMonitor/listReview`, `/ReviewMonitor/detail/5` otomatis ke-map oleh convention router. Kalau nanti mau URL cantik (mis. `/review-intelligence`), baru tambah rule eksplisit di `app/config/routes.php`.

### Step 5 — Daftarin ke Menu Sidebar

Baca `app/models/Menu.php` untuk struktur kolom + contoh row di `manage_menu.sql`, lalu insert menu baru + mapping ke role lu via `RoleMenu`. (Detail kolom sengaja tidak gua tulis karena harus diverifikasi dari file itu — jangan nebak schema.)

### Step 6 — Test

```bash
# di dalam WSL
cd /var/www/html/onecloud/onecloud
./swoole-dev.sh        # atau cara run dev yang dipakai tim (tanya lead kalau beda)
# buka http://localhost/ReviewMonitor
```

Seed 2–3 row manual ke tabel `review_monitor` (dengan `site_id` sesuai site dev lu) biar list-nya keisi.

---

## Bagian 4 — Best Practices di Codebase Ini

1. **Selalu scope pakai `site_id`.** Ini aplikasi multi-tenant. Query tanpa `site_id` = data leak antar klien. Ini bug paling berbahaya yang bisa dibuat junior di sini.
2. **Pakai bound parameters** (`conditions` + `bind`), jangan pernah concat string ke query — SQL injection.
3. **Logic taruh di `Library\`, bukan di controller.** Controller tipis: ambil input → panggil library/model → lempar ke view. Contoh role model: `CiptalifeApi.php`.
4. **Logging pakai `Library\Logger`** (Monolog): `$this->log = Logger::get('NamaKomponen');` — jangan `error_log()` / `var_dump()`.
5. **Jangan hardcode credential/URL.** Config per environment ada di `app/config/{development,staging,production-*}.php`. Ikuti cara nilai config existing dibaca (lihat `config.php` + `services.php`).
6. **Hati-hati state di Swoole.** Ini long-running process, bukan PHP-FPM klasik: `static` variable & singleton bakal persist antar request. Jangan simpan state per-request di static. (`swoole-server.php` bikin DI baru per request justru untuk alasan ini.)
7. **Ikuti konvensi penamaan:** `XxxController` + `xxxAction`, view folder PascalCase, task `XxxTask`, library `PascalCase.php` di `Library\`.
8. **Jangan sentuh modul besar yang bukan punya lu** tanpa paham owner boundary-nya — banyak modul (Ticket, Communicator, ChatbotAI) saling terkait.
9. **Partial render untuk AJAX** pakai `$this->view->getRender(...)`, JSON response pakai `$this->view->disable()` + `setJsonContent()`.
10. **Sebelum bikin file baru, cari dulu yang mirip.** Codebase ini 100+ library, 100+ controller — hampir semua pattern udah pernah ada. Grep dulu, contek pattern-nya.

---

## Bagian 5 — Git Workflow ✅ (observed dari branch nyata)

Repo ini pakai **Gitflow** dengan naming convention ketat, terikat tiket Jira:

```
develop                                          ← branch integrasi utama
feature/DNGO19-2902_Improvement-Penerapan-AI-Pada-Dashboard
        └──[kode Jira]──└──[deskripsi-pakai-dash]
release/1.118.0_rc1                              ← release candidate, semver
hotfix/1.117.5                                   ← patch production
hotfix/1.108.2_SNGOC-3074_Perbaikan-Error-Dialogflow  ← hotfix + tiket
```

Observed dari log: release di-cut dari develop sebagai `release/x.y.z_rcN`, ada commit bump `update version to 1.118.0`, hotfix di-merge balik ke release/develop. Ada `merge_request.sh` di monorepo (flow MR/PR via script) dan `captainhook.json` (git hooks). Deploy via Jenkins (`Jenkinsfile.deploy`, `Jenkinsfile.rollback`).

**Workflow lu sebagai dev:**

```bash
git checkout develop
git pull origin develop
git checkout -b feature/DNGO19-XXXX_Review-Intelligence-Discovery   # pakai nomor tiket lu
# ... ngoding, commit kecil-kecil dengan pesan jelas ...
git push origin feature/DNGO19-XXXX_Review-Intelligence-Discovery
# lalu buat merge request ke develop (cek merge_request.sh / flow tim)
```

Format commit message yang observed: `<Modul> : <deskripsi perbaikan>` — contoh nyata: `Report outbound : Fix error datatable report outbound by subject & by status`.

Aturan main:
- ❌ Jangan commit langsung ke `develop`, `release/*`, apalagi `hotfix/*` yang bukan punya lu
- ⚠️ Working copy sekarang lagi di `hotfix/1.118.1` — pindah dulu sebelum ngoding
- ✅ Satu tiket = satu feature branch
- ✅ Hotfix hanya untuk bug production urgent, di-branch dari release/tag terkait

---

## Bagian 6 — Analisa Integrasi: Review System × Onebox

### 6.1 🔥 Temuan paling penting: OVERLAP BESAR

Onebox **sudah punya** infrastruktur yang fungsinya beririsan dengan Hermina Crawler:

| Yang Hermina punya | Yang Onebox SUDAH punya ✅ |
|---|---|
| Selenium Google Maps crawler | `Library\SeleniumCrawler.php`, `ScrapeopsCrawler.php`, `FlaresolverrCrawler.php`, `CurlCrawler.php`, `Crawler.php`, `CrawlerDb.php` |
| Ambil Google review | `Library\Gbusiness.php` → **`getListReviews($account, $location)`**, `GoogleBusiness.php`, `MyBusiness.php` |
| AI analysis (sentiment, dll) | `Library\OpenAi.php`, `OpenAiAssistant.php`, `Chatgpt.php` + fitur ChatbotAI aktif dikembangkan (banyak feature branch AI) |
| Scheduled crawl | `tasks/CrawlerTask.php`, `GbusinessTask.php`, `GoogleTask.php` + Gearman worker + scheduler |
| Dashboard/insight UI | Controller & view `Digitalinsight`, `Mediamonitoring`, `Dashboard` |

⚠️ Catatan: `Gbusiness.php` kemungkinan pakai **Google Business Profile API resmi** (butuh kepemilikan/akses akun GBP lokasi), sedangkan Hermina scraping publik Google Maps — beda pendekatan, beda coverage, beda risiko ToS. Ini perlu diverifikasi sebelum klaim redundan.

### 6.2 Tiga opsi arsitektur

**Opsi A — Hermina tetap microservice terpisah, Onebox pull via REST** *(sesuai superprompt)*

| Pros | Cons |
|---|---|
| Isolasi total: Selenium/Chrome yang berat & rapuh tidak hidup di dalam proses Swoole Onebox | Ada 2 sistem untuk di-maintain, 2 deploy pipeline |
| FastAPI + Python ecosystem lebih enak untuk scraping & AI | Butuh auth service-to-service yang belum final |
| Sudah jadi & terbukti jalan; tinggal integrate | Data duplikat (DB crawler + kemungkinan DB Onebox) |
| Preseden pattern-nya SUDAH ADA di Onebox: `CiptalifeApi.php` = external REST client + JWT login persis seperti kebutuhan lu | Latency & failure mode baru (timeout, 401, service down) |
| Kalau crawler mati, Onebox tetap hidup | Tenant mapping (siteId ↔ lokasi RS) harus didesain |

**Opsi B — Rebuild semua di dalam Onebox pakai library existing**

| Pros | Cons |
|---|---|
| Satu codebase, satu deploy, tanpa auth antar-service | Selenium di dalam ekosistem Onebox = berat, rapuh, dan superprompt lu sendiri melarang ini ("Jangan menjalankan Selenium dari OneBox") |
| Reuse `Gbusiness`, `OpenAi`, `CrawlerTask` | Kerja tulang: porting semua logic Python → PHP |
| Native multi-tenant dari awal | Buang investasi yang sudah jalan di Hermina |
|  | Scraping berskala di proses Swoole bisa ganggu stabilitas product utama |

**Opsi C — Hybrid (REKOMENDASI): Hermina = crawling+analysis engine, Onebox = UI + storage + management**

- Hermina tetap terpisah, tugasnya: crawl + AI analysis + expose REST API.
- Onebox bikin `Library\HerminaCrawlerClient.php` **meniru pattern `CiptalifeApi.php`** (login, token caching, timeout, Monolog, structured error).
- Sync task `tasks/HerminaSyncTask.php` (contek `CrawlerTask.php`) narik data berkala → **persist ke tabel Onebox** (bukan proxy realtime) → UI Onebox baca dari DB lokal.
- Kenapa persist, bukan proxy: (1) UI Onebox tetap hidup walau crawler down; (2) bisa di-scope `site_id` native; (3) fitur "dikelola" (assign, follow-up, tanggapi review — permintaan CEO) butuh state di sisi Onebox; (4) reporting/dashboard Onebox bisa join dengan data existing.
- Dedup pakai `review_hash` / `external_review_id` (sudah ada di response API Hermina).

### 6.3 Gap analysis — dan cara nutupnya

| # | Gap | Solusi |
|---|---|---|
| 1 | **Auth service-to-service** — JWT user-based Hermina gak cocok untuk machine-to-machine | Short-term: service account khusus + login JWT (pattern CiptalifeApi persis begini). Long-term: API key statis atau network-internal only (docker network/VPN). Simpan credential di config per-env Onebox, bukan hardcode |
| 2 | **Tenant mapping** — Hermina punya `location_id`, Onebox punya `site_id` | Tabel mapping `hermina_location_map (site_id, hermina_location_id)` di Onebox; sync task iterate per mapping |
| 3 | **Persist vs proxy** belum diputuskan | Rekomendasi: persist (alasan di 6.2 Opsi C). Butuh keputusan lead sebelum bikin migration |
| 4 | **Delta sync** — API Hermina belum punya `updated_since`/cursor | Tambah param `updated_since` di sisi FastAPI (kerjaan kecil, lu owner-nya), atau interim: pull `latest_first=true` + stop saat ketemu `review_hash` yang sudah ada |
| 5 | **UI porting Next.js → Volt** — FE Hermina cuma benchmark visual | Jangan port React-nya. Ambil desainnya (layout, warna, komponen dashboard) lalu implement ulang pakai Volt + template/CSS existing Onebox (`app/views/layouts/`, cek kelas yang dipakai `Dashboard`/`Digitalinsight` sebagai referensi terdekat). Target "11/12" realistis kalau chart pakai lib JS yang sudah ada di Onebox |
| 6 | **Scheduler** | Sudah ada: Phalcon CLI task + scheduler container. Tinggal bikin `HerminaSyncTask` dan daftarin ke scheduler (cek `scheduler.sh` / `docker-compose.scheduler.yml` cara daftarnya) |
| 7 | **Duplikasi dengan `Gbusiness`** | Presentasikan ke lead: Hermina = scraping publik tanpa perlu akses GBP owner; Gbusiness = API resmi. Bisa koeksis, tapi harus explicit biar gak dianggap reinvent |
| 8 | **Error handling & observability** | Timeout eksplisit, retry terbatas + backoff di client; log via `Logger::get('HerminaCrawler')`; jangan log credential |

### 6.4 Risiko terbesar

1. **Data leak antar tenant** kalau sync/persist gak di-scope `site_id` dengan benar — ini yang paling fatal di product multi-klien.
2. **Bikin fitur redundan** tanpa restu lead padahal `Gbusiness`/`Digitalinsight` exist — validasi dulu positioning-nya (pertanyaan #7 di atas).
3. **Ngoding di branch salah** — sekarang working copy di `hotfix/1.118.1`.
4. **Swoole memory/state pitfalls** kalau client HTTP-nya nyimpen state static.

---

## Bagian 7 — Roadmap Next Steps

### Phase 0 — Validasi & Setup (minggu ini)
- [ ] Konfirmasi ke lead: (a) persist vs proxy, (b) positioning vs `Gbusiness`/`Digitalinsight`, (c) auth model service-to-service, (d) minta tiket Jira (DNGO19-xxx)
- [ ] Bikin feature branch dari `develop`
- [ ] Jalanin dev environment lokal (`swoole-dev.sh` / tanya flow tim), pastikan bisa buka app

### Phase 1 — Latihan + Scaffold (1–3 hari)
- [ ] Implement mock feature `ReviewMonitor` dari Bagian 3 end-to-end sampai muncul di menu — ini sekaligus onboarding MVC lu
- [ ] Pelajari `CiptalifeApi.php` sampai paham betul (ini template client lu)

### Phase 2 — Integration Client (placeholder → live)
- [ ] `Library\HerminaCrawlerClient.php`: `health()`, `login()`, `getReviews($params)`, `getDashboardOverview()` — mock fixture dulu, lalu live ke crawler di docker
- [ ] Config env placeholder di config per-environment (ikuti pattern existing, bukan .env style)
- [ ] Dev-only test-connection action di controller

### Phase 3 — Data layer
- [ ] Field mapping table (crawler → Onebox), keputusan nullable/transform
- [ ] Migration tabel review + mapping lokasi (SETELAH keputusan persist)
- [ ] `tasks/HerminaSyncTask.php` + dedup via `review_hash`

### Phase 4 — UI & Production
- [ ] Port desain FE Next.js ke Volt pakai template Onebox
- [ ] Registrasi menu + role
- [ ] Retry/backoff, monitoring, integration test, lalu MR ke develop

---

*Dokumen ini hasil eksplorasi read-only; tidak ada file di repo onecloud yang diubah.*
