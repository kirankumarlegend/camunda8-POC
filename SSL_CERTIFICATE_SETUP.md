# SSL Certificate Setup for MCP Server

## 🔐 Problem

The MCP server uses a self-signed certificate, causing SSL verification errors:
```
[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate in certificate chain
```

## ✅ Solutions

### Option 1: Use the Certificate (Recommended for Production)

#### Step 1: Download the Certificate

**Method A - Automatic (using openssl):**
```bash
cd /Users/n0c082s/Documents/repo/metamorphosis/Camunda8/camunda8-POC
./setup_mcp_cert.sh
```

**Method B - Manual (using browser):**
1. Visit https://cbs-content-mcp-server.cbs-mcp.dev.k8s.walmart.net in Chrome/Safari
2. Click the lock icon in address bar
3. Click "Certificate" → "Details" → "Export"
4. Save as `certs/mcp-server.crt`

**Method C - Using openssl command:**
```bash
mkdir -p certs
openssl s_client -showcerts -connect cbs-content-mcp-server.cbs-mcp.dev.k8s.walmart.net:443 </dev/null 2>/dev/null | \
  openssl x509 -outform PEM > certs/mcp-server.crt
```

#### Step 2: Configure Environment

Set the certificate path:
```bash
export MCP_SERVER_CERT_PATH=/Users/n0c082s/Documents/repo/metamorphosis/Camunda8/camunda8-POC/certs/mcp-server.crt
export MCP_SERVER_VERIFY_SSL=true
```

Or add to `.env` file:
```bash
MCP_SERVER_CERT_PATH=/Users/n0c082s/Documents/repo/metamorphosis/Camunda8/camunda8-POC/certs/mcp-server.crt
MCP_SERVER_VERIFY_SSL=true
```

#### Step 3: Restart the Worker

```bash
python3 workers/mds_evaluation_worker_real.py
```

---

### Option 2: Disable SSL Verification (Quick Fix for Development)

⚠️ **NOT recommended for production!**

```bash
# Set environment variable
export MCP_SERVER_VERIFY_SSL=false

# Start the worker
python3 workers/mds_evaluation_worker_real.py
```

Or add to `.env`:
```bash
MCP_SERVER_VERIFY_SSL=false
```

---

## 🚀 Quick Start (Development)

For immediate testing, disable SSL verification:

```bash
cd /Users/n0c082s/Documents/repo/metamorphosis/Camunda8/camunda8-POC

# Disable SSL verification for this session
export MCP_SERVER_VERIFY_SSL=false

# Start the worker
python3 workers/mds_evaluation_worker_real.py
```

In another terminal:
```bash
cd /Users/n0c082s/Documents/repo/metamorphosis/Camunda8/camunda8-POC

# Submit workflow
python3 workflows/start_mds_evaluation.py \
  /Users/n0c082s/Downloads/OneDrive_1_2-10-2026/7688663-9169-NULL-IAB-STANDARD-BANNERS-LAST-MINUTE-GIFTS-FY26-XCAT-EXGT-XCAT-DNAD-300x250-NULL-GM-EL-25011430133PWW1073.jpg \
  /Users/n0c082s/Downloads/OneDrive_1_2-10-2026/7688663-9175-NULL-IAB-STANDARD-BANNERS-LAST-MINUTE-GIFTS-FY26-XCAT-EXGT-XCAT-DNAD-300x250-NULL-GM-EL-25011430133PWW1065.jpg
```

---

## 🔍 Verify Certificate Installation

Check if certificate is valid:
```bash
openssl x509 -in certs/mcp-server.crt -text -noout
```

Test connection with certificate:
```bash
curl --cacert certs/mcp-server.crt https://cbs-content-mcp-server.cbs-mcp.dev.k8s.walmart.net/health
```

---

## 📝 Environment Variables Reference

| Variable | Description | Example |
|----------|-------------|---------|
| `MCP_SERVER_CERT_PATH` | Path to SSL certificate | `/path/to/certs/mcp-server.crt` |
| `MCP_SERVER_VERIFY_SSL` | Enable/disable SSL verification | `true` or `false` |

---

## 🐛 Troubleshooting

### Certificate Not Found
```
Error: [Errno 2] No such file or directory: 'certs/mcp-server.crt'
```
**Solution:** Ensure certificate path is absolute or relative to worker directory

### Certificate Expired
```
Error: certificate verify failed: certificate has expired
```
**Solution:** Download a fresh certificate from the server

### Still Getting SSL Errors
```
Error: [SSL: CERTIFICATE_VERIFY_FAILED]
```
**Solutions:**
1. Verify certificate path is correct
2. Check certificate is in PEM format
3. Try disabling SSL verification for testing
4. Contact CBS Platform team for updated certificate

---

## 📚 Additional Resources

- **httpx SSL docs**: https://www.python-httpx.org/advanced/#ssl-certificates
- **OpenSSL certificate guide**: https://www.openssl.org/docs/
