# Onebox / OneCloud — DFD (Data Flow Diagram)

> **Status:** Living document — dibangun dari dokumen "Onebox – DFD, ERD". Beberapa diagram masih menyusul, jadi isi bisa bertambah. Lihat **Coverage Tracker** di bagian bawah.
> **Tujuan:** Referensi tunggal pemahaman alur data Onebox untuk (a) developer dan (b) AI agent. Ditulis dari pembacaan diagram; hal yang belum diverifikasi ke kode/DB ditandai ⚠️.
> **Companion:** [erd.md](erd.md) (struktur data) · [ONEBOX_ONECLOUD_DEV_GUIDE.md](ONEBOX_ONECLOUD_DEV_GUIDE.md) (cara ngoding + analisa integrasi).

---

## Cara Baca DFD Ini

- **Lingkaran** = *Process* (proses/aktivitas yang mengolah data). Diberi nomor hierarkis (`2.2.7` = anak dari `2.2` yang anak dari `2`).
- **Kotak** = *External Entity* (aktor/sistem di luar boundary: user, channel, server).
- **Garis dua sisi / label bergaris** = *Data Store* (tabel/penyimpanan; mis. `Ticket`, `Site`).
- **Panah** = aliran data, dengan label isi datanya.
- Penomoran mengikuti dekomposisi: Level 0 (context) → Level 1 → Level 2 → Level 3.

**Prinsip kunci Onebox:** hampir semua data di-scope per **`Site`** (= tenant). Ini pondasi multi-tenancy; di kode tercermin lewat `site_id` / `$this->getSiteId()`.

---

## 🔑 Keputusan Terkunci (Review Intelligence) — dari lead Agung

- Data review **di-persist ke data store `Ticket`** ("sesuai yg sudah berjalan"), lewat modul **`Mediamonitoring`** existing — **bukan** proses/domain baru.
- **Terverifikasi di kode:** `MediamonitoringController` sudah menjalankan pola "scraping → `Ticket` (dengan kolom `Sentiment`) → dashboard/report" (dashboardSentimen, reportSLA, reportAnalisa, trendNews). Jadi alur DFD Review Intelligence = **memperkaya sumber/analisa `2.1 Manage Message` + reuse reporting `2.3.x`**, bukan bikin cabang baru.
- UI target: **dashboard VOC** consume data inbound + scraping dari internal table.
- **Deliverable pertama = tasklist fitur (tiap task ≤5 hari kerja / 5MD)** → dasar tiket Jira. Kode belakangan.

---

## Level 0 — Context Diagram

Satu proses tunggal **Onebox Cloud** dengan external entity di dua sisi:

**Aktor internal (role):**
`Agent TS` · `Agent CS` · `Supervisor` · `Admin` · `Supervisor Sales` · `AgentSales`

**Channel / eksternal:**
`Email` · `Facebook` · `Twitter` · `Instagram` · `Whatsapp` · `Livechat` · `Public`

> **Interpretasi:** Onebox = hub omnichannel. Sisi kiri (role) mengoperasikan sistem; sisi kanan (channel) adalah sumber & tujuan pesan. Di kode, channel = library di `app/library/` (`Waba.php`, `Facebook.php`, `Instagram.php`, `Line.php`, dst).

---

## Level 1 — Tiga Proses Inti

| # | Proses | Data store utama |
|---|--------|------------------|
| 1 | **Registrasi** | Registration, Site, User |
| 2 | **Layanan Pelanggan** | Message, Ticket, Contact |
| 3 | **Prospect Management** | Contact, Prospect |

Alur besar: registrasi tenant (1) → melayani pelanggan lewat tiket (2) → mengelola calon/prospek (3). Entity `User` menyentuh ketiganya.

---

## Proses 1 — Registrasi (Level 2)

Dekomposisi `1`:

| # | Sub-proses | Data store yang disentuh |
|---|-----------|--------------------------|
| 1.1 | **Site Registration** | Site, Registration, User, Contact, Message |
| 1.2 | **Setup Parameter** | Category, Organization, Member, User, Contact, Product, Region |
| 1.3 | **Create User & Team** | User, Member, Organization (aktor: User/Admin) |
| 1.4 | **Manage Connection** | Connection, SiteBenefit |

### 1.1 Site Registration (Level 3)

Urutan onboarding tenant baru:

| # | Proses | Catatan / data store |
|---|--------|----------------------|
| 1.1.1 | Create Registration | → `Registration` |
| 1.1.2 | Choose Package | → `SiteBenefit`, `SiteProduct` (pilih paket langganan) |
| 1.1.3 | Create Site | → `Organization`, `Site` |
| 1.1.4 | Create User | → `User`, `Member`, `UserRole` |
| 1.1.5 | Setup Site | konfigurasi awal site |
| 1.1.6 | Send Email Verification | → `Contact` (aktor `Server`) |
| 1.1.7 | Update Password | → `Registration`, `User` |
| 1.1.8 | Login | validasi kredensial, mulai sesi |

> **Interpretasi:** alur klasik SaaS signup: daftar → pilih paket → buat site+org → buat user admin → verifikasi email → set password → login. `Member` = jembatan `User`↔`Site` beserta role-nya.

### 1.2 Setup Parameter (Level 3)

Master data per-site yang dikelola admin:

| # | Proses | Data store |
|---|--------|-----------|
| 1.2.1 | Manage Category | `Category` |
| 1.2.2 | Manage Product | `Product` |
| 1.2.3 | Manage Region | `Region` |
| 1.2.4 | Manage Tipe Contact | `SiteReference` |
| 1.2.5 | Manage GUI | `Settings` (logo, coloring, dsb) |

> **Relevan integrasi:** `1.2.5 Manage GUI → Settings` menyimpan tema/branding per-site (logo, warna). Ini yang harus dihormati saat membangun UI Review Intelligence agar konsisten dengan template existing.

### 1.4 Manage Connection (Level 3)

Kelola akun channel (koneksi ke WhatsApp/FB/dll):

| # | Proses | Catatan |
|---|--------|---------|
| 1.4.1 | Create Channel | divalidasi ke `SiteBenefit` (limit paket!) → `Connection` |
| 1.4.2 | Setup Provider | aktor `Server` |
| 1.4.3 | Update Account Media | |
| 1.4.4 | Update Provider | |
| 1.4.5 | Delete Account Media | |
| 1.4.6 | Find Channel | |
| 1.4.7 | View Channel | |

> **Interpretasi penting:** jumlah channel yang boleh dibuat dibatasi oleh **`SiteBenefit`** (paket langganan). `Connection` = satu akun channel milik satu site. ⚠️ Kalau Review Intelligence diperlakukan sebagai "channel/media source", ia berpotensi tunduk pada mekanisme limit paket ini — perlu keputusan desain.

---

## Proses 2 — Layanan Pelanggan (Level 2)

Jantung produk. Pesan masuk dari channel → jadi tiket → dikerjakan agent → dilaporkan.

| # | Sub-proses | Data store |
|---|-----------|-----------|
| 2.1 | **Manage Message** | Message, Connection, Data (+ input: `Media`, `System`) |
| 2.2 | **Manage Ticket** | Ticket (+ banyak store pendukung) |
| 2.3 | **Report Ticket** | Ticket, Message |
| 2.4 | **Manage Contact** | Contact |

Alur: `Media (Email/Sosmed/Livechat)` + `System` → **2.1 Manage Message** (inbound/outbound, baca `Connection` untuk tahu akun asal) → membentuk **Ticket** → **2.2/2.3/2.4**.

### 2.2 Manage Ticket (Level 3) — Lifecycle Tiket

| # | Proses | Data store / catatan |
|---|--------|----------------------|
| 2.2.1 | Create Ticket | `Ticket` |
| 2.2.2 | Assign Ticket | `TicketAssignee` |
| 2.2.3 | Assign Ticket to Team | `TicketGroup` |
| 2.2.4 | Reassign Ticket | `TicketAssignee` |
| 2.2.5 | Find Ticket | |
| 2.2.6 | View Ticket | baca `Reference`, `Category`, `Product`, `Region`, `Message`/`MessageContent`/`MessageUser`, `Contact`, `Attachment`, `File` |
| 2.2.7 | Reply Ticket | `Message` (+ `Template`) |
| 2.2.8 | Forward Ticket | via `Connection` |
| 2.2.9 | Send Note | `Notes`, `Notification` |
| 2.2.10 | Save Quick Response | `Template` |
| 2.2.11 | Choose Quick Response | `Template` |
| 2.2.12 | Update Ticket | `Ticket`, `Template` |
| 2.2.13 | Pending (Hold) Ticket | status → **Pending** |
| 2.2.14 | Mark as Spam | status → **Spam** |
| 2.2.15 | Resolve Ticket | status → **Resolve** |
| 2.2.16 | Close Ticket | status → **Close** |

**State tiket (observed):** `Pending` · `Spam` · `Resolve` · `Close` (+ status awal open/new saat Create).

### 2.3 Report Ticket (Level 3) — Layer Analitik

| # | Proses | Metrik / sumber |
|---|--------|-----------------|
| 2.3.1 | Dashboard | Count Ticket, Response Time, Resolution Time |
| 2.3.2 | Rpt Case | data case dari `Ticket` |
| 2.3.3 | Rpt Interaction | `Message`, `MessageContent` |
| 2.3.4 | Report SLA | Info Case, Response Time, Resolution Time |
| 2.3.5 | Report Mapping Case | Case by Category / Media |
| 2.3.6 | Report Trend | Count Case, Count Message |

> **Relevan integrasi (penting):** pola dashboard/SLA/trend ini adalah **template visual & metrik yang sudah matang** di Onebox. Untuk dashboard Review Intelligence, pola `2.3.x` lebih relevan sebagai acuan ketimbang FE Next.js Hermina.

### 2.4 Manage Contact

`New Contact` / `Info Contact` ↔ data store `Contact`. Contact = identitas pelanggan/pengirim pesan.

---

## Proses 3 — Prospect Management

Data store: `Contact`, `Prospect`. ⚠️ Dekomposisi Level 2/3 belum ada di batch diagram yang diterima — lihat Coverage Tracker.

---

## Indeks Data Store (dari DFD)

Tenant/identitas: `Registration`, `Site`, `Organization`, `User`, `Member`, `UserRole`
Paket/langganan: `SiteBenefit`, `SiteProduct`
Master data: `Category`, `Product`, `Region`, `SiteReference`, `Reference`, `Settings`
Channel: `Connection`
Layanan pelanggan: `Message`, `MessageContent`, `MessageUser`, `Ticket`, `TicketAssignee`, `TicketGroup`, `Contact`, `Notes`, `Notification`, `Template`, `Attachment`, `File`, `Data`
Prospek: `Prospect`

---

## Bagaimana DFD Ini Menuntun Integrasi Review Intelligence

1. **Semua aliran data punya boundary `Site`.** Data review wajib masuk ke boundary yang sama (scoped `site_id`), termasuk siapa yang boleh melihat/mengelola (via `Member`/`UserRole`).
2. **Dua pola integrasi kandidat** (harus divalidasi ke lead):
   - **A. Domain paralel** — review = data store baru + proses baru (mis. `Manage Review`, `Report Review`), mirip pola `2.x` tapi terpisah dari Ticket. Aman, terisolasi, cocok untuk langkah awal.
   - **B. Sumber media baru** — review masuk sebagai input ke `2.1 Manage Message` → membentuk `Ticket` → reuse seluruh lifecycle `2.2` dan reporting `2.3`. Sangat native, tapi invasif (menyentuh modul inti) dan mungkin tunduk limit `SiteBenefit`.
3. **Reporting Review Intelligence** sebaiknya meniru pola `2.3.x` (Dashboard, SLA, Trend, Mapping) agar konsisten dan reuse komponen.
4. **UI harus hormati `Settings` (1.2.5)** — logo/coloring per-site.

---

## Coverage Tracker

| Bagian DFD | Status |
|------------|--------|
| Level 0 Context | ✅ |
| Level 1 (3 proses) | ✅ |
| 1.1 Site Registration (L3) | ✅ |
| 1.2 Setup Parameter (L3) | ✅ |
| 1.3 Create User & Team (L3) | ⚠️ hanya terlihat di L2, dekomposisi detail belum |
| 1.4 Manage Connection (L3) | ✅ |
| 2.1 Manage Message (L3) | ⚠️ terlihat di L2, dekomposisi detail belum |
| 2.2 Manage Ticket (L3) | ✅ |
| 2.3 Report Ticket (L3) | ✅ |
| 2.4 Manage Contact (L3) | ⚠️ terlihat di L2, dekomposisi detail belum |
| 3 Prospect Management (L2/L3) | ❌ belum ada diagram |

*Diperbarui seiring batch diagram berikutnya masuk.*
