# Flooding Target Setup

If you plan to use the traffic generation features, set up the following targets.

## 1) Firewall Rules

Open necessary ports using PowerShell:

```powershell
New-NetFirewallRule -DisplayName "Allow HTTP Stress Test" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow
New-NetFirewallRule -DisplayName "Allow HTTPS Stress Test" -Direction Inbound -Protocol TCP -LocalPort 443 -Action Allow
New-NetFirewallRule -DisplayName "Allow UDP 8080 Stress Test" -Direction Inbound -Protocol UDP -LocalPort 8080 -Action Allow
New-NetFirewallRule -DisplayName "Allow FTP Stress Test" -Direction Inbound -Protocol TCP -LocalPort 21 -Action Allow
New-NetFirewallRule -DisplayName "Allow FTPS Stress Test" -Direction Inbound -Protocol TCP -LocalPort 990 -Action Allow
New-NetFirewallRule -DisplayName "Allow SFTP Stress Test" -Direction Inbound -Protocol TCP -LocalPort 2222 -Action Allow
```

## 2) HTTP Server (Port 80)

```cmd
python tool/run_http_server.py --port 80 --directory .
```

* Press **ESC** to stop the server gracefully.

## 3) HTTPS Server (Port 443)

```cmd
python tool/run_https_server.py --port 443 --directory .
```

* Auto-generates self-signed `cert.pem` and `key.pem` if missing.
* Press **ESC** to stop the server gracefully.

## 4) UDP Server (Port 8080)

```cmd
python tool/run_udp_server.py --port 8080
```

* Press **ESC** to stop the server gracefully.

## 5) FTP/FTPS Server

```cmd
python tool/run_ftp_server.py --port 21 --user test --password password
python tool/run_ftp_server.py --port 990 --ftps --user test --password password
```

* Supports "Blackhole" mode (discards uploads to save disk space).
* FTPS mode auto-generates self-signed certificates.
* Press **ESC** to stop the server gracefully.

## 6) SFTP Server

```cmd
python tool/run_sftp_server.py --port 2222 --user test --password password
```

* Uses `paramiko` to run a stub SFTP server.
* Press **ESC** to stop the server gracefully.