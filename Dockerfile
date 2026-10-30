# ─────────────────────────────────────────────────────────────
#  Lean build (slim base, chromium-only Playwright, pruned bgutil)
#  Fixes vs old Dockerfile:
#   - removed the risky site-packages cleanup (deleting every "test"/
#     "tests" dir and *.dist-info can silently break installed packages)
#   - build now FAILS if pyrogram/pytgcalls can't be imported, so a
#     broken image is never deployed
#   - temporary compiler added only for the pip step, then purged
# ─────────────────────────────────────────────────────────────
FROM python:3.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV BGUTIL_SERVER_HOME=/app/bgutil-ytdlp-pot-provider/server
ENV DEBIAN_FRONTEND=noninteractive

# ── System deps: ffmpeg + Node.js 20 + Chromium deps + git ──
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        wget \
        git \
        gnupg \
        ca-certificates \
        ffmpeg \
        libnss3 \
        libnspr4 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libxkbcommon0 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libgbm1 \
        libasound2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgtk-3-0 \
        libx11-xcb1 \
        libxcb-dri3-0 \
        fonts-liberation \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && apt-get autoremove -y \
    && rm -rf \
        /var/lib/apt/lists/* \
        /var/cache/apt/archives/* \
        /usr/share/doc/* \
        /usr/share/man/* \
        /usr/share/locale/* \
        /tmp/*

WORKDIR /app

# ── Python packages ───────────────────────────────────────────
# gcc/g++ only for packages that have no prebuilt wheel, purged after.
COPY requirements.txt .
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc g++ make libffi-dev libssl-dev \
    && python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install -r requirements.txt \
    && python -m pip install -U bgutil-ytdlp-pot-provider \
    # Fail the build immediately if the core libs are not importable
    && python -c "import pyrogram, pytgcalls; print('pyrogram', pyrogram.__version__, 'OK')" \
    # Patch pyrogram 2.0.106 so new 64-bit channel IDs (e.g. -1002275616383) are accepted
    && sed -i 's/MIN_CHANNEL_ID = -1002147483647/MIN_CHANNEL_ID = -1007852516352/' /usr/local/lib/python3.10/site-packages/pyrogram/utils.py \
    && sed -i 's/MIN_CHAT_ID = -2147483647/MIN_CHAT_ID = -999999999999/' /usr/local/lib/python3.10/site-packages/pyrogram/utils.py \
    && grep -n "MIN_CHANNEL_ID =\|MIN_CHAT_ID =" /usr/local/lib/python3.10/site-packages/pyrogram/utils.py \
    # Safe cleanup only (bytecode caches)
    && find /usr/local/lib/python3.10 -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true \
    && apt-get purge -y --auto-remove gcc g++ make libffi-dev libssl-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /root/.cache/pip /tmp/*

# ── Playwright: chromium only (system deps already installed) ─
RUN playwright install chromium \
    && rm -rf /root/.cache/pip /tmp/* /var/tmp/*

# ── bgutil Node.js server ─────────────────────────────────────
RUN git clone --single-branch --depth 1 \
        https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git \
        /app/bgutil-ytdlp-pot-provider \
    && cd /app/bgutil-ytdlp-pot-provider/server \
    && npm ci \
    && npx tsc \
    && npm prune --production \
    && rm -rf \
        /app/bgutil-ytdlp-pot-provider/server/src \
        /app/bgutil-ytdlp-pot-provider/.git \
        /root/.npm \
        /tmp/*

# ── Project source ────────────────────────────────────────────
COPY . .
RUN chmod +x start \
    && find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true \
    && find . -name "*.pyc" -delete 2>/dev/null || true

CMD ["bash", "start"]
