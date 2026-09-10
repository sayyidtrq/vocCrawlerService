# RI-04 — Library `VoiceOfCustomerSystemClient` (≤4 MD)

> Keputusan terkait: D1, D3. Pattern rujukan: `app/library/CiptalifeApi.php` [verified]

## 1. Tujuan & Definition of Done
Class client external REST di `app/library/` yang bisa `health()`, `login()`, `getReviews()` ke VoC System — dengan mode mock (fixture) dan mode live.
**Selesai kalau:** dipanggil dari task/CLI dev → return data terparse dari (a) fixture dan (b) VoC live lokal; tidak ada credential di kode; error 401/timeout tertangani.

## 2. Prasyarat & Dependency
- RI-03 selesai (base URL + service credential + fixture ada).
- **Branch git**: `git checkout develop && git pull && git checkout -b feature/DNGO19-XXXX_VoC-Integration` (nomor tiket dari Agung; JANGAN kerja di `hotfix/1.118.1`). Semua task kode berikutnya (RI-05 dst) numpang branch ini sampai ada arahan lain.

## 3. File Target
| File | Status |
|---|---|
| `onecloud/app/library/VoiceOfCustomerSystemClient.php` | [baru] |
| `onecloud/app/config/development.php` (atau config env aktif dev) | [ubah] — tambah section `voiceofcustomer` ⚠️ JANGAN di-commit (file ini dirty-local; nilai production nanti via MR terpisah yang bersih) |
| `markdowns/07-data-and-seeding/field-mapping/implementation-plan/fixtures/reviews_sample.json` | [baca-saja] — mock |
| `app/library/CiptalifeApi.php` | [baca-saja] — contekan |

## 4. Langkah Implementasi

### Step 1 — Section config (dev only)
```php
// app/config/development.php — tambah key:
'voiceofcustomer' => [
    'baseUrl'  => 'http://<host-ip>:<port>',   // hasil RI-03 langkah 3
    'username' => 'onebox-svc@internal',
    'password' => '***',
    'timeout'  => 30,
    'mock'     => false,                        // true = pakai fixture
    'mockFile' => '/path/ke/reviews_sample.json',
],
```

### Step 2 — Class client (skeleton, meniru CiptalifeApi 1:1)
```php
<?php
namespace Library;

class VoiceOfCustomerSystemClient
{
    private $baseUrl; private $username; private $password;
    private $token; private $timeout = 30;
    private bool $mock = false; private string $mockFile = '';
    protected ?\Monolog\Logger $log;

    public function __construct(array $cfg)   // terima array config, bukan hardcode
    {
        $this->log = Logger::get('VoiceOfCustomerSystem');
        $this->baseUrl  = rtrim($cfg['baseUrl'] ?? '', '/');
        $this->username = $cfg['username'] ?? '';
        $this->password = $cfg['password'] ?? '';
        $this->timeout  = (int)($cfg['timeout'] ?? 30);
        $this->mock     = (bool)($cfg['mock'] ?? false);
        $this->mockFile = $cfg['mockFile'] ?? '';
    }

    public function health(): bool { /* GET /api/health, return status==ok */ }

    public function login(): string
    {
        if ($this->token) return $this->token;
        // POST /api/auth/login, body form-urlencoded: username=...&password=...
        // [verified kontrak dari RI-03] response: {access_token, token_type}
        // simpan $this->token; throw \Exception kalau gagal; JANGAN log password
    }

    public function getReviews(array $params = []): array
    {
        if ($this->mock) return json_decode(file_get_contents($this->mockFile), true);
        $this->ensureAuthenticated();                       // pola CiptalifeApi:149
        $resp = $this->get('/api/reviews', $params);        // Authorization: Bearer
        // NOTE 401 → token expired: reset $this->token, login ulang, retry SEKALI
        return $resp;   // {items, total, page, page_size, total_pages}
    }

    private function ensureAuthenticated(): void { if (empty($this->token)) $this->login(); }

    private function get(string $path, array $q = []): array
    {
        // curl GET: timeout $this->timeout, header Bearer, http_build_query($q)
        // non-2xx → log error (tanpa credential) + throw \Exception dengan http code
    }
}
```
Detail `get()`/curl: contek implementasi method `get()` CiptalifeApi (line ±163) apa adanya — jangan improvisasi gaya baru.

### Step 3 — Smoke test via task dev sementara
Buat action kecil untuk manual test (nanti dipakai juga RI-05):
```php
// sementara boleh nebeng file task RI-05 nanti; atau php snippet via boot
$cfg = $this->config->voiceofcustomer->toArray();
$client = new \Library\VoiceOfCustomerSystemClient($cfg);
var_dump($client->health());
$r = $client->getReviews(['page'=>1,'page_size'=>5,'latest_first'=>true]);
echo count($r['items'] ?? []);
```
⚠️ Cara invoke task CLI OneBox: `[assumption]` — verifikasi dulu dengan lihat bagaimana SonarTask dijalankan (cek `supervisor.sh` / `docker-compose.scheduler.yml` / tanya tim: kemungkinan `php app/boot.php <task> <action>`). Catat command pastinya di Temuan.

## 5. Cara Verifikasi
1. Mode mock (`mock=true`): `getReviews()` return isi fixture — tanpa network.
2. Mode live: health `true`; getReviews return `items` ≥1; matikan container VoC → panggilan gagal dengan exception ter-log rapi (bukan fatal tak tertangani).
3. `grep -rn "password" app/library/VoiceOfCustomerSystemClient.php` → tidak ada nilai literal.

## 6. Risiko & Rollback
State di Swoole: **jangan** simpan token di `static` (long-running process — pelajaran dari developer_guide §Swoole). Token di property instance OK karena task CLI short-lived. Rollback: hapus file class + revert config dev.

## 7. Temuan & Deviasi (eksekusi 2026-07-14)

1. **SELESAI** — file: `app/library/VoiceOfCustomerSystemClient.php` (lolos `php -l`, smoke test mock OK).
2. **Deviasi konfigurasi (ikut D9/D6 revisi):** credential TIDAK di `development.php` — dibaca dari row `Connection` (kolom `Url`/`UserId`/`Password`, extras di `Options` JSON). Constructor: `new VoiceOfCustomerSystemClient($username, $password, $baseUrl, $extras)`.
3. **Login kontrak beda dari CiptalifeApi:** `POST /api/auth/login` pakai **x-www-form-urlencoded** (`username`, `password`) — verified dari `auth.py` (OAuth2PasswordRequestForm), bukan JSON. Response `{access_token, token_type}`.
4. **Command invoke CLI (verified):** `php app/bootstrap.php voice_of_customer_system <action> <connId>` — dijalankan **di dalam container** `dev_DNGO19-3346_webapp` (`docker exec <container> php app/bootstrap.php ...`); di host WSL tidak ada `vendor/`. Nama task WAJIB underscore (`voice_of_customer_system`) karena Phalcon camelize per-underscore → `VoiceOfCustomerSystemTask`.
5. **Mock file path harus visible dari container:** `/mnt/c/...` tidak ke-mount; `/tmp` host WSL ke-mount ke container → fixture ditaruh `/tmp/voc_reviews_sample.json` (source of truth: `markdowns/07-data-and-seeding/field-mapping/implementation-plan/fixtures/reviews_sample.json` di repo VoC, copy manual). Catatan: `/tmp` hilang saat WSL restart — copy ulang kalau perlu.
6. Fixture dibuat dari 10 review real DB VoC (semua analyzed), shape persis `ReviewListResponse` (`location`=branch_name, `reviewer_name` fallback "Anonymous" — verified `review_service.py:_row_to_dict`).

## 8. API Gap / Handoff ke Codex
Kalau login form-urlencoded bermasalah dari curl PHP, minta Codex sediakan JSON login body (opsional).

## 9. Estimasi (4 MD)
Hari 1: config + skeleton + login/health. Hari 2: getReviews + mock mode. Hari 3: error handling (401 retry, timeout) + smoke test live. Hari 4: buffer + rapikan logging.
