# DigitalOcean Deployment Guide

This guide details how to deploy BIMCalc to a DigitalOcean Droplet using Docker Compose.

## Prerequisites

- A DigitalOcean account.
- A registered domain name (optional, but recommended for SSL).
- SSH key pair for secure access.

## 1. Create a Droplet

1.  **Log in** to your DigitalOcean Control Panel.
2.  Click **Create** -> **Droplets**.
3.  **Choose Region**: Select a region closest to your users (e.g., London, New York).
4.  **Choose Image**: Select **Marketplace** -> **Docker** (this comes with Docker and Docker Compose pre-installed on Ubuntu).
5.  **Choose Size**:
    - **Minimum**: Basic Droplet, Regular Intel with SSD.
    - **RAM**: At least **4GB** is recommended due to the AI/ML components (pgvector, embeddings). 2GB might work with swap but is risky.
    - **CPU**: 2 vCPUs recommended.
6.  **Authentication**: Select **SSH Key** and upload your public key.
7.  **Hostname**: Give your droplet a meaningful name (e.g., `bimcalc-staging`).
8.  Click **Create Droplet**.

## 2. Initial Server Setup

1.  **SSH into your droplet**:
    ```bash
    ssh root@<DROPLET_IP_ADDRESS>
    ```

2.  **Update the system**:
    ```bash
    apt-get update && apt-get upgrade -y
    ```

3.  **Set up a firewall (UFW)**:
    ```bash
    ufw allow OpenSSH
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw enable
    ```

## 3. Application Deployment (Automated)

We have provided a `deploy.sh` script to automate the file transfer and setup.

1.  **Run the deployment script**:
    From your local machine (where this repo is):
    ```bash
    ./deploy.sh root@<DROPLET_IP_ADDRESS>
    ```
    *Example: `./deploy.sh root@192.0.2.1`*

    This script will:
    - Connect to your Droplet via SSH.
    - Install Docker if it's missing.
    - Copy all necessary configuration files and source code.
    - Build and start the application containers.

2.  **Verify Status**:
    SSH into the server to check logs if needed:
    ```bash
    ssh root@<DROPLET_IP_ADDRESS>
    cd /opt/bimcalc
    docker compose logs -f app
    ```

## 4. SSL Configuration (Manual Step)

For a production-grade setup, you should serve the application over HTTPS.

1.  **Point your domain**: Add an A record in your DNS provider pointing to your Droplet's IP.

2.  **Install Nginx and Certbot**:
    ```bash
    apt-get install -y nginx certbot python3-certbot-nginx
    ```

3.  **Configure Nginx**:
    Create a new config file `/etc/nginx/sites-available/bimcalc`:
    ```nginx
    server {
        server_name yourdomain.com;

        location / {
            proxy_pass http://localhost:80; # Maps to port 80 exposed by docker-compose.prod.yml
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
    ```

4.  **Enable the site**:
    ```bash
    ln -s /etc/nginx/sites-available/bimcalc /etc/nginx/sites-enabled/
    rm /etc/nginx/sites-enabled/default
    nginx -t
    systemctl restart nginx
    ```

5.  **Obtain SSL Certificate**:
    ```bash
    certbot --nginx -d yourdomain.com
    ```

## 5. Maintenance

-   **Updates**:
    ```bash
    cd /opt/bimcalc
    git pull
    docker compose -f docker-compose.prod.yml up -d --build
    ```

-   **Backups**:
    Regularly backup the `db_data` volume or use a managed database service.
