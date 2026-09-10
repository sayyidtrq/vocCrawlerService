# RI-14 — Aksi Manajemen Review (≤4 MD)

> Ini pemenuhan "review bisa DIKELOLA" dari CEO — reuse lifecycle Ticket existing [verified: assign/resolve/close/note ada di modul Ticket, DFD Onebox 2.2].

## 1. Tujuan & DoD
Dari detail review (RI-11): **assign** ke user, **tandai selesai (resolve)**, **tambah catatan internal (note)**. **Selesai kalau:** ketiga aksi bekerja dan tercermin di kolom Ticket (`TicketAssignee`, `StatusId`, `Notes`) + terlihat di list (badge status/assignee).

## 2. Prasyarat
RI-11. Verifikasi dulu mekanisme existing.

## 3. Langkah
1. **Verifikasi cara modul lain melakukan assign/resolve** `[assumption]`: cari action assign di TicketController/helpdesk (`grep -rn "TicketAssignee" app/controllers --include="*.php" -l | head`) — **prioritas: panggil ulang mekanisme existing** (endpoint/method yang sama), bukan menulis logic status sendiri.
2. Kalau endpoint existing bisa dipakai lintas modul → tombol di detailReview cukup memanggilnya (AJAX). Kalau tidak → action tipis di Mediamonitoring yang update `StatusId`/insert `TicketAssignee`/insert `Notes` meniru persis nilai-nilai yang dipakai modul Ticket (status code `TS*` dari RI-01 L3).
3. Badge status/assignee di list & detail.
4. Permission: hormati `getActionRolePermission()` [verified dipakai Mediamonitoring line 27] — aksi manajemen hanya untuk role yang berhak.

## 5. Verifikasi
Assign → muncul di `TicketAssignee` + user ybs melihatnya; resolve → `StatusId` berubah + `SolveDate` terisi; note → tersimpan & tampil; role tanpa permission → tombol tidak muncul/aksi ditolak server-side (dua-duanya).

## 6. Risiko
Menyimpang dari lifecycle resmi bikin data aneh di report SLA existing — makanya langkah 1 (reuse) wajib dicoba dulu.

## 9. Estimasi (4 MD)
Hari 1: verifikasi mekanisme existing. Hari 2: wiring aksi. Hari 3: badge + permission. Hari 4: verifikasi role + SLA sanity.
