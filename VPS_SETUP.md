# Flowscope Linux VPS Deployment Guide (Ubuntu)

Panduan ini berisi langkah-langkah utuh untuk menjalankan **Flowscope** (Backend, Database, dan Frontend) di server VPS Linux (Ubuntu 22.04 / 24.04). Sistem dirancang agar dapat menyala 24/7 tanpa henti (otomatis hidup kembali saat server restart).

## Persiapan Server
1. Login ke VPS Anda via SSH.
2. Update sistem dasar:
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```
3. Install dependensi wajib:
   ```bash
   sudo apt install curl git build-essential nginx -y
   ```

## 1. Install PostgreSQL & Redis
Flowscope menggunakan PostgreSQL untuk merekam *history* aliran uang yang masif dan Redis untuk caching cepat (opsional namun disarankan).

```bash
# Install Database & Cache
sudo apt install postgresql postgresql-contrib redis-server -y

# Setup PostgreSQL Database dan User
sudo -u postgres psql
```

Dalam *prompt* PostgreSQL (`postgres=#`), ketikkan:
```sql
CREATE DATABASE flowscope;
CREATE USER flowdb_user WITH PASSWORD 'password_super_kuat';
ALTER ROLE flowdb_user SET client_encoding TO 'utf8';
ALTER ROLE flowdb_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE flowdb_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE flowscope TO flowdb_user;
\q
```

## 2. Install Python dan Node.js

**Install Node.js (via NVM):**
```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc
nvm install 20
nvm use 20
```

**Install Python & PM2:**
```bash
sudo apt install python3.11 python3.11-venv python3-pip -y
npm install -g pm2
```

## 3. Clone Repository & Setup Lingkungan

Misalkan kita meletakkan repo di `/var/www/flowscope`:
```bash
sudo mkdir -p /var/www/flowscope
sudo chown -R $USER:$USER /var/www/flowscope
cd /var/www/flowscope

# (Asumsi Anda memindahkan file dari lokal Anda ke VPS via git / rsync / scp)
# git clone <url-repo-anda> .
```

---

## 4. Setup Backend (FastAPI / Uvicorn)

1. Buat Virtual Environment:
   ```bash
   cd /var/www/flowscope/backend
   python3.11 -m venv venv
   source venv/bin/activate
   ```
2. Install dependensi:
   ```bash
   pip install -r requirements.txt
   ```
3. Sesuaikan file `.env` untuk config database yang menggunakan kredensial PostgreSQL yang baru Anda buat.
   ```ini
   DATABASE_URL=postgresql://flowdb_user:password_super_kuat@localhost:5432/flowscope
   ```
4. Verifikasi bahwa database dapat bermigrasi dan backend menyala normal:
   ```bash
   python -m uvicorn main:app --port 8000
   ```
   *(Tekan CTRL+C jika log terlihat hijau dan API sudah jalan)*

5. **Jalankan Backend Secara Permanen via PM2:**
   ```bash
   pm2 start "source venv/bin/activate && python -m uvicorn main:app --host 127.0.0.1 --port 8000" --name flowscope-backend
   ```

---

## 5. Setup Frontend (Next.js)

1. Masuk ke direktori Frontend:
   ```bash
   cd /var/www/flowscope/frontend
   ```
2. Install npm module:
   ```bash
   npm install
   ```
3. Sesuaikan URL API backend Anda (opsional, jika Anda menyiapkan koneksi antar-port secara default, biarkan standar).
4. Lakukan Build untuk *Production*:
   ```bash
   npm run build
   ```
5. **Jalankan Frontend Secara Permanen via PM2:**
   ```bash
   pm2 start npm --name "flowscope-frontend" -- start
   ```

## 6. Menyimpan PM2 agar Otomatis Startup

Agar PM2 akan kembali menghidupkan Backend dan Frontend saat server restart/mati tiba-tiba:
```bash
pm2 save
pm2 startup
# (Ikuti / Copy-Paste perintah sudo yang muncul di terminal setelah mengetik pm2 startup)
```

---

## 7. Expose ke Publik dengan Nginx Reverse Proxy (Opsional tapi Wajib untuk Akses Domain)

Buat file konfigurasi nginx:
```bash
sudo nano /etc/nginx/sites-available/flowscope
```

Isikan rancangan berikut (ganti domain.com dengan IP/Domain Anda):
```nginx
server {
    listen 80;
    server_name your_domain_or_IP;

    # Routing Frontend Next.js
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Routing Backend FastAPI API & WebSocket
    location /api/ {
        proxy_pass http://localhost:8000/; # '/' mentranslate /api/scanner menjadi /scanner ke backend
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

Aktifkan konfigurasi dan restart nginx:
```bash
sudo ln -s /etc/nginx/sites-available/flowscope /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

Selamat! Sistem Flowscope Profesional Anda sekarang berjalan penuh 24/7 di VPS secara aman dan terisolasi!
