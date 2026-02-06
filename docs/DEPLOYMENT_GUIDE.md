# Deployment Guide

## Overview

This guide covers deploying Finehance to production environments. The platform is designed for Docker-based deployment with optional cloud provider hosting.

**Note**: A production Docker Compose file (`docker-compose.prod.yml`) does not yet exist. The current `docker-compose.yml` is designed for development. See the [P5 roadmap](../roadmap/06_P5_PRODUCTION_HARDENING.md) for production deployment plans.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Configuration](#environment-configuration)
3. [Docker Deployment](#docker-deployment)
4. [Cloud Deployment](#cloud-deployment)
5. [Database Setup](#database-setup)
6. [Security Configuration](#security-configuration)
7. [Monitoring and Logging](#monitoring-and-logging)
8. [Backup and Recovery](#backup-and-recovery)
9. [Scaling](#scaling)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

**Minimum Requirements**:
- CPU: 2 cores
- RAM: 4 GB
- Storage: 20 GB
- OS: Linux (Ubuntu 20.04+ recommended)

**Recommended for Production**:
- CPU: 4+ cores
- RAM: 8+ GB
- Storage: 50+ GB SSD
- OS: Linux (Ubuntu 22.04 LTS)

### Software Requirements

- Docker 24.0+
- Docker Compose 2.20+
- PostgreSQL 16 (if not using Docker)
- Redis 7 (if not using Docker)
- Python 3.11+ (if not using Docker)

### Domain and SSL

- Domain name configured
- SSL certificate (Let's Encrypt recommended)
- DNS records pointing to your server

---

## Environment Configuration

### Environment Variables

Create a `.env` file in the project root with production values:

```bash
# Application
APP_NAME="AI Finance Platform"
APP_VERSION="1.0.0"
DEBUG=false
LOG_LEVEL=INFO
SECRET_KEY=<generate-strong-secret-key>
ENCRYPTION_KEY=<generate-strong-encryption-key>

# Database
DATABASE_URL=postgresql+asyncpg://username:password@postgres:5432/ai_finance_platform
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# Redis
REDIS_URL=redis://redis:6379/0
REDIS_MAX_CONNECTIONS=50

# CORS
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# JWT
JWT_SECRET_KEY=<generate-strong-jwt-secret>
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30

# Email (optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=noreply@yourdomain.com

# External APIs (optional)
PLAID_CLIENT_ID=your-plaid-client-id
PLAID_SECRET=your-plaid-secret
PLAID_ENV=production

# Monitoring (optional)
SENTRY_DSN=your-sentry-dsn
```

### Generating Secrets

Generate strong secrets for production:

```bash
# SECRET_KEY (32 bytes)
python -c "import secrets; print(secrets.token_urlsafe(32))"

# ENCRYPTION_KEY (32 bytes, base64 encoded)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# JWT_SECRET_KEY (64 bytes)
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

**IMPORTANT**: Never commit these secrets to version control!

---

## Docker Deployment

### Production Docker Compose

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    container_name: ai-finance-postgres
    restart: always
    environment:
      POSTGRES_DB: ai_finance_platform
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - backend
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: ai-finance-redis
    restart: always
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    networks:
      - backend
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: ai-finance-backend
    restart: always
    env_file:
      - .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - backend
      - frontend
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  nginx:
    image: nginx:alpine
    container_name: ai-finance-nginx
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
      - frontend_build:/usr/share/nginx/html:ro
    depends_on:
      - backend
    networks:
      - frontend

volumes:
  postgres_data:
  redis_data:
  frontend_build:

networks:
  backend:
  frontend:
```

### Production Dockerfile

Create `Dockerfile` (if not exists):

```dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry==1.7.1

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Run migrations and start application
CMD ["sh", "-c", "poetry run alembic upgrade head && poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

### Nginx Configuration

Create `nginx.conf`:

```nginx
events {
    worker_connections 1024;
}

http {
    upstream backend {
        server backend:8000;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

    server {
        listen 80;
        server_name yourdomain.com www.yourdomain.com;
        
        # Redirect HTTP to HTTPS
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name yourdomain.com www.yourdomain.com;

        # SSL Configuration
        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers on;

        # Security Headers
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;

        # Frontend
        location / {
            root /usr/share/nginx/html;
            try_files $uri $uri/ /index.html;
        }

        # API
        location /api {
            limit_req zone=api_limit burst=20 nodelay;
            
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # Timeouts
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }

        # Health check
        location /health {
            proxy_pass http://backend/health;
            access_log off;
        }
    }
}
```

### Deployment Steps

1. **Clone Repository**:
```bash
git clone https://github.com/cyberkunju/Finehance.git
cd ai-finance-platform
```

2. **Configure Environment**:
```bash
cp .env.example .env
# Edit .env with production values
nano .env
```

3. **Build and Start Services**:
```bash
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d
```

4. **Verify Deployment**:
```bash
docker-compose -f docker-compose.prod.yml ps
docker-compose -f docker-compose.prod.yml logs -f backend
```

5. **Check Health**:
```bash
curl http://localhost/health
```

---

## Cloud Deployment

### AWS Deployment

#### Using ECS (Elastic Container Service)

1. **Create ECR Repository**:
```bash
aws ecr create-repository --repository-name ai-finance-platform
```

2. **Build and Push Image**:
```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build image
docker build -t ai-finance-platform .

# Tag image
docker tag ai-finance-platform:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/ai-finance-platform:latest

# Push image
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/ai-finance-platform:latest
```

3. **Create RDS PostgreSQL Instance**:
```bash
aws rds create-db-instance \
    --db-instance-identifier ai-finance-db \
    --db-instance-class db.t3.medium \
    --engine postgres \
    --engine-version 16 \
    --master-username admin \
    --master-user-password <strong-password> \
    --allocated-storage 20 \
    --vpc-security-group-ids sg-xxxxx
```

4. **Create ElastiCache Redis**:
```bash
aws elasticache create-cache-cluster \
    --cache-cluster-id ai-finance-cache \
    --cache-node-type cache.t3.micro \
    --engine redis \
    --num-cache-nodes 1
```

5. **Create ECS Task Definition** (see AWS documentation)

6. **Create ECS Service** (see AWS documentation)

#### Using EC2

1. **Launch EC2 Instance** (Ubuntu 22.04 LTS, t3.medium or larger)

2. **SSH into Instance**:
```bash
ssh -i your-key.pem ubuntu@your-instance-ip
```

3. **Install Docker**:
```bash
sudo apt update
sudo apt install -y docker.io docker-compose
sudo usermod -aG docker ubuntu
```

4. **Deploy Application** (follow Docker deployment steps above)

### Google Cloud Platform (GCP)

#### Using Cloud Run

1. **Build and Push to Container Registry**:
```bash
gcloud builds submit --tag gcr.io/your-project-id/ai-finance-platform
```

2. **Deploy to Cloud Run**:
```bash
gcloud run deploy ai-finance-platform \
    --image gcr.io/your-project-id/ai-finance-platform \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --set-env-vars DATABASE_URL=<cloud-sql-url>,REDIS_URL=<redis-url>
```

3. **Create Cloud SQL PostgreSQL**:
```bash
gcloud sql instances create ai-finance-db \
    --database-version=POSTGRES_16 \
    --tier=db-f1-micro \
    --region=us-central1
```

4. **Create Memorystore Redis**:
```bash
gcloud redis instances create ai-finance-cache \
    --size=1 \
    --region=us-central1
```

### Azure

#### Using Azure Container Instances

1. **Create Resource Group**:
```bash
az group create --name ai-finance-rg --location eastus
```

2. **Create Container Registry**:
```bash
az acr create --resource-group ai-finance-rg --name aifinanceacr --sku Basic
```

3. **Build and Push Image**:
```bash
az acr build --registry aifinanceacr --image ai-finance-platform:latest .
```

4. **Create PostgreSQL Database**:
```bash
az postgres flexible-server create \
    --resource-group ai-finance-rg \
    --name ai-finance-db \
    --location eastus \
    --admin-user admin \
    --admin-password <strong-password> \
    --sku-name Standard_B1ms \
    --version 16
```

5. **Deploy Container**:
```bash
az container create \
    --resource-group ai-finance-rg \
    --name ai-finance-backend \
    --image aifinanceacr.azurecr.io/ai-finance-platform:latest \
    --dns-name-label ai-finance \
    --ports 8000 \
    --environment-variables DATABASE_URL=<postgres-url> REDIS_URL=<redis-url>
```

---

## Database Setup

### Running Migrations

After deployment, run database migrations:

```bash
# Using Docker
docker-compose -f docker-compose.prod.yml exec backend poetry run alembic upgrade head

# Or directly
poetry run alembic upgrade head
```

### Creating Initial Admin User

```bash
# Using Docker
docker-compose -f docker-compose.prod.yml exec backend poetry run python scripts/create_admin.py

# Or directly
poetry run python scripts/create_admin.py
```

### Database Backup

Set up automated backups:

```bash
# Create backup script
cat > /usr/local/bin/backup-db.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/ai_finance_$TIMESTAMP.sql.gz"

docker-compose -f /path/to/docker-compose.prod.yml exec -T postgres \
    pg_dump -U postgres ai_finance_platform | gzip > $BACKUP_FILE

# Keep only last 30 days
find $BACKUP_DIR -name "ai_finance_*.sql.gz" -mtime +30 -delete
EOF

chmod +x /usr/local/bin/backup-db.sh

# Add to crontab (daily at 2 AM)
echo "0 2 * * * /usr/local/bin/backup-db.sh" | crontab -
```

---

## Security Configuration

### SSL/TLS Setup

#### Using Let's Encrypt (Certbot)

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Auto-renewal (already configured by Certbot)
sudo certbot renew --dry-run
```

### Firewall Configuration

```bash
# Allow SSH, HTTP, HTTPS
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### Security Best Practices

1. **Change Default Passwords**: Update all default passwords
2. **Restrict Database Access**: Only allow backend to connect
3. **Enable Fail2Ban**: Protect against brute force attacks
4. **Regular Updates**: Keep system and dependencies updated
5. **Monitor Logs**: Set up log monitoring and alerts
6. **Backup Encryption**: Encrypt database backups
7. **API Rate Limiting**: Configure rate limits in Nginx

---

## Monitoring and Logging

### Application Logging

Logs are written to stdout/stderr and can be viewed with:

```bash
docker-compose -f docker-compose.prod.yml logs -f backend
```

### Centralized Logging (Optional)

#### Using ELK Stack

1. **Add Filebeat to Docker Compose**
2. **Configure Elasticsearch**
3. **Set up Kibana dashboards**

#### Using Cloud Logging

- **AWS**: CloudWatch Logs
- **GCP**: Cloud Logging
- **Azure**: Azure Monitor

### Monitoring Tools

#### Prometheus + Grafana

Add to `docker-compose.prod.yml`:

```yaml
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana
    volumes:
      - grafana_data:/var/lib/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

### Health Checks

Monitor application health:

```bash
# Health endpoint
curl https://yourdomain.com/health

# Database connectivity
docker-compose -f docker-compose.prod.yml exec postgres pg_isready

# Redis connectivity
docker-compose -f docker-compose.prod.yml exec redis redis-cli ping
```

---

## Backup and Recovery

### Automated Backups

1. **Database Backups**: Daily at 2 AM (see Database Setup)
2. **File Backups**: ML models, uploaded files
3. **Configuration Backups**: Environment files, configs

### Disaster Recovery

#### Database Restore

```bash
# Restore from backup
gunzip < backup.sql.gz | docker-compose -f docker-compose.prod.yml exec -T postgres \
    psql -U postgres ai_finance_platform
```

#### Full System Restore

1. Provision new server
2. Install Docker and dependencies
3. Clone repository
4. Restore environment files
5. Restore database backup
6. Start services

---

## Scaling

### Horizontal Scaling

#### Load Balancer Setup

Use Nginx or cloud load balancers to distribute traffic across multiple backend instances.

#### Database Scaling

- **Read Replicas**: For read-heavy workloads
- **Connection Pooling**: Use PgBouncer
- **Partitioning**: Partition large tables by user_id or date

#### Redis Scaling

- **Redis Cluster**: For high availability
- **Redis Sentinel**: For automatic failover

### Vertical Scaling

Increase resources as needed:
- CPU: 2 → 4 → 8 cores
- RAM: 4 → 8 → 16 GB
- Storage: Add more disk space

---

## Troubleshooting

### Common Issues

#### Application Won't Start

```bash
# Check logs
docker-compose -f docker-compose.prod.yml logs backend

# Common causes:
# - Database connection failed
# - Missing environment variables
# - Port already in use
```

#### Database Connection Errors

```bash
# Test database connectivity
docker-compose -f docker-compose.prod.yml exec postgres pg_isready

# Check connection string in .env
# Verify database credentials
```

#### High Memory Usage

```bash
# Check container stats
docker stats

# Increase memory limits in docker-compose.yml
# Optimize database queries
# Enable Redis caching
```

#### Slow API Responses

```bash
# Check database query performance
# Enable query logging
# Add database indexes
# Increase connection pool size
```

### Getting Help

- **Swagger UI**: `http://localhost:8000/docs` (interactive API docs)
- **GitHub Issues**: [github.com/cyberkunju/Finehance/issues](https://github.com/cyberkunju/Finehance/issues)
- **Project Docs**: See `docs/` directory in the repository

---

## Maintenance

### Regular Tasks

**Daily**:
- Monitor logs for errors
- Check system resources
- Verify backups completed

**Weekly**:
- Review security alerts
- Check application performance
- Update dependencies (if needed)

**Monthly**:
- Security patches
- Database optimization
- Review and rotate logs

**Quarterly**:
- Disaster recovery drill
- Security audit
- Performance optimization

---

## Conclusion

You now have a production-ready deployment of the AI Finance Platform. Remember to:

- Keep secrets secure
- Monitor application health
- Maintain regular backups
- Stay updated with security patches
- Scale as your user base grows

For additional support, open an issue on [GitHub](https://github.com/cyberkunju/Finehance/issues).

---

**Version**: 1.0.0  
**Last Updated**: February 6, 2026
