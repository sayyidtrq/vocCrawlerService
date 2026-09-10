# VoC Crawler System - Pull Flow, Environment, Risk, and Deployment

Dokumen ini menjelaskan flow pull data dari Crawler System ke OneBox, env, risiko, mitigasi, dan deployment backend.

## 1. Arsitektur Ringkas

Pola MVP: OneBox pull data dari Crawler System via REST API. Crawler System adalah data provider. OneBox adalah consumer yang melakukan ingestion ke Contact, Ticket, Message, dan MessageContent.

Flow utama:
1. Source eksternal menghasilkan review.
2. Worker mengambil review sesuai REVIEW_SOURCE_MODE, lalu menyimpan review ke VoC DB dengan review_hash.
3. AI Analysis mengisi sentiment, urgency, issue_category, summary, recommended_action, dan keywords.
4. OneBox Task memanggil API Crawler System dan melakukan ingestion ke Contact, Ticket, Message, dan MessageContent.

## 2. Endpoint Pull

Target endpoint: GET {VOC_API_BASE_URL}/api/integration/v1/reviews
Header wajib: Authorization Bearer {VOC_SERVICE_TOKEN}, Accept application/json, dan X-Request-ID.
Parameter: limit untuk ukuran page, cursor untuk lanjut page, updated_since untuk delta sync awal, dan location_id untuk pull per lokasi.
Catatan saat ini: endpoint integration v1 sudah ada, tetapi service token auth masih placeholder sampai VOC-CS-03 selesai. Production wajib memakai service token scoped company dengan scope reviews:read.

## 3. Cursor, Dedup, dan Mapping
Jika has_more true, OneBox lanjut memakai next_cursor. Jika has_more false, OneBox menyimpan checkpoint_cursor untuk siklus berikutnya.
checkpoint_cursor hanya boleh disimpan setelah seluruh batch sukses di-ingest. Jika batch gagal, ulangi request yang sama.
Dedup wajib memakai SiteId plus review_hash atau SiteId plus external_review_id agar rerun task tidak membuat Ticket ganda.
Mapping: location_id ke Connection.TargetId atau mapping lokasi, reviewer_name ke Contact, review ke Ticket, review_text ke MessageContent, dan review_hash ke Message.RemoteId.

## 4. Environment yang Perlu Disiapkan
Root .env.example sudah diperbarui untuk Crawler System. Production atau staging wajib mengganti APP_ENV, DATABASE_URL, JWT_SECRET_KEY, INTEGRATION_CURSOR_SECRET, REVIEW_SOURCE_MODE, dan LOCAL_LLM_BASE_URL.
CORS_ALLOWED_ORIGINS hanya penting jika browser OneBox FE memanggil Crawler System langsung. Backend OneBox ke Crawler System tidak terkena CORS.
Config konseptual OneBox: VOC_API_ENABLED=false, VOC_API_BASE_URL=http://10.13.13.90:8000, VOC_API_TOKEN=secret-per-env, VOC_API_TIMEOUT_SECONDS=30, VOC_API_PAGE_SIZE=100, VOC_API_LOCATION_ID=1039.

## 5. Risiko dan Mitigasi
- Selenium selector berubah: mitigasi dengan selector terpusat, screenshot atau HTML debug, dan smoke test rutin.
- Login Google atau browser profile expired: mitigasi dengan fallback Google Places, Google Business Profile, atau third party source.
- Rate limit atau blocking source: mitigasi dengan throttle, retry backoff, limit per lokasi, dan jadwal fetch bertahap.
- Review duplikat: mitigasi dengan review_hash di Crawler System dan SiteId plus RemoteId di OneBox.
- Cursor disimpan terlalu cepat: mitigasi dengan menyimpan checkpoint_cursor hanya setelah batch sukses penuh.
- Network WireGuard tidak reachable: mitigasi dengan curl health dari host dan container OneBox, lalu cek route, firewall, dan port 8000.
- Service auth belum final: mitigasi dengan menyelesaikan VOC-CS-03 sebelum production dan memakai service token scoped company.
- Secret bocor: mitigasi dengan tidak commit .env, masking log, dan secret berbeda per environment.

## 6. Deployment Backend
Deploy dari source: git fetch origin, git switch branch-deploy, git pull --ff-only, copy .env.example ke .env, isi .env, lalu docker compose up -d --build.
Deploy dari image registry: docker compose pull api, lalu docker compose up -d --force-recreate api.
Health check: curl http://127.0.0.1:8000/api/health, curl http://server-ip:8000/api/health, dan curl http://server-ip:8000/api/docs.
Test dari OneBox container: curl --connect-timeout 5 http://voc-api-host:8000/api/health dan curl --connect-timeout 5 http://voc-api-host:8000/api/integration/v1/reviews?limit=1.
Interpretasi: 200 berarti siap, 401 atau 403 berarti token bermasalah, 503 SERVICE_AUTH_NOT_READY berarti auth belum aktif, 404 berarti path atau image salah, timeout berarti network/firewall/VPN.

## 7. Smoke Test End-to-End
Checklist: Crawler System healthy, database reachable, minimal satu Location punya review, review_hash terisi, OneBox container bisa curl API, task menerima response, review menjadi Ticket, Message.RemoteId terisi, rerun tidak membuat duplikat, dan dashboard menampilkan data.

## 8. Kesimpulan
Crawler System adalah data provider. OneBox adalah consumer. Fokus integrasi adalah network, service auth, cursor, dedup, mapping Ticket, dan observability. CORS hanya relevan jika browser memanggil Crawler System langsung.
