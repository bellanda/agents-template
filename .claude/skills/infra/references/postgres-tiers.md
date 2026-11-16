# Postgres prod.conf — memory tiers (decision 2026-11-15, audit infra-live-02)

There is NO generator: each repo carries `config/postgres/prod.conf` as a hand-edited file and
`backend/tests/scripts/test_runtime_infra_config.py` guards that `shared_buffers + max_connections *
work_mem` fits the postgres container limit in `compose.prod.yaml`. This table is the reference the
files are edited against; change a value here AND in the repos together.

## shared-16gb — VPS shared by several apps (`bellanda-hostinger-vps`: kailos, promoservice, akmeo, emporion)

| Setting | kailos | small apps (promoservice, akmeo, emporion) |
| --- | --- | --- |
| shared_buffers | 1GB | 256MB |
| effective_cache_size | 4GB | 1GB |

Common to both: work_mem 16MB, maintenance_work_mem 256MB, autovacuum_work_mem 128MB, max_connections 60,
max_worker_processes 8, max_parallel_workers 4, max_parallel_workers_per_gather 2, wal_buffers 16MB,
max_wal_size 4GB, min_wal_size 512MB, jit off.

## dedicated-16gb — VPS with a single app (nexarena, optimuslar)

shared_buffers 3GB, effective_cache_size 10GB, work_mem 32MB, maintenance_work_mem 512MB (autovacuum_work_mem
256MB), max_connections 100, max_worker_processes 8, max_parallel_workers 4, max_parallel_workers_per_gather 2
(2-3 workers is the intended range; 4/2 is what the repos run), wal_buffers 16MB, max_wal_size 4GB,
min_wal_size 512MB, jit off.

## State of the repos on 2026-11-15 (checked against each prod.conf)

- kailos: matches shared-16gb.
- nexarena, optimuslar: match dedicated-16gb.
- promoservice, akmeo, emporion: still at the old small values (shared_buffers 128MB, effective_cache_size
  768MB, work_mem 8MB, maintenance_work_mem 128MB, autovacuum_work_mem 64MB, max_connections 50) - NOT yet
  at the shared-16gb small-app tier. Raise them only together with the `compose.prod.yaml` memory limit check.
