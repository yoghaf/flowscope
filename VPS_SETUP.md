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

Flowscope menggunakan PostgreSQL untuk merekam _history_ aliran uang yang masif dan Redis untuk caching cepat (opsional namun disarankan).

```bash
# Install Database & Cache
sudo apt install postgresql postgresql-contrib redis-server -y

# Setup PostgreSQL Database dan User
sudo -u postgres psql
```

Dalam _prompt_ PostgreSQL (`postgres=#`), ketikkan:

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
sudo apt install python3.11 python3-pip -y
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

1. Install dependensi:
   ```bash
   cd /var/www/flowscope/backend
   pip3 install -r requirements.txt
   ```
2. Sesuaikan file `.env` untuk config database yang menggunakan kredensial PostgreSQL yang baru Anda buat. Tambahkan juga aturan CORS untuk mengizinkan web Anda meremote data.
   ```ini
   DATABASE_URL=postgresql://flowdb_user:password_super_kuat@localhost:5432/flowscope
   FLOWSCOPE_CORS_ORIGINS=http://IP_VPS_ANDA:3000,http://IP_VPS_ANDA,http://localhost:3000
   ```
3. Verifikasi bahwa database dapat bermigrasi dan backend menyala normal:

   ```bash
   python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
   ```

   _(Tekan CTRL+C jika log terlihat hijau dan API sudah jalan)_

4. **Jalankan Backend Secara Permanen via PM2:**
   ```bash
   pm2 start "python3 -m uvicorn main:app --host 0.0.0.0 --port 8000" --name flowscope-backend
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
3. **PENTING: Tembakkan URL API ke IP Servermu!**
   Secara default React akan mencoba mengambil data di `localhost`. Agar web bisa diakses dari HP/PC lain, beri tahu Next.js di mana API berada dengan membuat file `.env.local`:
   ```bash
   echo "NEXT_PUBLIC_API_URL=http://IP_VPS_ANDA:8000" > .env.local
   ```
4. Lakukan Build untuk _Production_:
   ```bash
   npm run build
   ```
   _(Setiap kali kamu mengubah IP/URL di `.env.local`, kamu wajib melakukan `npm run build` ulang)_.
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
