# Firecrawl Setup dan Analysis Guide

Target awal: PT Swakarya Insan Mandiri / SIMGROUP.
Website utama: https://sim.co.id/

Tujuan: pakai Firecrawl sebagai layer public web intelligence untuk discovery halaman, scrape markdown/JSON, crawl website official, dan bahan analisis industri. Ini bukan pengganti Google Maps review crawler yang sudah ada.

## 1. Script Biasa vs Firecrawl

Jawaban pendek: untuk eksplorasi industri baru, pakai Firecrawl dulu. Setelah field dan halaman penting stabil, baru buat Python extractor khusus.

| Kebutuhan | Python script biasa | Firecrawl |
| --- | --- | --- |
| HTML sederhana | Bagus | Bisa, tapi overkill |
| Banyak halaman/domain | Perlu discovery manual | Bagus dengan map/crawl |
| JS-heavy | Perlu Selenium/Playwright | Lebih praktis |
| Output LLM-ready | Perlu cleaning manual | Markdown/JSON bawaan |
| Structured extraction | Manual parsing | Bisa schema/prompt |
| Biaya | Compute sendiri | Credit/API limit |

Rekomendasi: Firecrawl untuk discovery dan analisis awal, Python script biasa untuk extractor production yang field-nya sudah stabil.
Jangan pakai Firecrawl atau script biasa untuk bypass login, CAPTCHA, rate limit, access control, atau data tanpa izin.

## 2. Target Data PT Swakarya Insan Mandiri

Dari website publik `https://sim.co.id/`, target awal yang masuk akal:
- Profil perusahaan dan positioning SIMGROUP.
- Layanan: employee supply, collection, verification, sales process, office cleaning.
- Jaringan/cabang, klien publik, artikel, karier, kontak, dan sosial media publik.
- Brand signals: logo, screenshot, warna, tone konten, dan metadata halaman.

Jangan targetkan tanpa approval: data pribadi pelamar, data karyawan individual, konten LinkedIn login-only, Google UI scraping agresif, halaman private/admin, atau konten yang dilarang robots/TOS.

## 3. Setup Dependency

Dependency sudah ditambahkan ke requirements.txt.
Package: firecrawl-py versi 2.x.
Install dari root project: python -m venv venv, activate venv, lalu pip install -r requirements.txt.
Kalau venv sudah aktif, cukup jalankan pip install firecrawl-py.

## 4. Setup API Key
Untuk workflow serius, pakai API key. Simpan di .env sebagai FIRECRAWL_API_KEY=fc-YOUR_API_KEY.
PowerShell sementara: set environment variable FIRECRAWL_API_KEY sebelum menjalankan script.
Mulai dengan limit kecil seperti 10 sampai 25 halaman karena crawl memakai credit per halaman.

## 5. Cara Pakai untuk PT SIM
Urutan yang disarankan: search, map, scrape satu halaman, crawl official site, structured extraction, lalu manual analysis.
Search query awal: PT Swakarya Insan Mandiri OR SIMGROUP outsourcing.
Map target: https://sim.co.id/ dengan limit 100 untuk menemukan URL tentang, layanan, jaringan, klien, karier, artikel, dan kontak.
Scrape smoke test: ambil https://sim.co.id/ dengan format markdown dan links, only_main_content true.
Crawl awal: url https://sim.co.id/, limit 25, formats markdown dan links, max_age 600000, timeout sekitar 180 detik.

## 6. Output Eksperimen
Simpan hasil awal ke exports/firecrawl/pt-swakarya-insan-mandiri/.
File minimum: search_results.json, map_links.json, crawl_pages.json, company_profile.json, analysis.md.

## 7. Cara Analyze
Validasi source_url, kelompokkan halaman, extract company facts, extract industry signals, tandai missing data, lalu tentukan next action.
Company facts: company_name, brand_name, industry, summary, services, clients_public, network_locations, career_links, contact_channels, source_url, scraped_at.
Industry signals: outsourcing, BPO, contact center, collection, verification, sales process, cleaning service, employee supply.

## 8. Integrasi ke Project Nanti
Struktur yang rapi: app/integrations/firecrawl_client.py, app/services/industry_crawl_service.py, app/prompts/industry_profile_extraction_prompt.md.
Jangan campur dengan tabel reviews. Buat domain baru seperti industry_targets, industry_pages, industry_profiles, dan industry_crawl_logs.

## 9. Rekomendasi Final
Untuk PT Swakarya Insan Mandiri: pakai Firecrawl untuk search, map, crawl official site, dan structured profile extraction.
Simpan output ke exports/firecrawl/pt-swakarya-insan-mandiri/, review manual, lalu baru putuskan apakah perlu extractor Python permanen.
Dengan flow ini, crawler naik level dari review intelligence menjadi company/industry intelligence tanpa memaksakan scraping UI yang riskan.

## 10. Endpoint Firecrawl yang Dipakai
Search: discovery sumber publik dari query. Scrape: ambil satu URL ke markdown, links, screenshot, atau JSON. Map: temukan URL dalam satu domain. Crawl: ambil banyak halaman dari satu domain dengan limit dan scrape options.

## 11. Referensi
Firecrawl Python SDK: https://docs.firecrawl.dev/sdks/python
Firecrawl Scrape docs: https://docs.firecrawl.dev/features/scrape
Firecrawl Search docs: https://docs.firecrawl.dev/features/search
Firecrawl Crawl docs: https://docs.firecrawl.dev/features/crawl
