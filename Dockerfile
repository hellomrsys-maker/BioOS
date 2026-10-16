# ---------- Stage 1: Plane A safety kernel cdylib (Linux target) ----------
FROM rust:1-slim AS kernel-builder
WORKDIR /build
# Copy manifests first for dependency-layer caching; seed an empty lib so
# `cargo build` can prefetch/compile dependencies, then overlay real sources.
COPY crates/bioos-kernel/Cargo.toml crates/bioos-kernel/Cargo.lock ./
RUN mkdir -p src && printf '' > src/lib.rs && cargo build --release --quiet
COPY crates/bioos-kernel/src ./src
RUN touch src/lib.rs && cargo build --release --quiet

# ---------- Stage 2: BioOS Enterprise Runtime (Plane B + Command Center) ----------
FROM python:3.12-slim
WORKDIR /app

# Pinned dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Plane A kernel cdylib: kernel_bridge resolves it at
# crates/bioos-kernel/target/release/libbioos_kernel.so (repo-relative layout preserved)
COPY --from=kernel-builder /build/target/release/libbioos_kernel.so \
     crates/bioos-kernel/target/release/libbioos_kernel.so

COPY services ./services
COPY web ./web

EXPOSE 8090

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8090/api/health', timeout=4).status==200 else 1)" || exit 1

CMD ["python", "services/bioos_runtime.py"]
