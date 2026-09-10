# VoC Settings — Redesign Brief untuk Google Stitch

> Sumber: 2 screenshot halaman **Pengaturan → Voice of Customer → VoC Settings** (OneBox, `VocController`), dibenchmark terhadap pola halaman usage/entitlement SaaS modern, lalu diturunkan jadi brief siap-paste ke [Google Stitch](https://stitch.withgoogle.com/).
> Palet warna **diambil murni dari `style.css`** yang sedang dipakai OneBox (skin default INSPINIA) — tidak ada warna baru yang diperkenalkan.

---

## 1. Riset benchmarking singkat

Pola yang konsisten muncul di halaman usage/entitlement SaaS modern (Stripe billing usage, Vercel usage & limits, Notion workspace settings, Linear settings, GitHub billing):

- **Satu kartu = satu sumber kebenaran.** Nama fitur, status aktif/nonaktif, dan angka pemakaian digabung dalam satu unit visual — bukan dipisah jadi "daftar fitur" lalu "daftar kuota" yang isinya tumpang-tindih.
- **Progress bar, bukan teks pecahan.** `348 / 5.000` sebagai teks polos memaksa pembaca menghitung mental; produk-produk di atas selalu menaruh bar visual + persentase di sampingnya.
- **Warna status punya makna, bukan dekorasi.** Hijau = sehat, kuning/oranye = mendekati limit (biasanya ambang 80%), merah = habis/terlampaui. Status "belum aktif"/"perlu tindakan" tidak pernah memakai abu-abu polos yang menyaru dengan teks biasa — itu bikin state yang butuh aksi jadi tidak terlihat.
- **Kartu bisa punya CTA kontekstual**, bukan cuma tombol generik "+ Tambah kuota" di semua kartu tanpa membedakan apakah kartu itu memang butuh aksi user atau cuma informatif.
- **Info identitas statis (profil, organisasi) dipisah secara visual** dari info yang berubah (pemakaian, kuota) — biasanya jadi sidebar sempit di kanan, bukan kartu selebar halaman untuk 4 baris data.

Sumber: [SapientPro — SaaS UI/UX 2025](https://sapient.pro/blog/designing-for-saas-best-practices), [SchematicHQ — Entitlement Management System](https://schematichq.com/blog/entitlement-management-system), [Stripe Docs — App design patterns](https://docs.stripe.com/stripe-apps/patterns?locale=en-GB), [Duck.design — SaaS UX best practices](https://duck.design/ux-ui-design-for-saas/).

---

## 2. Diagnosis halaman saat ini (dari screenshot)

| # | Masalah | Bukti di screenshot |
|---|---|---|
| 1 | **Duplikasi informasi** — kuota yang sama muncul dua kali dalam bentuk berbeda | "Review dianalisis AI: 110/0" ada di kartu Entitlements *dan* diulang lagi di kartu terpisah "Pemakaian Kuota" |
| 2 | **Tidak ada progress bar** — semua angka kuota disajikan sebagai teks pecahan polos | `348 / 5.000 review`, `110 / 0 review` — tidak ada bar visual |
| 3 | **State "butuh tindakan" tersamar sebagai info biasa** | "Kuota crawl per hari — Belum aktif — belum terdaftar di katalog Benefit, migrasi belum dijalankan" ditulis abu-abu datar, padahal ini blocker yang perlu aksi admin |
| 4 | **State "habis" tidak diberi sinyal warna** | "Review dianalisis AI: 110/0 review — habis" ditulis teks abu-abu biasa, warna sama dengan teks deskriptif lain |
| 5 | **Kartu identitas statis makan lebar penuh** untuk data yang jarang berubah | "Profil Pengguna" & "Informasi Dasar Organisasi" masing-masing selebar halaman untuk ~4 baris label-value |
| 6 | **"Jadwal crawl aktif: 3/2 — habis"** = kuota **terlampaui**, tapi visualnya identik dengan kartu status sehat (badge hijau "Aktif") | Tidak ada eskalasi warna walau nilai melebihi limit |
| 7 | **Tidak ada jejak kepercayaan** (kapan terakhir sync, dari mana angka ini) | Tidak ada timestamp/breadcrumb di header |

---

## 3. Design tokens — diambil dari `style.css`

### Warna

| Token | Hex | Penggunaan asal di CSS | Dipakai untuk |
|---|---|---|---|
| `--primary` | `#00bcd4` | `.btn-primary`, `.nav-header`, `.progress-bar` | Tombol utama, ikon aktif, progress bar sehat (<70%) |
| `--primary-hover` | `#00aec5` | `.btn-primary:hover` | Hover state |
| `--success` | `#93dd56` | `.btn-success`, `.label-success`, `.progress-bar-success` | Badge "Aktif", progress bar sehat |
| `--info` | `#3ed9ef` | `.btn-info`, `.label-info` | Aksen sekunder / ikon informatif |
| `--warning` | `#ffa726` | `.btn-warning`, `.progress-bar-warning` | Progress bar mendekati limit (70–89%), badge "Perlu migrasi" |
| `--danger` | `#ea5395` | `.btn-danger`, `.progress-bar-danger` | Progress bar habis/terlampaui (≥90% atau melebihi kuota) |
| `--text-muted` | `#676a6c` / `#888888` | `body`, `.text-muted` | Body text sekunder, label |
| `--border` | `#e7eaec` | `.ibox-title`, `.border-bottom` | Garis pemisah antar section dalam kartu |
| `--surface` | `#ffffff` | `.ibox-content`, `.white-bg` | Permukaan kartu |
| `--surface-muted` | `#f3f3f4` | `.gray-bg`, `.todo-list > li` | Latar halaman / badge default |
| `--tint-primary` | `#e3f4fc` | `.light-primary` | Latar pill status "Aktif" (primer) |
| `--tint-success` | `#effae4` | `.light-success` | Latar pill status "Aktif" (varian hijau) |
| `--tint-warning` | `#fef7f0` | `.light-warning` | Latar pill status "Perlu migrasi" |
| `--tint-danger` | `#fff2f4` | `.light-danger` / `.light-magenta` | Latar pill status "Habis"/"Terlampaui" |
| `--dark-surface` | `#263238` | `body { background }` | Reserved — dipakai kalau ada varian dark shell, **tidak** dipakai di isi halaman ini |

### Tipografi & bentuk

- Font: `'Open Sans', 'Helvetica Neue', Helvetica, Arial, sans-serif` (skin default INSPINIA yang dipakai — bukan `.md-skin` yang pakai Roboto).
- Body base: 13px, `color:#676a6c`.
- Label mikro (mis. "SETUP PARAMETER", "USER PROFILE"): uppercase, ~10–11px, letter-spacing tipis, `.text-muted` — pola ini sudah bagus, **pertahankan**.
- Judul kartu (`h5` dalam `.ibox-title`): 14px, weight 400 default tapi disarankan naikkan ke 600 untuk hierarki lebih tegas di kartu entitlement (selaras `.font-bold`).
- Radius: `.btn { border-radius: 3px }`, kartu `.ibox` tidak pakai radius besar (garis lurus, border 1px `#e7eaec`) — **pertahankan look tegas ini**, jangan diganti radius besar ala card modern generik.
- Shadow: pakai `.shadow` (`box-shadow: 0 2px 2px 0 rgba(0,0,0,.14), 0 3px 1px -2px rgba(0,0,0,.2), 0 1px 5px 0 rgba(0,0,0,.12)`) hanya untuk kartu yang butuh sedikit elevasi (kartu entitlement di grid utama), sidebar cukup border tipis tanpa shadow biar tidak kompetisi visual.

---

## 4. Struktur halaman baru

```
┌─────────────────────────────────────────────────────────────────┐
│ Breadcrumb: Pengaturan / Voice of Customer / Benefit & Kuota     │
│ H1  Benefit & Kuota Voice of Customer         [Onebox Dev ▾]     │
│ sub Hak akses fitur VoC & sisa kuota untuk site ini.             │
│                              Tersinkron 3 menit lalu · Refresh ↻ │
├───────────────────────────────────────┬───────────────────────────┤
│ KOLOM UTAMA (8/12)                    │ SIDEBAR (4/12)            │
│                                        │                           │
│ ── Entitlements & Kuota (1 section) ──│ ┌ Profil Pengguna ───────┐│
│ ┌──────────────┐ ┌──────────────┐    │ │ admin-news              ││
│ │ Kuota review  │ │ Kuota crawl  │    │ │ admin-news@ciptadra...  ││
│ │ per bulan     │ │ per hari     │    │ │ Login terakhir: —       ││
│ │ [progress bar]│ │ ⚠ Perlu      │    │ └─────────────────────────┘│
│ │ 348/5.000 ·7% │ │  migrasi     │    │                           │
│ └──────────────┘ └──────────────┘    │ ┌ Organisasi ─────────────┐│
│ ┌──────────────┐ ┌──────────────┐    │ │ Onebox Development       ││
│ │ Review        │ │ Jadwal crawl │    │ │ dev.onebox.co.id         ││
│ │ dianalisis AI │ │ aktif        │    │ │ Default · ● Active       ││
│ │ [bar: habis]  │ │ [bar: 150%]  │    │ └─────────────────────────┘│
│ │ 110/110·habis │ │ 3/2·terlampaui│   │                           │
│ └──────────────┘ └──────────────┘    │                           │
│ ┌──────────────┐                      │                           │
│ │ Pelacakan     │                      │                           │
│ │ kompetitor    │                      │                           │
│ │ ● Aktif       │                      │                           │
│ └──────────────┘                      │                           │
└───────────────────────────────────────┴───────────────────────────┘
```

Breakpoint: 2 kolom di ≥992px, sidebar pindah ke bawah kolom utama di <768px (selaras `@media (max-width: 992px)` yang sudah ada di CSS untuk pola serupa).

**Section "Pemakaian Kuota" (Quotas) dihapus total** — datanya sudah melebur ke tiap kartu entitlement (poin diagnosis #1).

---

## 5. Spesifikasi komponen

### 5.1 Entitlement Card (komponen utama, ganti pasangan kartu Entitlements+Quotas lama)

Anatomi, top→bottom:
1. **Row header**: ikon dalam lingkaran (bg = tint warna status, 32px), judul kartu (14px/600), kode benefit sebagai pill monospace kecil di sebelah judul (mis. `VOC_REVIEW`) — reuse `.simple_tag`. Pill status di kanan atas: `Aktif` (`.light-success`), `Nonaktif` (`.light-gray`/`.badge-disable`), `Perlu migrasi` (`.light-warning`).
2. **Deskripsi 1 baris**, `.text-muted`, 12px.
3. **Usage meter** (hanya untuk entitlement yang punya angka kuota):
   - Progress bar horizontal 8–10px, reuse `.progress` + `.progress-bar` (bukan `.progress-bar-navy-light`).
     - `< 70%` terpakai → `.progress-bar` (teal primary)
     - `70–89%` → `.progress-bar-warning` (oranye)
     - `≥ 90%` atau melebihi kuota (>100%) → `.progress-bar-danger` (magenta)
   - Caption di bawah bar: `"348 / 5.000 review · 7% terpakai"`. Kalau habis: `"110 / 110 review · Habis"` dengan kata "Habis" berwarna danger, bold.
   - Kalau melebihi kuota (mis. jadwal 3 aktif dari kuota 2): caption jadi `"3 / 2 jadwal · Melebihi kuota"`, bar penuh warna danger walau> 100% (bar dikunci visual di 100% width, bukan overflow container).
4. **Footer aksi**, kontekstual per state:
   - Sehat/normal → tombol `.btn-primary.btn-outline` kecil: `+ Tambah kuota`.
   - `Perlu migrasi` → tombol `.btn-warning` solid: `Jalankan migrasi` (bukan dibiarkan tanpa CTA seperti sekarang), plus border-left accent 3px warna warning pada seluruh card (reuse pola `.agile-list li.warning-element`).
   - `Habis`/`Melebihi kuota` → tombol `.btn-danger` solid: `Naikkan kuota`, border-left accent 3px danger.
   - Binary toggle tanpa angka (mis. Pelacakan kompetitor) → tidak perlu bar, cukup baris `Aktif untuk site ini.` + toggle switch `.onoffswitch.enable` di kanan kalau butuh kontrol on/off langsung dari kartu.

### 5.2 Status pill

Reuse `.label` / `.badge` + tint background:
```
Aktif          → bg #effae4  text #93dd56 (atau #1a9c4a untuk kontras teks lebih baik)
Nonaktif       → bg #f3f3f4  text #676a6c
Perlu migrasi  → bg #fef7f0  text #ffa726
Habis/Terlampaui → bg #fff2f4  text #ea5395
```

### 5.3 Sidebar mini-card (Profil & Organisasi)

Ganti dari `.ibox` selebar halaman jadi card ramping (max-width 100% dari kolom 4/12), padding lebih kecil (`.ibox-content` → 15px, bukan 20px), format label-value vertikal rapat (label 10px uppercase muted, value 13px langsung di bawahnya tanpa gap besar) — bukan grid 2 kolom lebar seperti sekarang yang menyisakan whitespace kosong di kanan.

### 5.4 Header

Breadcrumb (`.breadcrumb`, sudah ada style-nya), site chip tetap pakai `.btn-white` seperti sekarang, tambahkan teks kecil `.text-muted` di kanan bawah chip: `Tersinkron {waktu relatif} · ` + link `Refresh` (`.btn-link`, warna primary saat hover).

---

## 6. Prompt siap-paste untuk Google Stitch

```
Redesign a SaaS admin settings page called "Benefit & Kuota Voice of Customer" inside an existing product called OneBox.

Layout: two-column dashboard, left column ~66% width holds a section titled
"Entitlements & Kuota" as a responsive 2-column grid of feature cards, right
column ~33% width is a narrow sidebar with two compact read-only info cards
("Profil Pengguna" and "Informasi Organisasi"). Stack sidebar below main
column on narrow screens.

Header: breadcrumb "Pengaturan / Voice of Customer / Benefit & Kuota", page
title "Benefit & Kuota Voice of Customer", muted subtitle "Hak akses fitur
VoC dan sisa kuota pemakaiannya untuk site ini.", a pill chip top-right
showing the active workspace name "Onebox Development", and small muted
text below it "Tersinkron 3 menit lalu · Refresh".

Each entitlement card contains, top to bottom: a small circular icon badge
tinted with the card's status color; a bold 14px title; a small monospace
pill next to the title showing a benefit code like "VOC_REVIEW"; a status
pill top-right of the card reading "Aktif" / "Nonaktif" / "Perlu migrasi";
one line of muted description text; a horizontal usage progress bar with a
caption below it like "348 / 5.000 review · 7% terpakai"; and a bottom-row
contextual action button — teal outline button "+ Tambah kuota" for healthy
cards, solid orange button "Jalankan migrasi" for cards needing migration
(with a 3px orange left border accent on the whole card), solid pink/magenta
button "Naikkan kuota" for cards that are exhausted or over quota (with a
3px pink left border accent). Include one binary toggle-style card without a
progress bar, just a status line and an on/off switch.

Show 5 entitlement cards in the grid: "Kuota review per bulan" (healthy,
teal progress bar at 7%), "Kuota crawl per hari" (needs migration state,
orange accent, no progress bar, message "Belum terdaftar di katalog
Benefit — migrasi belum dijalankan"), "Review dianalisis AI" (exhausted,
pink progress bar at 100%, caption "110 / 110 review · Habis"), "Jadwal
crawl aktif" (over quota, pink progress bar capped at 100% width, caption
"3 / 2 jadwal · Melebihi kuota"), "Pelacakan kompetitor" (active binary
toggle, no progress bar, caption "Aktif untuk site ini.").

Sidebar card 1 "Profil Pengguna": compact label/value rows for Nama
Lengkap, Alamat Email, Telepon, Mobile, Login Terakhir — tight vertical
spacing, no wasted whitespace.
Sidebar card 2 "Informasi Organisasi": Nama Perusahaan, Domain, Tipe Site,
Status Site (as a small active/green dot + label), Deskripsi.

Color palette (use exactly these hex values, no new colors):
primary/teal #00bcd4 (primary buttons, healthy progress bar, active icon
accents), success/green #93dd56 (active status pill text), warning/orange
#ffa726 (near-limit progress bar, migration-needed accent and button),
danger/magenta #ea5395 (exhausted/over-quota progress bar, accent and
button), muted text #676a6c, borders #e7eaec, card surface #ffffff, page
background #f3f3f4, soft tint backgrounds for status pills: #e3f4fc
(primary tint), #effae4 (success tint), #fef7f0 (warning tint), #fff2f4
(danger tint).

Typography: Open Sans, sans-serif. Small uppercase muted micro-labels
above section titles (e.g. "ENTITLEMENTS", "USER PROFILE") like an admin
dashboard convention. Card titles bold 14px, body text 12-13px, muted
secondary text lighter gray.

Visual style: flat, sharp corners (3px border radius on buttons and pills,
not rounded cards), thin 1px borders instead of heavy shadows, dense
information-first admin dashboard aesthetic — not a consumer marketing
page. Subtle drop shadow only on the entitlement cards in the main grid,
no shadow on sidebar cards.
```

---

## 7. Catatan implementasi (reuse dari `style.css`, tidak perlu class baru)

| Kebutuhan UI | Class existing yang bisa dipakai langsung |
|---|---|
| Card container | `.ibox`, `.ibox-title`, `.ibox-content` |
| Progress bar 3-warna | `.progress`, `.progress-bar`, `.progress-bar-warning`, `.progress-bar-danger`, `.progress-small` |
| Status pill tint | `.light-primary`, `.light-success`, `.light-warning`, `.light-danger` |
| Pill kode benefit monospace | `.simple_tag` |
| Border-left accent per state | pola dari `.agile-list li.warning-element` / `.danger-element` / `.success-element` (border-left 3px) |
| Tombol aksi kontekstual | `.btn-primary.btn-outline`, `.btn-warning`, `.btn-danger` (semua sudah ada, tinggal size `.btn-sm`) |
| Toggle biner | `.onoffswitch.enable` (sudah ada varian "Enabled"/"Disabled" custom di CSS ini) |
| Shadow kartu utama | `.shadow` |
| Breadcrumb | `.breadcrumb` |

Yang **perlu ditambah** (belum ada di `style.css`):
- Varian ukuran progress bar khusus untuk card ini (~8px height, di antara `.progress` default dan `.progress-small`).
- Border-left accent generik untuk `.ibox` (saat ini pola border-left cuma didefinisikan untuk `.agile-list li`, belum untuk `.ibox`) — cukup tambah 1 utility class `.ibox.accent-warning { border-left: 3px solid #ffa726; }` dst.
