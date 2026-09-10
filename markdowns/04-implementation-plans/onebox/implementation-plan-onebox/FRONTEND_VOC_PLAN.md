# Frontend Implementation Plan - Voice of Customer (Onebox)

## 1. Pendahuluan
Dokumen ini berisi rencana implementasi *Front-End* untuk fitur Voice of Customer (VoC) di sistem Onebox, berdasarkan arahan mentor. Tampilan VoC akan mengadaptasi desain (halaman-halaman) dari purwarupa `herminaCrawler` sebelumnya, namun disesuaikan secara harmonis dengan ekosistem, komponen, dan *layout* bawaan Onebox.

## 2. Ruang Lingkup (Modul Pertama)
Sesuai dengan arahan penugasan pertama, fokus awal pengembangan adalah:
1. **Mock Dashboard:** Membangun antarmuka *dashboard* awal (statistik, bagan/chart sentimen).
2. **Modul Location & Review:** Membangun antarmuka daftar ulasan (tabel ulasan pelanggan) beserta filternya.

## 3. Aturan Eksekusi (Golden Rules)
1. **Isolasi Pengerjaan:** Semua pembuatan dan modifikasi kode HTML/Volt HANYA boleh dilakukan di dalam *sub-directory* baru: `app/views/VoiceOfCustomer/`.
2. **Tanpa Merusak Layout Utama:** DILARANG KERAS mengedit file inti *sidebar* atau *template* utama seperti `views/layouts/templates.volt` atau `views/Menu/sideMenu.volt`.
3. **Menu Dinamis:** Registrasi menu VoC ke *sidebar* Onebox akan dilakukan sepenuhnya melalui *Database* (tabel `Menu`) atau halaman *Administrator Settings*, bukan di-*hardcode* di *file layout*.
4. **Penggunaan Data Dummy:** Pada fase *mocking* ini, gunakan data *dummy* (nilai *hardcode* HTML) untuk mengisi tabel, grafik, dan kartu informasi. Tim *Back-End* akan menukar data *dummy* ini dengan variabel dinamis (misal: `{{ review.name }}`) setelah API siap.

## 4. Struktur File Target (Workspace: `onecloud`)

Semua pengerjaan di bawah ini akan dieksekusi di dalam *remote workspace* WSL (`onecloud`).

### 4.1. Views (Volt Templates)
Lokasi: `/var/www/html/onecloud/onecloud/app/views/VoiceOfCustomer/`
*   **`index.volt`**: Halaman utama / *Dashboard* dan daftar ulasan (*Location & Review*).
*   **`detail.volt`**: Halaman rincian spesifik untuk satu ulasan pelanggan (bisa berupa *pop-up* modal atau halaman terpisah).

**Sistem Extend Layout:**
Setiap file `.volt` wajib menerapkan *template inheritance* bawaan Phalcon agar otomatis mewarisi *Header*, *Sidebar*, dan *Footer* Onebox tanpa modifikasi berlebih:
```volt
{% extends "layouts/templates.volt" %}

{% block content %}
    <!-- HTML khusus Voice of Customer ditulis di sini -->
    <div class="row">
        <div class="col-lg-12">
            <h1>Halaman Voice of Customer</h1>
        </div>
    </div>
{% endblock %}
```

### 4.2. Assets Tambahan (Jika Diperlukan)
Lokasi: `/var/www/html/onecloud/onecloud/public/`
Jika komponen bawaan Onebox tidak mencukupi, penambahan akan diisolasi pada:
*   `css/voc-custom.css`: Untuk *styling* spesifik VoC.
*   `js/voc-script.js`: Untuk logika UI/DOM spesifik VoC.

### 4.3. Controller Jembatan (Bridge Controller)
Lokasi: `/var/www/html/onecloud/onecloud/app/controllers/VoiceOfCustomerController.php`
Untuk memungkinkan *Front-End Developer* melihat pratinjau hasil *mockup* secara langsung di browser tanpa menunggu penyelesaian seluruh logika *Back-End*, sebuah *Controller* dasar akan dibuat. *Controller* ini hanya berisi `indexAction()` yang bertugas merender *view* `index.volt`.

## 5. Referensi Desain
Referensi tata letak (kartu, posisi grafik, tabel ulasan) akan diambil murni dari halaman `herminaCrawler`. Namun, *class-class* CSS dan struktur HTML (seperti `div class="row"`, `col-lg-12`, format *button*, dsb) akan dikonversi menggunakan pedoman gaya (UI/UX *guideline*) yang berlaku di sistem Onebox saat ini agar terlihat menyatu (*native*).
