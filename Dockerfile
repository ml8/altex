FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ghostscript nodejs npm default-jre-headless unzip curl && \
    rm -rf /var/lib/apt/lists/*

# Install verapdf (PDF/UA validator) via IzPack auto-install.
RUN curl -sL https://software.verapdf.org/releases/verapdf-installer.zip \
        -o /tmp/verapdf.zip && \
    unzip -q /tmp/verapdf.zip -d /tmp/verapdf-inst && \
    JAR=$(find /tmp/verapdf-inst -name '*.jar' -type f | head -1) && \
    printf '<?xml version="1.0" encoding="UTF-8"?>\n\
<AutomatedInstallation langpack="eng">\n\
<com.izforge.izpack.panels.htmlhello.HTMLHelloPanel id="welcome"/>\n\
<com.izforge.izpack.panels.target.TargetPanel id="install_dir">\n\
<installpath>/opt/verapdf</installpath>\n\
</com.izforge.izpack.panels.target.TargetPanel>\n\
<com.izforge.izpack.panels.packs.PacksPanel id="sdk_pack_select">\n\
<pack index="0" name="veraPDF Mac and *nix Scripts" selected="true"/>\n\
<pack index="1" name="veraPDF Validation model" selected="true"/>\n\
</com.izforge.izpack.panels.packs.PacksPanel>\n\
<com.izforge.izpack.panels.install.InstallPanel id="install"/>\n\
<com.izforge.izpack.panels.finish.FinishPanel id="finish"/>\n\
</AutomatedInstallation>' > /tmp/auto.xml && \
    java -jar "$JAR" /tmp/auto.xml && \
    ln -s /opt/verapdf/verapdf /usr/local/bin/verapdf && \
    rm -rf /tmp/verapdf-inst /tmp/verapdf.zip /tmp/auto.xml && \
    apt-get purge -y unzip curl && apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt flask gunicorn

COPY package.json .
RUN npm install --production

COPY altex/ altex/
COPY web/ web/
COPY scripts/ scripts/

ENV FLASK_APP=web.app
ENV ALTEX_STORAGE=inline
EXPOSE 5000

CMD ["gunicorn", "web.app:app", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "2", \
     "--timeout", "120"]
