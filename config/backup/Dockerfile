# Canonical daily Postgres backup image (identical in every app of the fleet; only compose env differs).
# Why FROM the postgres image: pg_dump/pg_restore must match the server's major version (18) exactly,
# and this image already ships them. Why the b2 CLI and not boto/S3: it speaks the B2 native API and
# handles large-file multipart on its own (dumps grow to GB/TB), and it avoids the boto>=1.36 CRC32
# aws-chunked trailer that B2 rejects.
FROM postgres:18.4-trixie

# b2 CLI standalone binary, pinned. `b2v4-linux` = the frozen v4 command interface shipped inside the
# 5.0.0 release, so a future major bump of `b2` cannot silently change the commands pg_backup.sh uses.
# sha256 taken from the GitHub release asset digest (Backblaze/B2_Command_Line_Tool v5.0.0).
ARG B2_VERSION=5.0.0
ARG B2_SHA256=a36b93eed5bba078987bf3343571c025260499a39fb94c60420d8eb2c48b2066

# jq: JSON log lines + parsing `b2 ls --json`. tzdata: the schedule is in America/Sao_Paulo local time.
# curl is build-only and purged afterwards.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl jq tzdata \
    && curl -fsSL -o /usr/local/bin/b2 \
        "https://github.com/Backblaze/B2_Command_Line_Tool/releases/download/v${B2_VERSION}/b2v4-linux" \
    && echo "${B2_SHA256}  /usr/local/bin/b2" | sha256sum -c - \
    && chmod 0755 /usr/local/bin/b2 \
    && apt-get purge -y --auto-remove curl \
    && rm -rf /var/lib/apt/lists/*

COPY pg_backup.sh /usr/local/bin/pg_backup.sh
# /backup is the volume mountpoint: a fresh named volume inherits this ownership, so the non-root user can write.
RUN chmod 0755 /usr/local/bin/pg_backup.sh \
    && mkdir /backup \
    && chown postgres:postgres /backup

# Non-root: the postgres user (uid 999) also owns the unix socket in the shared `pgsocket` volume.
USER postgres
ENTRYPOINT ["/usr/local/bin/pg_backup.sh"]
CMD ["run"]
