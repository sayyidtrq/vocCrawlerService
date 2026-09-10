# Voice of Customer — UI di OneBox (Media Monitoring)

> Dibuat 2026-07-16 · sisi OneBox (repo `onecloud`, branch `feature/DNGO19-3346_Media-Crawler-Google-Business-Review`)
> Menu VoC hidup **di dalam Media Monitoring** sebagai SPA route. Reviews = Volt; Dashboard = React embed.

---

## 1. Ringkasan

Fitur **Voice of Customer System** ditampilkan di OneBox sebagai bagian dari modul **Media Monitoring**:
di sidebar kiri MM ada grup **"Voice of Customer"** berisi submenu (Dashboard, Reviews, dst).
Klik submenu → tab kebuka **di dalam** MM (navbar + sidebar MM tetap), URL jadi
`.../Mediamonitoring/#/voc/<page>`.

Metode implementasi: **hybrid** —
- **Reviews** → Volt (server-rendered table + AJAX ke endpoint JSON).
- **Dashboard** → React embed (dari `app/react-views`, di-mount ke dalam tab MM).

## 2. Arsitektur (mengikuti pola MM yang sudah ada)

MM memakai **Sammy.js** (`public/js/routes.js`) untuk hash-route (`#/news/...`, `#/dashboard/...`).
Tiap route memanggil `openTabGeneral(id, title, 'Controller/action', 'Get')` yang **AJAX-load partial**
sebuah controller action ke tab (`#pageTabContent`). VoC mengikuti pola ini persis:

```
Sidebar MM  →  submenu VoC (NavigateUrl = #/voc/dashboard)
            →  Sammy route  this.get("#/voc/:page")
            →  openTabGeneral("voc_dashboard","VoC Dashboard","Voc/dashboard","Get")
            →  AJAX GET /Voc/dashboard  →  VocController::dashboardAction (render partial saja)
            →  partial di-append ke tab  →  (Dashboard) script mount React
```

Data:
```
VocController::reviewsData / dashboardData
   → query Ticket + Message + MessageContent (scoped SiteId + ProviderId 'PVD97')
   → JSON  →  Volt table / React dashboard
```

## 3. File yang dibuat/diubah (repo onecloud)

| File | Status | Isi |
|---|---|---|
| `app/controllers/VocController.php` | baru | `dashboardAction`/`reviewsAction` (render partial, `LEVEL_ACTION_VIEW`), `reviewsDataAction`/`dashboardDataAction` (JSON dari Ticket), 7 stub action |
| `app/views/Voc/reviews.volt` | baru | Partial tabel review + KPI (Volt + jQuery, AJAX ke `Voc/reviewsData`) |
| `app/views/Voc/dashboard.volt` | baru | Partial mount React (`<script>` classic + `import()` dinamis dari vite dev `localhost:5173`) |
| `app/views/Voc/stub.volt` | baru | Placeholder 7 screen lain |
| `app/react-views/src/features/voc/VocDashboard.tsx` | baru | Komponen dashboard React (KPI, distribusi sentimen/rating, top issue, monitoring cabang, review negatif) |
| `app/react-views/src/features/voc/mount.tsx` | baru | `export mountVocDashboard(el, {dataUrl})` |
| `public/js/routes.js` | ubah | Tambah Sammy route `this.get("#/voc/:page", ...)` |

**Catatan render partial:** view VoC TIDAK `extends templates.volt` — karena di-append ke tab via
jQuery `.append()`. Konsekuensi: `<script type="module">` tidak jalan saat di-inject, jadi Dashboard
memakai `<script>` classic + `import()` dinamis.

## 4. Sumber data (PENTING — bukan mock di UI)

- UI membaca **data `Ticket` REAL dari DB OneBox** (bukan data hardcoded).
- Review masuk ke OneBox lewat `VoiceOfCustomerSystemProvider` (`ProviderId 'PVD97'`, `MediaId 'GBUSINESS'`).
- Untuk saat ini review di-ingest dalam **mock mode** dari fixture
  `markdowns/07-data-and-seeding/field-mapping/implementation-plan/fixtures/reviews_sample.json`
  (snapshot **10 review Hermina asli**, 2 lokasi: Hermina Depok & HGA Depok).
- **Live pull** dari API VoC sudah diverifikasi terpisah (Codex). Untuk mengaktifkan live:
  set `Connection.Options.mock=false` + isi `Url`/`UserId`/`Password` (creds service user VoC).

Jadi: konten real, mengalir lewat pipeline real (provider → Ticket), UI 100% data-driven dari DB.
Yang "mock" hanya *cara seeding*-nya (fixture), bukan lapisan UI.

## 5. Perubahan DATABASE (dev — belum ada di git, perlu di-seed di env lain)

Perubahan DB tidak ikut ter-commit lewat kode. Berikut ringkasan + seed SQL untuk reproduksi.
Semua di **SiteId 169**.

### 5a. Master data / config
| Tabel | Perubahan |
|---|---|
| `Reference` | +1 row: `PVD97` (GroupId=Provider, Code=`VoiceOfCustomerSystem`) |
| `Category` | +18 row (Id 1054–1071): enum kategori VoC, slug disimpan di kolom `Remarks` |
| `Location` | +2 row: `1703` Hermina Depok, `1704` HGA Depok |
| `Connection` | +2 row: `1039` (VoC Hermina Depok, TargetId=4), `1040` (VoC HGA Depok, TargetId=2); `MediaId='GBUSINESS'`, `ProviderId='PVD97'`, `Options` berisi `mock`, `mock_file`, `location_map` |
| `Menu` | +10 row: `1375` SIDEMENU "Voice of Customer" (ParentId=**254**=header MM "Semua Sumber") + `1376–1384` SUBSIDEMENU (NavigateUrl `#/voc/*`) |
| `Permission` | +ALLOWED untuk menu VoC, role 1/6/15/17/22/23 |

### 5b. Dihapus (percobaan menu pertama yang salah tempat)
- HEADERMENU `1365` + SIDEMENU `1366–1374` + Permission-nya (dulu nongol di top-navbar; sudah dihapus).

### 5c. Data review (dev-only, JANGAN di-seed ke prod)
Dibuat otomatis saat menjalankan provider (mock mode): ~15 `Ticket` + `Message` + `MessageContent` +
`Contact` (channel GBUSINESS, ConnectionId 1039/1040). Ini yang tampil di UI. Di env lain, ini dihasilkan
dengan menjalankan ingest, bukan di-seed manual.

### 5d. Seed SQL (master data + menu) untuk reproduksi
> ⚠️ `Id` di bawah menyesuaikan auto-increment env masing-masing; sesuaikan `ParentId=254` dengan
> Id header MM "Semua Sumber" di env target. Idealnya dijadikan migration resmi.

```sql
-- Provider
INSERT INTO Reference (Id, Code, Description, GroupId, Sequence, Enabled, CreateDate, Creator, ModifyDate, Modifier, ExpireDate)
VALUES ('PVD97','VoiceOfCustomerSystem','Voice of Customer System','Provider',0,1,NOW(),1,NOW(),1,'3000-01-01 00:00:00');

-- Menu: grup Voice of Customer di sidebar MM (ParentId = header "Semua Sumber", cek di env target)
INSERT INTO Menu (Code,TypeId,NavigateUrl,Visible,Enabled,Description,ImageUrl,Priority,BeginGroup,Collapsed,Level,CreateDate,Creator,ModifyDate,Modifier,ExpireDate,ParentId)
VALUES ('voc','SIDEMENU','',1,1,'Voice of Customer','fi-rr-comment-heart',6,1,1,1,NOW(),1,NOW(),1,'3000-01-01 00:00:00',254);
SET @voc := LAST_INSERT_ID();
INSERT INTO Menu (Code,TypeId,NavigateUrl,Visible,Enabled,Description,Priority,BeginGroup,Collapsed,Level,CreateDate,Creator,ModifyDate,Modifier,ExpireDate,ParentId) VALUES
('voc_dashboard','SUBSIDEMENU','#/voc/dashboard',1,1,'Dashboard',1,1,1,2,NOW(),1,NOW(),1,'3000-01-01 00:00:00',@voc),
('voc_reviews','SUBSIDEMENU','#/voc/reviews',1,1,'Reviews',2,1,1,2,NOW(),1,NOW(),1,'3000-01-01 00:00:00',@voc),
('voc_locations','SUBSIDEMENU','#/voc/locations',1,1,'Locations',3,1,1,2,NOW(),1,NOW(),1,'3000-01-01 00:00:00',@voc),
('voc_competitors','SUBSIDEMENU','#/voc/competitors',1,1,'Competitors',4,1,1,2,NOW(),1,NOW(),1,'3000-01-01 00:00:00',@voc),
('voc_fetchjobs','SUBSIDEMENU','#/voc/fetchjobs',1,1,'Fetch Jobs',5,1,1,2,NOW(),1,NOW(),1,'3000-01-01 00:00:00',@voc),
('voc_analysis','SUBSIDEMENU','#/voc/analysis',1,1,'Analysis',6,1,1,2,NOW(),1,NOW(),1,'3000-01-01 00:00:00',@voc),
('voc_insights','SUBSIDEMENU','#/voc/insights',1,1,'Insights',7,1,1,2,NOW(),1,NOW(),1,'3000-01-01 00:00:00',@voc),
('voc_reports','SUBSIDEMENU','#/voc/reports',1,1,'Reports',8,1,1,2,NOW(),1,NOW(),1,'3000-01-01 00:00:00',@voc),
('voc_settings','SUBSIDEMENU','#/voc/settings',1,1,'Settings',9,1,1,2,NOW(),1,NOW(),1,'3000-01-01 00:00:00',@voc);

-- Permission (sesuaikan RoleId dengan env target)
INSERT INTO Permission (ObjectName,ObjectId,RoleId,ActionId,SiteId,CreateDate,Creator,ModifyDate,Modifier,ExpireDate)
SELECT 'Menu', m.Id, r.RoleId, 'ALLOWED', '169', NOW(),1,NOW(),1,'3000-01-01 00:00:00'
FROM (SELECT 1 RoleId UNION SELECT 6 UNION SELECT 15 UNION SELECT 17 UNION SELECT 22 UNION SELECT 23) r
CROSS JOIN Menu m WHERE m.Code LIKE 'voc%';
```
(Seed Category 18 row + Connection + Location: lihat file SQL di `implementation-plan/` / catatan RI-05/06/07.)

## 6. Cara menjalankan (dev)

1. **Vite dev server** (untuk Dashboard React):
   ```bash
   cd app/react-views && npm run dev   # localhost:5173  (butuh Node 20+; di sini pakai nvm node 22)
   ```
   Catatan: `NODE_ENV=production` di container webapp membuat `react_url()` mencari build produksi.
   Karena belum ada build, `dashboard.volt` meng-import langsung dari `localhost:5173`. Untuk produksi:
   `npm run build` + `NODE_ENV != production` + pakai `react_url()`/`react_asset()`.
2. Buka **Media Monitoring** → **hard-reload (Ctrl+Shift+R)** agar `routes.js` terbaru terbaca.
3. Sidebar kiri → **Voice of Customer** → Dashboard / Reviews.

## 7. Batasan & langkah berikutnya

- Dashboard React: **peta risiko cabang (Leaflet) belum** — menyusul.
- 7 submenu lain (Locations, Competitors, Fetch Jobs, Analysis, Insights, Reports, Settings) masih **stub**.
- React embed **dev-mode** (butuh vite dev server); belum ada production build di OneBox.
- Untuk produksi: seed menu jadi **migration**, buat production build react-views, dan set Connection ke live (mock=false).
