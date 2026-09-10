# OneBox — API Guide (cara kerja & contoh pakai)

> Diverifikasi dari kode: `app/config/routes.php`, `app/controllers/api/*` (RESTController, AuthController), `app/controllers/MediamonitoringController.php`.
> **Poin terpenting:** OneBox punya **DUA gaya API yang beda**. Lu wajib tau bedanya karena menu VOC lu (RI-10/11/12) bakal pakai **Gaya B**, bukan Gaya A.

---

## Ringkasan: Dua Gaya API OneBox

| | **Gaya A — REST Resource API** | **Gaya B — Controller Action (JSON)** |
|---|---|---|
| URL | `/api/v1/<resource>` | `/<Controller>/<action>` |
| Contoh | `GET /api/v1/ticket/123` | `GET /Mediamonitoring/dataChart` |
| Auth | **JWT token** (Bearer / `?token=`) | **Session login** (cookie web) |
| Sumber | auto-CRUD dari Model (`RESTController`/`ModelController`) | action di controller biasa, return `setJsonContent()` |
| Dipakai untuk | client eksternal / mobile app | **frontend web internal (SPA seperti Mediamonitoring)** |
| **Buat VOC menu lu** | ❌ bukan ini | ✅ **INI yang lu tiru** |

> **Kesimpulan buat kerjaan lu:** menu VOC ngikutin **Gaya B** — bikin action di `VocController` yang return JSON, di-auth pakai session login web yang udah ada (`$this->getSiteId()` dari session), persis kayak `MediamonitoringController::dataChartAction`. Gaya A (REST) itu buat integrasi eksternal, bukan buat SPA internal.

---

## Bagian 1 — Gaya A: REST Resource API

### Arsitektur
Auto-CRUD dari model. Satu resource = satu controller di `app/controllers/api/v1/`. Ada 100+ resource (Ticket, Contact, Case, Message, Category, Connection, Agent, Campaign, dst).

### Route pattern (verified dari routes.php)
| Method | Path | Fungsi |
|---|---|---|
| `GET` | `/api/v1/:resource` | list (+ paging/filter) |
| `GET` | `/api/v1/:resource/{id}` | ambil satu |
| `POST` | `/api/v1/:resource` | create |
| `PUT` | `/api/v1/:resource/{id}` | replace |
| `PATCH` | `/api/v1/:resource/{id}` | update sebagian |
| `DELETE` | `/api/v1/:resource/{id}` | hapus |
| `OPTIONS` | `/api/v1/:resource` | CORS preflight |

Versi tanpa `/v1` juga ada (`/api/:resource`) → default ke v1.

### Auth (verified) ⚠️ pakai endpoint yang BENAR
- **Login:** `POST /api/v1/authenticate` — **`AuthenticateController::post`** (bukan `AuthController`!).
  - `AuthenticateController` = satu-satunya yang matiin JWT guard (`__construct(true, false, false)`) → boleh diakses tanpa token. ✅
  - `AuthController::login` = **JANGAN dipakai buat login pertama** — dia masih dijaga `verifyJwt` → balikin `401 "jwt token not found"` (chicken-and-egg).
  - **Body: `x-www-form-urlencoded`** (kodenya baca `$request->get()`, BUKAN raw JSON). Field: `email`, `password`, `siteId` (opsional).
  - Kalau `siteId` kosong & user punya >1 site → response = **daftar site** (bukan token). Pilih satu `Id` → kirim ulang dengan `siteId` terisi → baru dapet token.
- **Pakai token:** tiap request kirim token via **query param `?token=<jwt>`** atau **header `Authorization`** (JWT). Kalau nggak ada → `401 "jwt token not found"`. (`RESTController` line ~167, ~422)

### Query params umum (list endpoint) — verified dari `RESTController::parseRequest`
`limit`, `offset`, `paging`, `q` (search), `fields`, `since`, `sinceId`, `lastUpdate`, `connectionId`, `email`, `token`

### Contoh Postman (Gaya A) — VERIFIED
```
# 1. login (endpoint BENAR: authenticate, bukan auth/login)
POST https://localhost.onebox.co.id/<basepath>/api/v1/authenticate
Body → x-www-form-urlencoded:
  email    = admin-news@ciptadrasoft.com
  password = Admin123
  siteId   = (kosongin; kalau dapet daftar site, kirim ulang dgn siteId terpilih)
→ dapat token

# 2. list ticket (pakai token)
GET https://localhost.onebox.co.id/<basepath>/api/v1/ticket?limit=10&token=<jwt>

# 3. satu ticket
GET https://localhost.onebox.co.id/<basepath>/api/v1/ticket/123?token=<jwt>
```
> `<basepath>` = nilai `ONECLOUD_PATH` (buat branch lu: `feature/DNGO19-3346`). Cek pasti-nya: `./printenv.sh local | grep ONECLOUD_PATH`.

---

## Bagian 2 — Gaya B: Controller Action JSON (INI yang lu tiru)

### Cara kerja
Action biasa di controller yang matiin view + return JSON. Contoh nyata dari Mediamonitoring:
```php
// pola yang bakal lu tiru di VocController
public function dataChartAction($type = 'sentiment')
{
    $this->view->disable();
    $siteId = $this->getSiteId();                 // auth dari SESSION, bukan token
    // ... query Ticket di-scope siteId ...
    $this->response->setContentType('application/json');
    $this->response->setJsonContent(['data' => $result]);
    return $this->response;
}
```
Diakses: `GET /Mediamonitoring/dataChart?type=sentiment` (dipanggil AJAX oleh SPA-nya).

### Auth
Pakai **session web** — user harus udah login lewat halaman login OneBox. `$this->getSiteId()` ambil tenant dari session. **Nggak pakai token.** Makanya kalau lu buka action ini di Postman tanpa cookie session → ke-redirect ke login / ditolak.

### Buat menu VOC lu (RI-10/11/12)
Endpoint yang bakal lu bikin, contoh:
```
GET /Voc/listReview          → return partial HTML atau JSON list review
GET /Voc/dataChart?type=...  → JSON buat dashboard (sentiment/urgency/trend)
GET /Voc/detail/{id}         → JSON detail satu review
```
Semua di-scope `$this->getSiteId()`, semua baca tabel `Ticket` (filter MediaId review).

---

## Bagian 3 — Cara Paling Andal Mahamin API OneBox: DevTools

Karena OneBox app gede & routing-nya banyak custom, **cara tercepat & paling akurat** buat liat API asli yang dipakai: **intip Network tab di browser.**

1. Buka app OneBox yang jalan (URL dari `printenv.sh`), login.
2. Buka modul **Mediamonitoring** (yang paling mirip target lu).
3. Buka **DevTools (F12) → tab Network → filter Fetch/XHR**.
4. Klik-klik menu (dashboard, list, filter) → liat request yang muncul:
   - **URL asli** endpoint-nya (ini ground truth, bukan tebakan)
   - **Method + params** yang dikirim
   - **Header** (ada token/cookie apa)
   - **Response** JSON-nya (buat tau shape data)
5. Klik kanan request → **Copy → Copy as cURL** → di Postman **Import → Raw text** → paste. Jadi request Postman siap pakai.

> Ini bakal langsung nunjukin: menu Mediamonitoring pakai Gaya B (action JSON + cookie session). Itu blueprint langsung buat VocController lu.

---

## Bagian 4 — Relevansi ke Kerjaan Lu

- **Menu VOC lu = Gaya B.** Contek pola `MediamonitoringController` action yang return JSON, auth session, scope SiteId, baca Ticket.
- **Gaya A (REST) hampir nggak kepake** buat fitur ini — kecuali nanti ada kebutuhan expose review ke sistem eksternal.
- **Jangan bikin auth token sendiri** buat menu VOC — pakai session login OneBox yang udah ada.
- Sebelum nulis view/action VOC, **jalanin Bagian 3 (DevTools)** di Mediamonitoring 15 menit — lu bakal langsung paham request/response pattern yang harus lu tiru.

---

## Catatan Verifikasi
- Route pattern & CRUD verbs: ✅ verified (`routes.php`).
- Token auth Gaya A + login POST email/password: ✅ verified (`AuthController`, `RESTController`).
- Gaya B (action JSON + session): ✅ verified (`MediamonitoringController`).
- **Path exact login & base path**: ⚠️ konfirmasi via DevTools (Bagian 3) — jangan diasumsikan.
