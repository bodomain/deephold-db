# Tutorial: deephold_db auf Proxmox (Debian 13) einrichten — Datenbank-Umzug

> **Fuer wen?** Du hast eine funktionierende `deephold_db` auf deinem Laptop und
> moechtest die **komplette Datenbank** (4 Mio+ Zeilen, 30 Jahre Historie) auf
> eine neue Proxmox-VM umziehen — **ohne alles neu herunterzuladen**.
> Du brauchst keine Vorkenntnisse. Jeder Schritt steht da, jeder Befehl ist kopierfertig.

---

## Inhaltsverzeichnis

1.  [Ueberblick: Was passieren wird](#1-ueberblick-was-passieren-wird)
2.  [Was du brauchst](#2-was-du-brauchst)
3.  [VM auf Proxmox erstellen](#3-vm-auf-proxmox-erstellen)
4.  [Debian 13 installieren](#4-debian-13-installieren)
5.  [Ersteinrichtung auf der VM](#5-ersteinrichtung-auf-der-vm)
6.  [Docker und Docker Compose installieren](#6-docker-und-docker-compose-installieren)
7.  [Git-Repo klonen + .env anlegen](#7-git-repo-klonen--env-anlegen)
8.  [PostgreSQL starten](#8-postgresql-starten)
9.  [Datenbank-Dump vom Laptop ziehen](#9-datenbank-dump-vom-laptop-ziehen)
10. [Dump auf die VM kopieren und einspielen](#10-dump-auf-die-vm-kopieren-und-einspielen)
11. [Verifizieren: Zaehlen was drin ist](#11-verifizieren-zaehlen-was-drin-ist)
12. [Python + Poetry einrichten (fuer Skripte/Updates)](#12-python--poetry-einrichten-fuer-skripteupdates)
13. [Taegliches Update (Cron)](#13-taegliches-update-cron)
14. [Optional: TUI-Explorer](#14-optional-tui-explorer)
15. [Optional: LaTeX-Handbuch bauen](#15-optional-latex-handbuch-bauen)
16. [Optional: Daten neu ingestieren (statt Umzug)](#16-optional-daten-neu-ingestieren-statt-umzug)
17. [Fehlersuche](#17-fehlersuche)
18. [Befehls-Uebersicht](#18-befehls-uebersicht)

---

## 1. Ueberblick: Was passieren wird

Wir machen **acht Dinge** — und bei Schritt 9+10 kopieren wir die bestehende
Datenbank, anstatt 4 Mio Zeilen neu herunterzuladen:

```
  LAUFENDE DB (Laptop)              NEUE VM (Proxmox)
  ┌──────────────────┐              ┌──────────────────┐
  │ deephold_pg       │              │ frische Debian 13│
  │ 4 Mio Zeilen      │   ──scp──>   │ + Docker         │
  │ 1 GB Daten        │              │ + pg_restore     │
  └──────────────────┘              └──────────────────┘
         │                                  │
     pg_dump -Fc                    pg_restore -c --if-exists
         │                                  │
         v                                  v
  deephold_backup.dump           deephold_db laeuft, alle Daten da!
  (~100 MB komprimiert)
```

**Zeitbedarf: ca. 15-20 Minuten** (inklusive VM-Setup, excl. ISO-Download).
Der eigentliche Datenbank-Transfer dauert ~2-3 Minuten.

---

## 2. Was du brauchst

| Ding                     | Woher?                                                       |
|--------------------------|--------------------------------------------------------------|
| Proxmox-Server (laeuft)  | Im Browser: `https://<server-ip>:8006`                       |
| Debian-13-ISO            | `https://cdimage.debian.org/cdimage/unofficial/weekly-builds/amd64/` — Lade die `netinst.iso` herunter |
| Git-Repo-Zugang          | `github.com:bodomain/deephold-db.git`                        |
| FRED API-Key             | `https://fred.stlouisfed.org/docs/api/api_key.html` — fuer spaetere Updates |
| **Laptop mit laufendem `deephold_pg`-Container** | Da ist deine DB drin |

**Minimale VM-Specs:**

| Resource   | Empfehlung |
|------------|------------|
| CPU        | 2 Kerne    |
| RAM        | 4 GB       |
| Disk       | 40 GB      |
| Netz       | Bridge, DHCP oder statisch |

> Warum 40 GB? Die DB ist ~1 GB, Docker-Images ~2 GB, Python-Venv ~500 MB,
> plus Puffer fuer Updates und Wachstum.

---

## 3. VM auf Proxmox erstellen

1. Im Proxmox-WebUI einloggen: `https://<server-ip>:8006`
2. Oben rechts: **Create VM** klicken.
3. **General:**
   - `VM ID`: z.B. `110` (fortlaufend, egal welche Nummer)
   - `Name`: `deephold`
4. **OS:**
   - `ISO image`: Die Debian-13-netinst.iso auswaehlen (muss vorher unter
     `local` → `Upload` hochgeladen worden sein)
   - `Type`: `Linux`
   - `Version`: `6.x - 2.6.kernel`
5. **System:**
   - `Machine` = `q35`, `BIOS` = `OVMF (UEFI)` (modern, empfohlen).
     Falls OVMF: klicke "Add" bei "EFI Disk" (wird automatisch erstellt).
   - Alternative: `i440fx` + `SeaBIOS` geht auch, ist aelter.
6. **Disks:**
   - `Bus/Device`: `SCSI` / `0`
   - `Storage`: `local-lvm` (oder wo du Platz hast)
   - `Disk size`: `40` (GB)
   - `Discard`: an (wenn SSD) — spart Platz
7. **CPU:**
   - `Cores`: `2`
   - `Type`: `host` (beste Performance)
8. **Memory:**
   - `Memory`: `4096` (4 GB)
9. **Network:**
   - `Bridge`: `vmbr0` (standard)
   - `Model`: `VirtIO (paravirtualized)`
   - `Firewall`: aus (einfacher fuer den Anfang)
10. **Confirm** → **Finish**.

Die VM erscheint links in der VM-Liste. **Start** klicken (der Pfeil-Button).
Dann auf **Console** klicken — da oeffnet sich ein VNC-Fenster.

---

## 4. Debian 13 installieren

Im VNC-Fenster:

1. **`Install`** waehlen (nicht `Graphical Install`).
2. **Sprache / Land:** English → United States → American English.
3. **Netzwerk:**
   - Hostname: `deephold`
   - Domain: leer lassen
4. **Root-Passwort:** Leer lassen fuer `sudo`-only (empfohlen).
5. **Benutzer anlegen:**
   - Full name: `deephold`
   - Username: `deephold`
   - Password: ein Passwort setzen
6. **Partitioning:** `Guided - use entire disk` → die einzige Festplatte →
   `All files in one partition` → `Finish` → `Yes`.
7. **Package selection:** Nur **`SSH server`** und **`standard system utilities`**
   ankreuzen. Kein Desktop.
8. **GRUB:** `Yes` → `/dev/sda` auswaehlen.
9. **Continue** → Reboot.

> **Tipp:** Wenn die VM nach dem Reboot nicht bootet, checke die Boot-Reihenfolge:
> VM → Options → Boot Order — die Festplatte muss als erstes.

---

## 5. Ersteinrichtung auf der VM

Einloggen als `deephold`. Die folgenden Befehle alle auf der VM ausfuehren.

### sudo einrichten (falls kein Root-Passwort)

```bash
# Falls du im Installer ein Root-Passwort gesetzt hast, ueberspringe das.
# Falls nicht:
su -
apt install -y sudo
usermod -aG sudo deephold
exit
```

### System updaten + Basis-Pakete

```bash
sudo apt update && sudo apt upgrade -y

sudo apt install -y \
  curl wget git vim htop tmux unzip \
  ca-certificates gnupg lsb-release \
  build-essential libpq-dev pkg-config \
  python3 python3-pip python3-venv python3-dev \
  openssh-server
```

| Paket        | Wofuer?                                        |
|--------------|-------------------------------------------------|
| `curl`       | Docker-Install, Bun-Install                    |
| `git`        | Repo klonen                                    |
| `vim`        | Dateien editieren                               |
| `htop`       | Speicher/CPU-Check                             |
| `tmux`       | Lange Jobs im Hintergrund                      |
| `libpq-dev`  | Python `psycopg` braucht die PostgreSQL-Libs  |
| `python3*`   | Wird spaeter fuer Ingest-Skripte gebraucht    |

### SSH-Zugang (damit du vom Laptop aus arbeiten kannst)

```bash
# VM-IP herausfinden:
ip addr show | grep "inet " | grep -v 127.0.0.1
# Merke dir die IP, z.B. 192.168.1.110
```

```bash
# Auf dem LAPTOP:
ssh-copy-id deephold@<vm-ip>

# Jetzt kannst du via SSH arbeiten (besser als VNC):
ssh deephold@<vm-ip>
```

---

## 6. Docker und Docker Compose installieren

```bash
# Docker-GPG-Key hinzufuegen
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Docker-Repo hinzufuegen
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Docker installieren
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Docker ohne sudo nutzen:
sudo usermod -aG docker deephold

# Gruppe aktivieren (ohne neu einloggen):
newgrp docker

# Pruefen:
docker compose version
# Ausgabe: Docker Compose version v2.x.x
```

> Falls `docker compose version` "permission denied" sagt: ausloggen und
> wieder einloggen, oder `newgrp docker` tippen.

---

## 7. Git-Repo klonen + .env anlegen

```bash
cd ~
git clone https://github.com/bodomain/deephold-db.git
cd deephold-db

# .env aus der Vorlage erstellen:
cp .env.example .env
```

Jetzt `.env` editieren — **mindestens den FRED_API_KEY eintragen** (fuer
spaetere Updates), und die Zugangsdaten checken:

```bash
vim .env
```

Die `.env` sollte so aussehen:

```ini
POSTGRES_USER=deephold
POSTGRES_PASSWORD=deephold
POSTGRES_DB=deephold
POSTGRES_PORT=5432
DATABASE_URL=postgresql+psycopg://deephold:deephold@localhost:5432/deephold
FRED_API_KEY=dein_echter_key_hier
ECB_SDMX_BASE=https://data-api.ecb.europa.eu/service
YAHOO_ENABLED=true
STOOQ_ENABLED=true
PREFECT_API_URL=http://localhost:4200/api
PREFECT_HOME=/opt/prefect
PREFECT_PORT=4200
ADMINER_PORT=8080
LOG_LEVEL=INFO
ENV=dev
```

> **Wichtig:** `FRED_API_KEY` muss dein echter Key sein. Kostenlos auf
> https://fred.stlouisfed.org/docs/api/api_key.html besorgen.
> Die `.env` steht in `.gitignore` — sie wird **nie** committet.

---

## 8. PostgreSQL starten

```bash
cd ~/deephold-db

# Docker-Container starten:
docker compose up -d

# Warten bis Postgres bereit ist:
until docker compose exec -T postgres pg_isready -U deephold; do sleep 2; done
echo "Postgres ist bereit!"

# Pruefen:
docker compose ps
```

Du solltest sehen: `deephold_pg` mit Status `Up`.

> **Was laeuft jetzt?**
>
> | Container          | Port  | Wofuer?                            |
> |--------------------|-------|-------------------------------------|
> | `deephold_pg`      | 5432  | PostgreSQL (leer, noch keine Daten) |
> | `deephold_adminer` | 8080  | Web-DB-Browser (optional)          |
> | `deephold_prefect` | 4200  | Prefect (optional)                 |

An diesem Punkt ist die Datenbank **leer** — keine Tabellen, keine Daten.
Das aendern wir jetzt mit dem Dump.

---

## 9. Datenbank-Dump vom Laptop ziehen

> **Das ist der wichtigste Schritt.** Wir exportieren die komplette
> bestehende Datenbank vom Laptop in eine Datei.

### Auf dem Laptop ausfuehren:

```bash
# Ins Projekt-Verzeichnis wechseln (wo docker-compose.yml liegt):
cd /pfad/zu/deephold-db    # bei dir wahrscheinlich ~/Desktop/Research/finance_data

# Komprimierten Dump ziehen (Empfohlen: ~100 MB statt ~600 MB):
docker exec deephold_pg pg_dump -U deephold -d deephold -Fc > deephold_backup.dump

# Groesse checken:
ls -lh deephold_backup.dump
# sollte zeigen: ~100 MB (komprimiert mit -Fc)
```

> **Was bedeutet `-Fc`?** Das ist das "custom" Format von PostgreSQL.
> Es ist komprimiert (ca. 6x kleiner als SQL-Text) und kann mit `pg_restore`
> einspielt werden. Die Alternative `-Fp` (plain SQL) waere groesser,
> aber menschenlesbar.

> **Alternative: Unkomprimierter SQL-Dump** (wenn du reinschauen willst):
> ```bash
> docker exec deephold_pg pg_dump -U deephold -d deephold > deephold_backup.sql
> # ~600 MB, aber lesbar mit jedem Texteditor
> ```

---

## 10. Dump auf die VM kopieren und einspielen

### 10a. Dump auf die VM kopieren

```bash
# Auf dem Laptop:
scp deephold_backup.dump deephold@<vm-ip>:~/
```

> `<vm-ip>` ist die IP aus Schritt 5, z.B. `192.168.1.110`.
> Der Vorgang dauert je nach Netzwerkgeschwindigkeit ca. 10-60 Sekunden.

### 10b. Dump in den Container kopieren und einspielen

```bash
# Auf der VM (per SSH oder direkt):
cd ~/deephold-db

# Dump-Datei in den laufenden Postgres-Container kopieren:
docker cp ~/deephold_backup.dump deephold_pg:/tmp/backup.dump

# Dump einspielen (das erstellt ALLE Tabellen + ALLE Daten):
docker exec deephold_pg pg_restore -U deephold -d deephold -c --if-exists /tmp/backup.dump

# Aufraeumen:
docker exec deephold_pg rm /tmp/backup.dump
```

> **Was macht `-c --if-exists`?** `-c` (clean) dropt existierende Objekte
> vor dem Erzeugen. `--if-exists` verhindert Fehler wenn die Objekte noch
> nicht existieren. Zusammen heisst das: der Dump kann in eine leere DB
> oder in eine bestehende DB eingespielt werden — immer idempotent.

> **Falls pg_restore Warnungen ausgibt** wie "does not exist, skipping":
> Das ist normal — `-c --if-exists` versucht Sachen zu droppen die noch
> nicht da sind. Solange keine "ERROR"-Zeilen kommen, ist alles OK.

### 10c. Inspizieren ob es funktioniert hat

```bash
# Tabellen auflisten:
docker exec deephold_pg psql -U deephold -d deephold -c "\dt"

# Zeilen zaehlen:
docker exec deephold_pg psql -U deephold -d deephold -c \
  "SELECT 'prices_daily' AS tabelle, count(*) FROM prices_daily
   UNION ALL SELECT 'fx_rates_daily', count(*) FROM fx_rates_daily
   UNION ALL SELECT 'bond_yields', count(*) FROM bond_yields
   UNION ALL SELECT 'macro_observations', count(*) FROM macro_observations
   UNION ALL SELECT 'instruments', count(*) FROM instruments
   UNION ALL SELECT 'vendors', count(*) FROM vendors
   UNION ALL SELECT 'macro_series', count(*) FROM macro_series;"
```

**Erwartete Ausgabe (ungefaehr):**

```
     tabelle      | count
------------------+--------
 prices_daily     | 3851359
 fx_rates_daily   | 137635
 bond_yields      |  81250
 macro_observations|  40170
 instruments      |    613
 vendors          |      3
 macro_series     |     25
(7 rows)
```

> Deine genauen Zahlen koennen leicht abweichen, je nachdem wie viele
> Serien du ingestiert hattest.

**Done!** Die Datenbank ist jetzt auf der Proxmox-VM laeuft mit allen 4 Mio+ Zeilen.
Der gesamte Transfer hat ~2-3 Minuten gedauert (statt 30-60 Minuten Neu-Download).

---

## 11. Verifizieren: Zaehlen was drin ist

Ein paar Stichproben:

```bash
docker exec deephold_pg psql -U deephold -d deephold
```

Im psql-Prompt:

```sql
-- DB-Groesse
SELECT pg_size_pretty(pg_database_size('deephold'));
-- Erwartet: ~1028 MB

-- Datumsspanne der Preise
SELECT min(date) AS von, max(date) AS bis FROM prices_daily;
-- Erwartet: 1996-06 bis heute

-- Letzte 5 AAPL-Kurse
SELECT p.date, p.close, p.volume
FROM prices_daily p
JOIN instrument_identifiers i ON p.instrument_id = i.instrument_id
WHERE i.scheme = 'YAHOO' AND i.value = 'AAPL'
ORDER BY p.date DESC LIMIT 5;

-- 10-Year Treasury Yield
SELECT date, yield FROM bond_yields b
JOIN instrument_identifiers i ON b.instrument_id = i.instrument_id
WHERE i.value = 'DGS10'
ORDER BY date DESC LIMIT 5;
```

Verlassen: `\q`

---

## 12. Python + Poetry einrichten (fuer Skripte/Updates)

Die DB laeuft jetzt, aber fuer Updates und das Query-Skript brauchen
wir Python:

```bash
# Poetry installieren:
curl -sSL https://install.python-poetry.org | python3 -
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Abhaengigkeiten installieren:
cd ~/deephold-db
poetry install

# Alembic-Status pruefen (sollte "head" zeigen):
poetry run alembic current
# Ausgabe: "38cd7d74eb4c (head)"
```

> **Wichtig:** Da der Dump alle Tabellen inklusive `alembic_version` enthaelt,
> brauchst du **nicht** `alembic upgrade head` laufen — die Migrationen
> sind schon in der DB! Das `alembic current` zeigt dir nur die aktuelle
> Version.

---

## 13. Taegliches Update (Cron)

Um die Datenbank jeden Tag um 02:00 Uhr auf dem neuesten Stand zu halten:

```bash
# Update-Skript anlegen:
cat > ~/deephold-db/scripts/daily_update.sh << 'EOF'
#!/bin/bash
set -euo pipefail
cd ~/deephold-db
poetry run python scripts/ingest_all.py --years 1 2>&1 | tee -a /var/log/deephold_ingest.log
EOF
chmod +x ~/deephold-db/scripts/daily_update.sh

# Crontab einrichten:
(crontab -l 2>/dev/null; echo "0 2 * * * ~/deephold-db/scripts/daily_update.sh") | crontab -
```

> `--years 1` holt nur die letzten 365 Tage. Da die meisten Daten schon da sind,
> werden per UPSERT nur neue/aktualisierte Werte geschrieben (~1-2 Minuten).

---

## 14. Optional: TUI-Explorer

```bash
# Bun installieren:
curl -fsSL https://bun.sh/install | bash
source ~/.bashrc

# TUI starten:
cd ~/deephold-db
make tui-install
make tui
```

---

## 15. Optional: LaTeX-Handbuch bauen

```bash
sudo apt install -y texlive-latex-base texlive-latex-extra texlive-bibtex-extra \
  texlive-fonts-recommended texlive-fonts-extra biber
make handbuch
```

---

## 16. Optional: Daten neu ingestieren (statt Umzug)

Falls du **keine** bestehende DB hast oder die Daten komplett neu aufbauen
willst, kannst du statt des Dumps auch alles neu herunterladen:

```bash
cd ~/deephold-db

# Zunaechst das Schema anlegen (da noch keine Tabellen existieren):
poetry run alembic upgrade head

# Alle Phasen nacheinander (~30-60 Minuten):
tmux new -s ingest
poetry run python scripts/ingest_all.py
# Strg+B, D zum Detachen

# Oder phase-fuer-phase:
poetry run python scripts/ingest_all.py --phase fred       # ~3 Min
poetry run python scripts/ingest_all.py --phase ecb         # ~2 Min
poetry run python scripts/ingest_all.py --phase yahoo-ne    # ~5 Min
poetry run python scripts/ingest_all.py --phase yahoo-eq   # ~30 Min
```

| Phase       | Quelle     | Asset-Klassen                       | ~Zeilen     |
|-------------|------------|--------------------------------------|-------------|
| `fred`      | FRED API   | Staatsanleihen, Makro, FX, Vol       | ~340.000    |
| `ecb`        | ECB SDMX   | EUR-FX, Geldmarkt, HICP              | ~23.000     |
| `yahoo-ne`  | yfinance   | Indizes, Rohstoffe, FX, Credit-ETFs  | ~206.000    |
| `yahoo-eq`  | yfinance   | Aktien (US/EU/JP/EM + S&P 500)       | ~3.680.000  |

> **Idempotenz:** Re-Runs erzeugen keine Duplikate (`ON CONFLICT DO UPDATE`).

---

## 17. Fehlersuche

### pg_restore Fehler: "role deephold does not exist"

Der Dump enthaelt evtl. `OWNER`-Statements fuer den User `deephold`.
Da der Docker-Container denselben User anlegt, sollte das klappen.
Falls nicht:

```bash
docker exec deephold_pg psql -U deephold -d deephold -c "CREATE ROLE deephold LOGIN PASSWORD 'deephold';"
# Nochmal versuchen:
docker exec deephold_pg pg_restore -U deephold -d deephold -c --if-exists /tmp/backup.dump
```

### Docker/Postgres startet nicht

```bash
docker compose logs postgres
# Port schon belegt?
sudo lsof -i :5432
# Neu starten:
docker compose down && docker compose up -d
```

### pg_restore: "connection to server on socket"

```bash
# Statt lokalem Socket, Host angeben:
docker exec deephold_pg pg_restore -h localhost -U deephold -d deephold -c --if-exists /tmp/backup.dump
```

### Dump zu gross fuer scp?

```bash
# Komprimierter Dump ist nur ~100 MB. Falls das immer noch zu gross ist:
# Auf dem Laptop:
docker exec deephold_pg pg_dump -U deephold -d deephold -Fc -Z9 > deephold_backup.dump
# -Z9 = maximale Kompression (~60-80 MB)
```

### VM-IP herausfinden

```bash
ip addr show | grep "inet " | grep -v 127.0.0.1
```

### Alle Daten loeschen (neu anfangen)

```bash
docker compose down -v     # -v loescht auch die Docker-Volumes!
docker compose up -d       # Neu starten (leere DB)
```

### Alembic-Version checken

```bash
# Sollte "head" (38cd7d74eb4c) anzeigen nach dem Dump:
poetry run alembic current
```

Falls nicht:

```bash
poetry run alembic stamp head    # Markiert aktuelle Migration als "head"
```

### psql-Shell fuer Ad-hoc-Queries

```bash
docker exec deephold_pg psql -U deephold -d deephold
```

---

## 18. Befehls-Uebersicht

### Auf dem Laptop (einmalig)

| Befehl                                                       | Was es tut                       |
|--------------------------------------------------------------|----------------------------------|
| `docker exec deephold_pg pg_dump -U deephold -d deephold -Fc > deephold_backup.dump` | DB-Export (komprimiert) |
| `scp deephold_backup.dump deephold@<vm-ip>:~/`               | Dump auf die VM kopieren         |

### Auf der VM

| Befehl                                                       | Was es tut                              |
|--------------------------------------------------------------|-----------------------------------------|
| `docker compose up -d`                                       | Postgres starten                        |
| `docker compose down`                                        | Stoppen (Daten bleiben)                 |
| `docker compose down -v`                                     | Stoppen + Daten loeschen                |
| `docker compose logs -f postgres`                            | Postgres-Logs live ansehen              |
| `docker cp ~/deephold_backup.dump deephold_pg:/tmp/backup.dump` | Dump in Container kopieren          |
| `docker exec deephold_pg pg_restore -U deephold -d deephold -c --if-exists /tmp/backup.dump` | Dump einspielen |
| `docker exec deephold_pg psql -U deephold -d deephold -c "\dt"` | Tabellen auflisten                  |
| `poetry install`                                              | Python-Abhaengigkeiten installieren    |
| `poetry run alembic current`                                  | Aktuelle Migration checken              |
| `poetry run python scripts/ingest_all.py --years 1`          | Nur Updates holen (Cron-Job)           |
| `poetry run python scripts/query_db.py`                      | DB-Inhalte anzeigen                     |

---

## Anhang: Schnellstart (Copy-Paste)

Fuer alle, die einfach nur moechten dass es laeuft — alle Befehle
von der VM aus, nachdem die Debian-Installation durch ist:

```bash
# ===== AUF DER VM =====

# 1. Basis-Pakete
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl wget git vim htop tmux ca-certificates gnupg lsb-release \
  build-essential libpq-dev pkg-config python3 python3-pip python3-venv python3-dev

# 2. Docker
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker

# 3. Repo klonen + .env
cd ~
git clone https://github.com/bodomain/deephold-db.git
cd deephold-db
cp .env.example .env
# vim .env   # FRED_API_KEY eintragen!

# 4. Postgres starten
docker compose up -d
until docker compose exec -T postgres pg_isready -U deephold; do sleep 2; done

# 5. Dump einspielen (Dump muss vorher per scp auf die VM kopiert worden sein!)
docker cp ~/deephold_backup.dump deephold_pg:/tmp/backup.dump
docker exec deephold_pg pg_restore -U deephold -d deephold -c --if-exists /tmp/backup.dump
docker exec deephold_pg rm /tmp/backup.dump

# 6. Poetry + Python-Skripte
curl -sSL https://install.python-poetry.org | python3 -
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
poetry install

# 7. Verifizieren
docker exec deephold_pg psql -U deephold -d deephold -c \
  "SELECT 'prices_daily' AS t, count(*) FROM prices_daily;"

# Fertig! ~4 Mio Zeilen Preise, 30 Jahre Historie, alles da.
```

```bash
# ===== AUF DEM LAPTOP =====

# 8. Dump ziehen (einmalig, vor Schritt 5)
cd /pfad/zu/deephold-db
docker exec deephold_pg pg_dump -U deephold -d deephold -Fc > deephold_backup.dump
scp deephold_backup.dump deephold@<vm-ip>:~/
```

---

*Letzte Aktualisierung: 2026-06-17. DB-Stand: ~4 Mio Zeilen prices_daily, 30 Jahre Historie.*