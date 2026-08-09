# VPS Deployment Guide - Stock Massive

Hướng dẫn từng bước deploy Stock Massive lên VPS.

> Guide này dành cho **production**: cả `api` và `web` đều chạy trong Docker.
> Ở development thì khác — backend trong Docker, frontend chạy trực tiếp trên
> máy. Xem [Deployment Guide](deployment-guide.md).

---

## Bước 1: Thuê VPS

### Cấu hình tối thiểu khuyến nghị

- **CPU**: 2 vCPU
- **RAM**: 4GB (tối thiểu 2GB — build image `web` khá tốn RAM)
- **Storage**: 50GB SSD
- **OS**: Ubuntu 22.04 LTS

Provider phổ biến: DigitalOcean, Vultr, Linode, AWS Lightsail, Contabo.

---

## Bước 2: Kết nối và tạo user

```bash
ssh root@your-vps-ip

# Tạo user thường (an toàn hơn dùng root)
adduser deploy
usermod -aG sudo deploy
su - deploy
```

---

## Bước 3: Cài Docker

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common

curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Cho phép user chạy docker không cần sudo
sudo usermod -aG docker $USER
newgrp docker

docker --version
docker compose version
```

---

## Bước 4: Clone project

```bash
sudo apt install -y git
mkdir -p ~/apps && cd ~/apps
git clone https://github.com/your-username/stock-massive.git
cd stock-massive
```

---

## Bước 5: Chọn phương án database

`docker-compose.prod.yml` mặc định **không** start container database. Có 2 lựa chọn:

### Phương án A — Postgres bên ngoài (khuyến nghị)

Dùng managed Postgres (Supabase, Neon, RDS, DigitalOcean Managed DB...). Chỉ cần
trỏ `DATABASE_URL` tới nó, thêm `?sslmode=require` nếu provider yêu cầu:

```env
DATABASE_URL=postgresql://user:password@db-host:5432/stockmassive?sslmode=require
```

Ưu điểm: backup và HA do provider lo. Container `api` phát hiện host khác
`db`/`localhost` nên bỏ qua bước chờ và chạy migration ở chế độ non-blocking.

### Phương án B — Self-host Postgres trên cùng VPS

Compose có sẵn service `db` phía sau profile `db`. Bật bằng cách thêm
`--profile db` vào mọi lệnh compose và cấu hình:

```env
DATABASE_URL=postgresql://postgres:MyStr0ngP@ssword@db:5432/stockmassive
POSTGRES_USER=postgres
POSTGRES_PASSWORD=MyStr0ngP@ssword
POSTGRES_DB=stockmassive
```

Data nằm trong named volume `postgres_data`. Bạn tự chịu trách nhiệm backup
(xem phần Backup ở dưới).

---

## Bước 6: Cấu hình Environment

```bash
cp .env.example .env
nano .env
```

Các giá trị bắt buộc sửa:

```env
# Database — theo phương án đã chọn ở Bước 5
DATABASE_URL=...
POSTGRES_PASSWORD=...        # chỉ khi dùng profile db

# Auth — tạo bằng: openssl rand -base64 32
AUTH_SECRET=...

# Domain của bạn (origin mà browser dùng)
CORS_ORIGINS=https://yourdomain.com

# URL API mà browser gọi — đây là BUILD ARG của image web
NEXT_PUBLIC_API_URL=https://api.yourdomain.com/api/v1
```

Tạo secret:

```bash
openssl rand -base64 32
```

Lưu file trong nano: `Ctrl+O` → `Enter` → `Ctrl+X`.

> `NEXT_PUBLIC_API_URL` được nhúng vào bundle lúc build image `web`. Đổi giá trị
> này thì phải rebuild image, restart không đủ.

---

## Bước 7: Build và chạy

```bash
# Phương án A (database bên ngoài)
docker compose -f docker-compose.prod.yml up -d --build

# Phương án B (self-host Postgres)
docker compose -f docker-compose.prod.yml --profile db up -d --build
```

Lần build đầu mất khoảng 5–10 phút.

Kiểm tra:

```bash
docker compose -f docker-compose.prod.yml ps
```

Kết quả mong đợi:

```
NAME                 STATUS
stockmassive-api     Up
stockmassive-web     Up
stockmassive-db      Up (healthy)   # chỉ khi dùng --profile db
```

Xem logs khi có lỗi:

```bash
docker compose -f docker-compose.prod.yml logs -f
docker compose -f docker-compose.prod.yml logs api
docker compose -f docker-compose.prod.yml logs web
```

> **Build image `web` fail với `fetch failed` / `ECONNREFUSED`?** Một số trang
> analytics fetch API trong lúc prerender, nên API phải reachable ở thời điểm
> build. Start `api` trước rồi build `web`:
> `docker compose -f docker-compose.prod.yml up -d --build api` →
> `docker compose -f docker-compose.prod.yml up -d --build web`.

Migrations chạy tự động qua `entrypoint.sh` của container `api`.

---

## Bước 8: Nginx reverse proxy

```bash
sudo apt install -y nginx
sudo nano /etc/nginx/sites-available/stockmassive
```

```nginx
# Frontend
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}

# API
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/stockmassive /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

---

## Bước 9: DNS

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | @ | your-vps-ip | 3600 |
| A | www | your-vps-ip | 3600 |
| A | api | your-vps-ip | 3600 |

---

## Bước 10: SSL (HTTPS)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com -d api.yourdomain.com
```

Certbot sẽ hỏi email, terms (chọn `A`), share email (`N`), redirect HTTP→HTTPS (chọn `2`).

Test auto-renew:

```bash
sudo certbot renew --dry-run
```

---

## Bước 11: Kiểm tra

Trên browser:

```
https://yourdomain.com           -> Frontend
https://api.yourdomain.com/docs  -> Swagger API docs
```

Trên terminal:

```bash
curl https://api.yourdomain.com/health
curl https://api.yourdomain.com/api/v1/stocks/symbols
```

---

## Vận hành

Các lệnh dưới đây giả định phương án A. Nếu dùng self-host Postgres, thêm
`--profile db` vào mọi lệnh `up` / `down` / `ps`.

### Quản lý containers

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml restart
docker compose -f docker-compose.prod.yml down          # giữ data
docker compose -f docker-compose.prod.yml down -v       # XÓA cả volume database
```

### Logs

```bash
docker compose -f docker-compose.prod.yml logs -f
docker compose -f docker-compose.prod.yml logs --tail=100 api
```

### Vào container

```bash
docker compose -f docker-compose.prod.yml exec api bash
docker compose -f docker-compose.prod.yml exec api alembic upgrade head

# Chỉ khi self-host Postgres
docker compose -f docker-compose.prod.yml --profile db exec db psql -U postgres -d stockmassive
```

### Update code

```bash
cd ~/apps/stock-massive
git pull origin main
docker compose -f docker-compose.prod.yml up -d --build

# Hoặc từng service
docker compose -f docker-compose.prod.yml up -d --build api
docker compose -f docker-compose.prod.yml up -d --build web
```

---

## Backup database

### Self-host Postgres (profile `db`)

```bash
docker compose -f docker-compose.prod.yml --profile db exec -T db \
  pg_dump -U postgres stockmassive > backup_$(date +%Y%m%d).sql

# Restore
docker compose -f docker-compose.prod.yml --profile db exec -T db \
  psql -U postgres -d stockmassive -v ON_ERROR_STOP=1 < backup_20260809.sql
```

Backup tự động hàng ngày:

```bash
nano ~/backup-db.sh
```

```bash
#!/bin/bash
BACKUP_DIR=~/backups
mkdir -p $BACKUP_DIR
cd ~/apps/stock-massive
docker compose -f docker-compose.prod.yml --profile db exec -T db \
  pg_dump -U postgres stockmassive > $BACKUP_DIR/backup_$(date +%Y%m%d_%H%M%S).sql
# Xóa backup cũ hơn 7 ngày
find $BACKUP_DIR -name "backup_*.sql" -mtime +7 -delete
```

```bash
chmod +x ~/backup-db.sh
crontab -e
# 0 3 * * * /home/deploy/backup-db.sh
```

### Postgres bên ngoài

```bash
pg_dump "$DATABASE_URL" > backup_$(date +%Y%m%d).sql
psql "$DATABASE_URL" < backup.sql
```

Managed provider thường có automated backup — kiểm tra và bật nếu chưa có.

---

## Troubleshooting

### Container không chạy

```bash
docker compose -f docker-compose.prod.yml logs api
docker compose -f docker-compose.prod.yml config    # kiểm tra biến đã resolve đúng
```

Compose fail ngay nếu thiếu `DATABASE_URL` hoặc `AUTH_SECRET` — đó là chủ ý.

### Database connection error

```bash
docker compose -f docker-compose.prod.yml logs api | grep -i database
# Self-host: kiểm tra db container
docker compose -f docker-compose.prod.yml --profile db ps db
# Bên ngoài: test trực tiếp
psql "$DATABASE_URL" -c "SELECT 1"
```

### Frontend gọi API bị chặn CORS

`CORS_ORIGINS` phải chứa đúng origin production (kèm `https://`). Sửa `.env` rồi
`docker compose -f docker-compose.prod.yml up -d api`.

### Frontend gọi sai URL API

`NEXT_PUBLIC_API_URL` đã nhúng vào bundle — sửa `.env` rồi **rebuild**:

```bash
docker compose -f docker-compose.prod.yml up -d --build web
```

### Port đã được sử dụng

```bash
sudo lsof -i :3000
sudo lsof -i :8000
```

### Hết dung lượng disk

```bash
df -h
docker system prune -a
```

---

## Checklist trước khi live

- [ ] `AUTH_SECRET` random (không dùng giá trị mẫu)
- [ ] `POSTGRES_PASSWORD` mạnh (nếu self-host database)
- [ ] `DATABASE_URL` đúng và test được
- [ ] `CORS_ORIGINS` trỏ đúng domain
- [ ] `NEXT_PUBLIC_API_URL` đúng và image `web` đã rebuild
- [ ] DNS đã trỏ về VPS
- [ ] SSL certificate đã cài, auto-renew đã test
- [ ] API và Frontend đã test qua HTTPS
- [ ] Backup database đã setup
- [ ] `DEBUG=false`
