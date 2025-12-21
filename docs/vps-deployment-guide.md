# VPS Deployment Guide - Stock Massive

Hướng dẫn chi tiết deploy Stock Massive lên VPS cho người mới bắt đầu.

---

## Bước 1: Thuê VPS

### Các nhà cung cấp phổ biến

| Provider | Giá từ | Ghi chú |
|----------|--------|---------|
| DigitalOcean | $6/tháng | Dễ dùng, nhiều tutorial |
| Vultr | $5/tháng | Nhiều location châu Á |
| Linode | $5/tháng | Ổn định |
| AWS Lightsail | $5/tháng | Thuộc Amazon |
| Contabo | €4.99/tháng | Giá rẻ, cấu hình cao |

### Cấu hình tối thiểu khuyến nghị

- **CPU**: 2 vCPU
- **RAM**: 4GB (tối thiểu 2GB)
- **Storage**: 50GB SSD
- **OS**: Ubuntu 22.04 LTS

---

## Bước 2: Kết nối VPS

### 2.1 Trên Windows - Dùng PowerShell hoặc Terminal

```bash
ssh root@your-vps-ip
# Nhập password được cấp qua email
```

### 2.2 Trên Mac/Linux

```bash
ssh root@your-vps-ip
```

### 2.3 Tạo user mới (bảo mật hơn dùng root)

```bash
# Tạo user mới
adduser deploy
# Nhập password và thông tin

# Cấp quyền sudo
usermod -aG sudo deploy

# Chuyển sang user mới
su - deploy
```

---

## Bước 3: Cài đặt Docker

### 3.1 Cập nhật hệ thống

```bash
sudo apt update && sudo apt upgrade -y
```

### 3.2 Cài Docker

```bash
# Cài các package cần thiết
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common

# Thêm Docker GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Thêm Docker repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Cài Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Cho phép user chạy docker không cần sudo
sudo usermod -aG docker $USER

# Áp dụng thay đổi (hoặc logout rồi login lại)
newgrp docker
```

### 3.3 Kiểm tra Docker

```bash
docker --version
# Docker version 24.x.x

docker compose version
# Docker Compose version v2.x.x
```

---

## Bước 4: Cài đặt Git và Clone Project

### 4.1 Cài Git

```bash
sudo apt install -y git
```

### 4.2 Clone repository

```bash
# Tạo thư mục cho ứng dụng
mkdir -p ~/apps
cd ~/apps

# Clone project (thay bằng URL repo của bạn)
git clone https://github.com/your-username/Stock_Massive.git
cd Stock_Massive
```

---

## Bước 5: Cấu hình Environment

### 5.1 Tạo file .env

```bash
# Copy template
cp .env.example .env

# Mở file để chỉnh sửa
nano .env
```

### 5.2 Chỉnh sửa các giá trị quan trọng

```bash
# ========================================
# Stock Massive - Docker Environment
# ========================================

# Database - ĐẶT PASSWORD MẠNH!
DB_USER=postgres
DB_PASSWORD=MyStr0ngP@ssword123!   # <-- Đổi password này
DB_NAME=stockmassive

# API - TẠO SECRET NGẪU NHIÊN
AUTH_SECRET=abc123xyz...           # <-- Tạo bằng lệnh bên dưới

# CORS - Domain của bạn
CORS_ORIGINS=https://yourdomain.com

# Frontend
NEXT_PUBLIC_API_URL=https://api.yourdomain.com/api/v1

# ... các biến khác giữ nguyên hoặc điền nếu cần
```

### 5.3 Tạo AUTH_SECRET ngẫu nhiên

```bash
# Chạy lệnh này để tạo secret
openssl rand -base64 32
# Copy kết quả và paste vào AUTH_SECRET trong .env
```

### 5.4 Lưu file

```bash
# Trong nano:
# Ctrl + O -> Enter (lưu)
# Ctrl + X (thoát)
```

---

## Bước 6: Build và Chạy Docker

### 6.1 Build images

```bash
# Build tất cả services (lần đầu mất 5-10 phút)
docker compose -f docker-compose.prod.yml build
```

### 6.2 Khởi động services

```bash
# Chạy ở background (-d = detached)
docker compose -f docker-compose.prod.yml up -d
```

### 6.3 Kiểm tra trạng thái

```bash
# Xem các container đang chạy
docker compose -f docker-compose.prod.yml ps

# Kết quả mong đợi:
# NAME                 STATUS
# stockmassive-db      Up (healthy)
# stockmassive-api     Up
# stockmassive-web     Up
```

### 6.4 Xem logs nếu có lỗi

```bash
# Xem logs tất cả services
docker compose -f docker-compose.prod.yml logs

# Xem logs của service cụ thể
docker compose -f docker-compose.prod.yml logs api
docker compose -f docker-compose.prod.yml logs web
docker compose -f docker-compose.prod.yml logs db

# Xem logs realtime (follow)
docker compose -f docker-compose.prod.yml logs -f
```

---

## Bước 7: Cài đặt Nginx Reverse Proxy

### 7.1 Cài Nginx

```bash
sudo apt install -y nginx
```

### 7.2 Tạo config cho Stock Massive

```bash
sudo nano /etc/nginx/sites-available/stockmassive
```

### 7.3 Paste nội dung sau

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

### 7.4 Kích hoạt config

```bash
# Tạo symlink
sudo ln -s /etc/nginx/sites-available/stockmassive /etc/nginx/sites-enabled/

# Xóa default config (optional)
sudo rm /etc/nginx/sites-enabled/default

# Kiểm tra syntax
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

---

## Bước 8: Cài SSL Certificate (HTTPS)

### 8.1 Cài Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
```

### 8.2 Lấy SSL certificate

```bash
# Cho cả frontend và API (thay domain của bạn)
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com -d api.yourdomain.com
```

### 8.3 Certbot sẽ hỏi:
- Email: Nhập email của bạn
- Terms: Nhấn A (Agree)
- Share email: Nhấn N (No)
- Redirect HTTP to HTTPS: Nhấn 2 (Yes)

### 8.4 Tự động renew certificate

```bash
# Test auto-renew
sudo certbot renew --dry-run
```

---

## Bước 9: Cấu hình Domain DNS

Vào panel quản lý domain của bạn, thêm các DNS records:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | @ | your-vps-ip | 3600 |
| A | www | your-vps-ip | 3600 |
| A | api | your-vps-ip | 3600 |

---

## Bước 10: Kiểm tra Deployment

### 10.1 Kiểm tra từ browser

```
https://yourdomain.com        -> Frontend
https://api.yourdomain.com    -> API (sẽ thấy {"detail":"Not Found"})
https://api.yourdomain.com/docs -> Swagger API docs
```

### 10.2 Kiểm tra từ terminal

```bash
# Kiểm tra API health
curl https://api.yourdomain.com/health

# Kiểm tra API endpoint
curl https://api.yourdomain.com/api/v1/stocks/symbols
```

---

## Các lệnh Docker thường dùng

### Quản lý containers

```bash
# Xem containers đang chạy
docker compose -f docker-compose.prod.yml ps

# Dừng tất cả
docker compose -f docker-compose.prod.yml stop

# Khởi động lại
docker compose -f docker-compose.prod.yml start

# Restart
docker compose -f docker-compose.prod.yml restart

# Dừng và xóa containers (giữ data)
docker compose -f docker-compose.prod.yml down

# Dừng và xóa cả data (CẢNH BÁO: mất hết database!)
docker compose -f docker-compose.prod.yml down -v
```

### Xem logs

```bash
# Logs realtime
docker compose -f docker-compose.prod.yml logs -f

# Logs 100 dòng cuối
docker compose -f docker-compose.prod.yml logs --tail=100

# Logs của service cụ thể
docker compose -f docker-compose.prod.yml logs api
```

### Vào trong container

```bash
# Vào container API
docker compose -f docker-compose.prod.yml exec api bash

# Vào container database
docker compose -f docker-compose.prod.yml exec db psql -U postgres -d stockmassive

# Chạy migration thủ công
docker compose -f docker-compose.prod.yml exec api alembic upgrade head
```

### Update code mới

```bash
cd ~/apps/Stock_Massive

# Pull code mới từ git
git pull origin main

# Rebuild và restart
docker compose -f docker-compose.prod.yml up -d --build

# Hoặc chỉ rebuild service cụ thể
docker compose -f docker-compose.prod.yml up -d --build api
docker compose -f docker-compose.prod.yml up -d --build web
```

---

## Backup Database

### Tạo backup

```bash
# Backup database ra file
docker compose -f docker-compose.prod.yml exec db pg_dump -U postgres stockmassive > backup_$(date +%Y%m%d).sql
```

### Restore từ backup

```bash
# Restore database từ file
docker compose -f docker-compose.prod.yml exec -T db psql -U postgres stockmassive < backup_20241221.sql
```

### Tự động backup hàng ngày

```bash
# Tạo script backup
nano ~/backup-db.sh
```

```bash
#!/bin/bash
BACKUP_DIR=~/backups
mkdir -p $BACKUP_DIR
cd ~/apps/Stock_Massive
docker compose -f docker-compose.prod.yml exec -T db pg_dump -U postgres stockmassive > $BACKUP_DIR/backup_$(date +%Y%m%d_%H%M%S).sql
# Xóa backup cũ hơn 7 ngày
find $BACKUP_DIR -name "backup_*.sql" -mtime +7 -delete
```

```bash
# Cấp quyền chạy
chmod +x ~/backup-db.sh

# Thêm vào crontab (chạy lúc 3:00 AM mỗi ngày)
crontab -e
# Thêm dòng:
0 3 * * * /home/deploy/backup-db.sh
```

---

## Troubleshooting

### Container không chạy

```bash
# Xem logs để tìm lỗi
docker compose -f docker-compose.prod.yml logs api

# Kiểm tra .env đã đúng chưa
cat .env

# Rebuild lại
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d --build
```

### Database connection error

```bash
# Kiểm tra db container
docker compose -f docker-compose.prod.yml ps db

# Xem logs db
docker compose -f docker-compose.prod.yml logs db

# Kiểm tra DATABASE_URL trong .env
```

### Port đã được sử dụng

```bash
# Xem port nào đang dùng
sudo lsof -i :3000
sudo lsof -i :8000

# Kill process nếu cần
sudo kill -9 <PID>
```

### Hết dung lượng disk

```bash
# Kiểm tra disk usage
df -h

# Xóa docker images không dùng
docker system prune -a

# Xóa logs cũ
docker compose -f docker-compose.prod.yml logs --tail=0
```

---

## Checklist trước khi live

- [ ] Đã đổi DB_PASSWORD mạnh
- [ ] Đã tạo AUTH_SECRET ngẫu nhiên
- [ ] Đã cấu hình CORS_ORIGINS đúng domain
- [ ] Đã cấu hình DNS trỏ về VPS
- [ ] Đã cài SSL certificate
- [ ] Đã test API hoạt động
- [ ] Đã test Frontend hoạt động
- [ ] Đã setup backup database
- [ ] Đã tắt DEBUG mode

---

## Liên hệ hỗ trợ

Nếu gặp vấn đề:
1. Kiểm tra logs: `docker compose -f docker-compose.prod.yml logs`
2. Google error message
3. Tạo issue trên GitHub repository
