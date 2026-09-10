# Voice of Customer System untuk Rumah Sakit

> Dokumen high-level untuk stakeholder dan CEO  
> Status: Draft fondasi kebutuhan bisnis  
> Tanggal: 23 Juli 2026

## 1. Tujuan Dokumen

Dokumen ini menjelaskan mengapa Voice of Customer (VoC) System dibutuhkan oleh rumah sakit, siapa pengguna utamanya, dan keputusan apa yang dibantu oleh sistem. Dokumen ini menjadi fondasi sebelum kebutuhan key screen, detail fitur, dan user interface diturunkan.

## 2. Ringkasan Eksekutif

Voice of Customer System membantu rumah sakit mendengar, memahami, dan menindaklanjuti pengalaman pasien yang muncul di kanal publik seperti Google Reviews. Sistem mengubah review yang tersebar dan tidak terstruktur menjadi informasi yang dapat dipantau: lokasi atau cabang yang terdampak, topik keluhan, sentiment, tingkat urgensi, tren, dan status tindak lanjut. Hasilnya tidak berhenti sebagai laporan reputasi, tetapi masuk ke workflow OneBox sebagai Ticket agar isu dapat memiliki pemilik, status, prioritas, dan riwayat penyelesaian.

Untuk manajemen, sistem ini berfungsi sebagai **early-warning dan decision-support system**. Yayasan atau direksi dapat melihat pola lintas cabang; direktur atau kepala cabang dapat mengetahui masalah yang membutuhkan perhatian; Komite Mutu, Keselamatan Pasien, atau Customer Care dapat memvalidasi dan mengelola keluhan; manager unit dapat menindaklanjuti isu yang menjadi tanggung jawabnya; dan IT memastikan akses, integrasi, serta ketersediaan sistem berjalan dengan baik. Sistem ini tidak menggantikan rekam medis, pelaporan insiden keselamatan pasien, investigasi klinis, atau kanal pengaduan resmi.

## 3. Masalah Bisnis Rumah Sakit

Rumah sakit beroperasi melalui banyak cabang, unit, dan titik layanan: pendaftaran, rawat jalan, IGD, rawat inap, laboratorium, radiologi, farmasi, kasir, dan layanan penunjang lain. Pengalaman pasien dapat terbentuk dari seluruh rangkaian interaksi tersebut, sementara review publik biasanya hanya berupa teks singkat, rating, dan konteks yang tidak seragam.

Tanpa sistem terpusat, manajemen berisiko:

- terlambat mengetahui keluhan yang berulang atau memburuk;
- sulit membedakan isu satu kali dengan pola masalah lintas cabang;
- tidak memiliki alur yang jelas dari review menuju pemilik tindakan;
- mengandalkan rekap manual yang lambat dan tidak konsisten;
- kehilangan histori apakah sebuah keluhan sudah ditindaklanjuti;
- melihat rating sebagai angka reputasi tanpa memahami penyebab operasionalnya.

## 4. Prinsip Bisnis Sistem

1. **Patient experience sebagai sinyal mutu** - review membantu menunjukkan bagaimana layanan dirasakan pasien, bukan hanya bagaimana proses dirancang secara internal.
2. **Dari insight ke action** - temuan penting harus dapat berubah menjadi Ticket yang memiliki status, prioritas, pemilik, dan penyelesaian.
3. **Satu pandangan lintas cabang** - manajemen dapat melihat konsolidasi, sementara unit hanya melihat data sesuai kewenangannya.
4. **Human-in-the-loop** - AI membantu merangkum dan mengelompokkan, tetapi keputusan mutu, keselamatan, dan respons tetap berada pada manusia yang berwenang.
5. **Data publik bukan fakta klinis** - review tidak boleh dianggap sebagai diagnosis, bukti insiden, atau pengganti investigasi resmi.

## 5. Aktor yang Disarankan

| Aktor | Posisi yang sesuai di rumah sakit | Peran utama dalam VoC |
|---|---|---|
| Yayasan / Pemilik / Dewan Pengawas | Pengarah strategis jaringan rumah sakit | Melihat kesehatan reputasi dan mutu lintas cabang serta memastikan akuntabilitas manajemen |
| Direksi / CEO Rumah Sakit | Pengambil keputusan tingkat korporat | Menetapkan prioritas perbaikan dan mengevaluasi kinerja jaringan atau rumah sakit |
| Direktur Rumah Sakit / Kepala Cabang | Pemilik kinerja satu rumah sakit atau cabang | Memantau kondisi cabang dan memastikan isu penting ditangani |
| Komite Mutu dan Keselamatan Pasien / Patient Experience / Customer Care | Pemilik proses mutu dan pengaduan | Memvalidasi, mengklasifikasikan, memprioritaskan, dan memonitor tindak lanjut |
| Manager Operasional / Manager Unit | Pemilik proses layanan tertentu | Menindaklanjuti isu yang berkaitan dengan unit dan mengoordinasikan perbaikan |
| PIC Unit / Supervisor / Kontributor Cabang | Pelaksana perbaikan di lapangan | Memberikan respons, catatan tindakan, bukti penyelesaian, dan update status |
| Staf IT / System Administrator | Pengelola platform dan integrasi | Mengatur akses, konfigurasi, konektivitas, scheduler, dan monitoring teknis |

### Perubahan dari daftar awal

- **Yayasan pendiri rumah sakit** diperluas menjadi **Yayasan / Pemilik / Dewan Pengawas**, karena aktor ini berfokus pada pengawasan strategis, bukan operasional harian.
- **Kepala cabang rumah sakit** lebih tepat ditulis **Direktur Rumah Sakit / Kepala Cabang**, bergantung pada struktur organisasi klien.
- **Manager cabang** diperjelas menjadi **Manager Operasional / Manager Unit**, karena tindakan biasanya dimiliki oleh unit tertentu, bukan oleh jabatan cabang secara abstrak.
- **Komite Mutu dan Keselamatan Pasien / Patient Experience / Customer Care** ditambahkan sebagai aktor utama. Tanpa aktor ini, sistem hanya menjadi dashboard dan tidak memiliki pemilik proses tindak lanjut.
- **Staf IT** tetap diperlukan, tetapi posisinya sebagai administrator dan penjaga layanan, bukan pemilik keputusan kualitas pelayanan.

## 6. User Story per Aktor

### 6.1 Yayasan / Pemilik / Dewan Pengawas

**Tujuan:** memperoleh pandangan strategis tentang reputasi, konsistensi mutu, dan isu yang berulang di seluruh jaringan rumah sakit.

- Sebagai **pemilik rumah sakit**, saya ingin melihat tren rating dan sentiment per cabang agar dapat mengetahui cabang mana yang membutuhkan perhatian strategis.
- Sebagai **pemilik rumah sakit**, saya ingin melihat isu yang berulang di banyak cabang agar dapat membedakan masalah lokal dari masalah sistemik.
- Sebagai **pemilik rumah sakit**, saya ingin melihat status penyelesaian isu prioritas agar dapat memastikan laporan manajemen diikuti tindakan nyata.
- Sebagai **pemilik rumah sakit**, saya ingin menerima ringkasan risiko reputasi dan patient experience tanpa membaca seluruh review satu per satu agar waktu pengambilan keputusan lebih efisien.

**Bantuan sistem:** dashboard konsolidasi, perbandingan cabang, tren periode, top issue, review kritis, dan ringkasan status tindak lanjut.

**Keputusan yang didukung:** prioritas investasi, evaluasi kinerja cabang, standardisasi layanan, dan eskalasi isu lintas organisasi.

### 6.2 Direksi / CEO Rumah Sakit

**Tujuan:** menghubungkan suara pasien dengan target mutu dan agenda perbaikan rumah sakit.

- Sebagai **direktur rumah sakit**, saya ingin melihat perubahan sentiment dan rating dari waktu ke waktu agar dapat menilai apakah program perbaikan memberi dampak.
- Sebagai **direktur rumah sakit**, saya ingin melihat review dengan urgensi tinggi dan kategori patient-safety signal agar isu sensitif tidak tertutup oleh volume review biasa.
- Sebagai **direktur rumah sakit**, saya ingin melihat cabang atau unit dengan tren memburuk agar dapat meminta corrective action lebih awal.
- Sebagai **direktur rumah sakit**, saya ingin melihat rasio Ticket yang terbuka, sedang ditangani, dan selesai agar akuntabilitas tindak lanjut dapat diukur.

**Bantuan sistem:** executive dashboard, critical issue queue, trend comparison, KPI penyelesaian, dan laporan berkala.

**Keputusan yang didukung:** penetapan fokus perbaikan, target layanan, eskalasi, dan review kinerja manajemen.

### 6.3 Direktur Rumah Sakit / Kepala Cabang

**Tujuan:** memahami kondisi cabang secara spesifik dan memastikan isu pasien diterjemahkan menjadi tindakan operasional.

- Sebagai **kepala cabang**, saya ingin melihat ringkasan review cabang saya agar dapat mengetahui kondisi patient experience hari ini.
- Sebagai **kepala cabang**, saya ingin memfilter review berdasarkan unit, kategori, sentiment, rating, dan urgensi agar fokus pemeriksaan dapat disesuaikan.
- Sebagai **kepala cabang**, saya ingin melihat Ticket yang melewati target penyelesaian agar dapat melakukan eskalasi kepada manager terkait.
- Sebagai **kepala cabang**, saya ingin membandingkan tren cabang dengan periode sebelumnya agar dapat mengetahui apakah masalah membaik atau memburuk.

**Bantuan sistem:** dashboard cabang, review list, filter, overdue view, dan branch trend.

**Keputusan yang didukung:** pembagian fokus operasional, eskalasi, coaching, dan evaluasi corrective action.

### 6.4 Komite Mutu dan Keselamatan Pasien / Patient Experience / Customer Care

**Tujuan:** menjadi pemilik proses dari penerimaan sinyal sampai validasi, klasifikasi, tindak lanjut, dan pembelajaran mutu.

- Sebagai **tim mutu atau Customer Care**, saya ingin melihat review baru yang belum ditinjau agar tidak ada keluhan penting yang terlewat.
- Sebagai **tim mutu**, saya ingin memvalidasi hasil sentiment, kategori, dan urgency agar keputusan tidak hanya bergantung pada AI.
- Sebagai **tim mutu**, saya ingin mengubah review menjadi Ticket dan menetapkan owner agar setiap isu memiliki penanggung jawab.
- Sebagai **tim mutu**, saya ingin melihat sumber, waktu, lokasi, dan konteks review agar investigasi awal memiliki dasar yang jelas.
- Sebagai **tim mutu**, saya ingin menandai isu yang berpotensi terkait keselamatan pasien atau risiko reputasi agar diteruskan ke prosedur resmi yang sesuai.
- Sebagai **tim Customer Care**, saya ingin memonitor SLA respons dan penyelesaian agar keluhan ditangani sesuai tingkat risikonya.
- Sebagai **tim mutu**, saya ingin melihat tema berulang dan rekomendasi tindakan agar temuan review dapat menjadi bahan improvement project.

**Bantuan sistem:** review inbox, validation state, triage, ticketing, assignment, SLA, escalation, audit trail, dan recurring issue analysis.

**Keputusan yang didukung:** klasifikasi risiko, jalur eskalasi, corrective action, pembelajaran mutu, dan pelaporan komite.

> Catatan penting: sistem VoC hanya memberikan sinyal awal. Jika review mengindikasikan keselamatan pasien, dugaan malpraktik, atau kejadian klinis, kasus harus masuk ke kanal investigasi resmi rumah sakit dan tidak diselesaikan hanya dengan mengubah status Ticket VoC.

### 6.5 Manager Operasional / Manager Unit

**Tujuan:** mengubah keluhan menjadi perbaikan proses di area yang menjadi tanggung jawabnya.

- Sebagai **manager unit**, saya ingin melihat Ticket yang ditugaskan ke unit saya agar dapat mengatur pekerjaan perbaikan.
- Sebagai **manager unit**, saya ingin melihat bukti dan konteks review agar dapat membedakan masalah komunikasi, waktu tunggu, fasilitas, administrasi, atau layanan klinis.
- Sebagai **manager unit**, saya ingin menambahkan catatan tindakan dan target penyelesaian agar progress dapat dipantau.
- Sebagai **manager unit**, saya ingin melihat pola keluhan per periode agar dapat menentukan perubahan proses, kebutuhan pelatihan, atau kebutuhan sumber daya.

**Bantuan sistem:** work queue unit, detail Ticket, assignment, due date, action note, status transition, dan trend kategori.

**Keputusan yang didukung:** corrective action unit, coaching staf, perubahan alur layanan, dan permintaan dukungan sumber daya.

### 6.6 PIC Unit / Supervisor / Kontributor Cabang

**Tujuan:** menyelesaikan tindakan yang sudah ditugaskan dengan konteks yang cukup dan akses yang terbatas.

- Sebagai **PIC unit**, saya ingin melihat hanya Ticket yang ditugaskan kepada saya atau unit saya agar pekerjaan tetap fokus.
- Sebagai **PIC unit**, saya ingin memperbarui status dan menambahkan catatan tindakan agar manager dapat melihat perkembangan terbaru.
- Sebagai **PIC unit**, saya ingin mengetahui prioritas dan batas waktu Ticket agar isu penting ditangani terlebih dahulu.
- Sebagai **PIC unit**, saya ingin melihat sumber review dan ringkasan yang relevan tanpa membuka data pasien yang tidak diperlukan.

**Bantuan sistem:** personal/unit worklist, detail terbatas, status update, internal note, dan notifikasi/escalation.

**Keputusan yang didukung:** pelaksanaan tindakan lapangan dan pelaporan penyelesaian.

### 6.7 Staf IT / System Administrator

**Tujuan:** menjaga agar platform aman, terhubung, dan tersedia bagi pengguna bisnis.

- Sebagai **administrator IT**, saya ingin mengatur role dan permission agar setiap pengguna hanya melihat data sesuai kewenangannya.
- Sebagai **administrator IT**, saya ingin memantau koneksi OneBox-Crawler System, scheduler, job, dan error agar gangguan dapat ditangani sebelum menghambat operasi.
- Sebagai **administrator IT**, saya ingin mengatur source, lokasi, service credential, dan parameter integrasi tanpa mengubah isi Ticket secara manual.
- Sebagai **administrator IT**, saya ingin melihat audit log dan histori sinkronisasi agar masalah data dapat ditelusuri.

**Bantuan sistem:** role management, integration health, scheduler history, service authentication, log, retry, dan configuration screen.

**Keputusan yang didukung:** akses, keamanan, availability, integrasi, dan troubleshooting.

## 7. Ringkasan Nilai per Aktor

| Aktor | Pertanyaan utama | Jawaban yang diberikan sistem |
|---|---|---|
| Yayasan / Pemilik | Apakah mutu dan reputasi jaringan membaik? | Tren lintas cabang, top issue, dan status isu strategis |
| Direksi / CEO | Apa yang paling perlu diprioritaskan sekarang? | Critical review, urgency, dampak, dan cabang/unit terdampak |
| Kepala Cabang | Apa masalah utama di cabang saya? | Ringkasan cabang, filter review, overdue Ticket, dan tren |
| Komite Mutu / Customer Care | Bagaimana keluhan dipilah dan ditindaklanjuti? | Triage, validasi, Ticket, SLA, eskalasi, dan audit trail |
| Manager Unit | Apa yang harus diperbaiki oleh unit saya? | Work queue, konteks review, action note, dan recurring issue |
| PIC Unit | Tindakan apa yang harus saya selesaikan? | Ticket ter-assign, prioritas, due date, dan status update |
| IT | Apakah sistem aman dan berjalan? | Health integrasi, akses, job history, retry, dan audit log |

## 8. Batasan dan Guardrail untuk Rumah Sakit

- Review publik merupakan **sinyal pengalaman**, bukan sampel ilmiah yang mewakili seluruh pasien.
- Review publik tidak boleh dipakai untuk mendiagnosis pasien, menilai kondisi klinis individu, atau menggantikan rekam medis.
- Informasi identitas pasien atau data kesehatan sensitif tidak boleh ditambahkan ke Ticket kecuali memang diperlukan, memiliki dasar kewenangan, dan mengikuti kebijakan privasi rumah sakit.
- AI harus menampilkan hasil sebagai bantuan analisis; pengguna berwenang tetap memvalidasi kategori dan urgensi.
- Dugaan patient safety, fraud, kekerasan, atau risiko hukum harus dieskalasikan ke proses resmi yang sudah dimiliki rumah sakit.
- Akses data wajib dibatasi berdasarkan company, rumah sakit/cabang, unit, role, dan kebutuhan kerja.

## 9. Indikator Keberhasilan Tingkat CEO

Indikator awal yang relevan untuk menilai manfaat sistem:

1. **Coverage:** persentase cabang dan lokasi aktif yang berhasil dimonitor.
2. **Freshness:** waktu antara review muncul dan review tersedia di OneBox.
3. **Triage speed:** waktu dari review masuk sampai divalidasi dan diprioritaskan.
4. **Response performance:** waktu tanggap dan penyelesaian Ticket berdasarkan tingkat urgensi.
5. **Closure rate:** persentase Ticket yang selesai dibandingkan Ticket yang masuk.
6. **Recurring issue reduction:** penurunan isu berulang setelah corrective action.
7. **Trend improvement:** perubahan rating, sentiment, dan kategori masalah dari waktu ke waktu.
8. **Accountability:** persentase Ticket yang memiliki owner, due date, dan catatan tindakan.

Indikator tersebut harus dibaca bersama konteks volume review, perubahan sumber, dan program mutu lain; tidak boleh digunakan sebagai satu-satunya ukuran kualitas klinis rumah sakit.

## 10. Implikasi terhadap Key Screen

Fondasi aktor di atas menyarankan enam kelompok screen utama:

1. **Executive Overview** - untuk yayasan, direksi, dan CEO.
2. **Branch Overview** - untuk direktur rumah sakit atau kepala cabang.
3. **Review Triage / VoC Inbox** - untuk Komite Mutu, Customer Care, dan patient experience.
4. **Ticket Worklist dan Ticket Detail** - untuk manager unit dan PIC.
5. **Quality Insight dan Trend** - untuk manajemen dan Komite Mutu.
6. **Administration dan Integration Health** - untuk IT/System Administrator.

Detail screen sebaiknya diturunkan dari keputusan yang harus dibuat aktor, bukan dari struktur tabel database. Satu screen dapat dipakai bersama dengan perbedaan filter, scope, dan permission berdasarkan role.

## 11. Referensi

- [WHO - Quality of care](https://www.who.int/health-topics/quality-of-care): layanan kesehatan bermutu perlu people-centred, timely, safe, effective, integrated, dan terus diukur dengan data yang akurat serta actionable.
- [WHO - Patient-reported experiences in primary care](https://www.who.int/publications/i/item/9789240112674): pengalaman pasien penting untuk perencanaan, delivery, dan quality improvement layanan terintegrasi.
- [AHRQ - Improving Patient Experience](https://www.ahrq.gov/cahps/quality-improvement/index.html): data pengalaman pasien membantu organisasi menemukan kekuatan/kelemahan, menentukan area perbaikan, dan melacak kemajuan.
- [AHRQ - About CAHPS](https://www.ahrq.gov/cahps/about-cahps/index.html): patient experience mencakup interaksi pasien dengan penyedia layanan, dokter, perawat, staf, dan fasilitas kesehatan.
- [NHS England - Giving your feedback](https://www.england.nhs.uk/get-involved/get-involved/how/feedback/): feedback pasien digunakan untuk membantu organisasi kesehatan melakukan perbaikan layanan.
- [Kementerian Kesehatan RI - Indikator Nasional Mutu Rumah Sakit](https://keslan.kemkes.go.id/inm/index/15200): indikator mutu rumah sakit mencakup kecepatan tanggap komplain dan kepuasan pasien.
- [Permenkes RI terkait indikator mutu pelayanan kesehatan](https://jdih.kemkes.go.id/common/dokumen/2022permenkes030.pdf): kecepatan tanggap komplain mencakup identifikasi, penetapan grading risiko, analisis, dan tindak lanjut.

## 12. Keputusan Stakeholder yang Perlu Dikonfirmasi

- Siapa pemilik proses resmi untuk memvalidasi dan menindaklanjuti review: Komite Mutu, Customer Care, Patient Experience, atau kombinasi beberapa unit?
- Apakah sistem hanya digunakan untuk review publik atau juga akan menerima survei internal dan kanal pengaduan resmi?
- Apa definisi dan SLA untuk review kritis, risiko reputasi, dan patient-safety signal?
- Apakah CEO membutuhkan dashboard jaringan, dashboard per rumah sakit, atau keduanya?
- Unit mana yang boleh menerima Ticket secara langsung dan siapa yang berwenang melakukan eskalasi?

