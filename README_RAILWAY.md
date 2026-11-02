# 🚂 Deploy to Railway in 5 Minutes

## Prerequisites
- GitHub account with this code pushed
- Railway account ([railway.app](https://railway.app))
- Google Earth Engine service account JSON

---

## 🚀 Deployment Steps

### 1️⃣ Create Railway Project

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new)

1. Click "Deploy on Railway" or go to [railway.app](https://railway.app)
2. **New Project** → **Deploy from GitHub repo**
3. Select this repository
4. Railway detects Dockerfile automatically ✅

### 2️⃣ Set Environment Variables

Click on your service → **Variables** tab → **Raw Editor** and paste:

```env
GEE_PROJECT=your-gee-project-id
GEE_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"...","private_key":"..."}
RR_HOST=0.0.0.0
RR_PORT=8000
CORS_ORIGINS=*
SERVE_FRONTEND=true
```

**Replace** `GEE_PROJECT` and `GEE_SERVICE_ACCOUNT_JSON` with your values.

### 3️⃣ Add Persistent Storage (Recommended)

1. **Variables** tab → **New Volume**
2. Mount Path: `/app/road_roughness/backend/storage`
3. Size: Start with 1GB

### 4️⃣ Deploy

Railway deploys automatically! ⚡

Get your URL: **Settings** → **Domains** → Copy the Railway URL

### 5️⃣ Test

Open: `https://your-app.up.railway.app`

---

## 🔑 Get Google Earth Engine Service Account

### Quick Steps:

1. **Create GCP Project**: [console.cloud.google.com](https://console.cloud.google.com)

2. **Create Service Account**:
   - IAM & Admin → Service Accounts → Create Service Account
   - Name: `railway-road-roughness`
   - Create → Done

3. **Generate Key**:
   - Click service account → Keys → Add Key → Create new key
   - Choose JSON → Download

4. **Register with Earth Engine**:
   - Go to [code.earthengine.google.com](https://code.earthengine.google.com)
   - Assets → Register service account email

5. **Copy JSON to Railway**:
   - Open downloaded JSON file
   - Copy entire content
   - Paste into `GEE_SERVICE_ACCOUNT_JSON` variable in Railway

---

## 🐳 Test Locally with Docker

```bash
# Copy environment template
cp .env.docker.example .env

# Edit .env with your credentials
nano .env

# Build and run
docker-compose up

# Open browser
open http://localhost:8000
```

---

## 📊 Monitor Your Deployment

### Railway Dashboard
- **Logs**: Real-time application logs
- **Metrics**: CPU, Memory, Network usage
- **Deployments**: Build and deploy history

### Health Check
Your app includes automatic health checks at `/api/config`

---

## 🔧 Troubleshooting

### ❌ Build Failed
Check **Deployments** → View logs
- Ensure Dockerfile is in repository root
- Verify all files are committed

### ❌ App Crashes
Check **Logs** tab
- Verify `GEE_PROJECT` matches your GCP project
- Ensure service account JSON is complete (not truncated)
- Check service account is registered with Earth Engine

### ❌ Earth Engine Error
```
Error: Earth Engine could not start
```
**Fix**:
1. Register service account at [code.earthengine.google.com](https://code.earthengine.google.com)
2. Enable Earth Engine API in Google Cloud Console
3. Verify JSON credentials are complete

### ❌ Storage Not Persisting
Add a volume (see Step 3 above) or set:
```env
KEEP_ONLY_LATEST_PROJECT=true
```

---

## 💰 Pricing

### Railway
- **Starter**: $5 free credit/month
- **Developer**: $5/month + usage
- **Usage**: ~$0.000463/GB-hour for storage

### Tips to Save
- Use `KEEP_ONLY_LATEST_PROJECT=true`
- Lower `NDWI_WORKERS` (default: 4)
- Add volume only if needed

---

## ⚙️ Configuration Reference

### Required Variables
| Variable | Description | Example |
|----------|-------------|---------|
| `GEE_PROJECT` | Google Earth Engine project ID | `my-project-123` |
| `GEE_SERVICE_ACCOUNT_JSON` | Service account credentials | `{"type":"service_account",...}` |

### Optional Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `RR_HOST` | `0.0.0.0` | Server host |
| `RR_PORT` | `8000` | Server port |
| `CORS_ORIGINS` | `*` | Allowed origins |
| `SERVE_FRONTEND` | `true` | Serve web UI |
| `KEEP_ONLY_LATEST_PROJECT` | `true` | Auto-cleanup old projects |
| `DEFAULT_CLOUD_PCT` | `40` | Sentinel-2 cloud threshold |
| `NDWI_WORKERS` | `4` | Parallel downloads |
| `NEAREST_SEARCH_DAYS` | `90` | Search window for images |

---

## 🔒 Security Checklist

- ✅ Never commit `.env` files
- ✅ Use Railway variables for secrets
- ✅ Set specific `CORS_ORIGINS` in production
- ✅ Use service accounts (not personal auth)
- ✅ Enable HTTPS (Railway default)
- ✅ Review access logs regularly

---

## 📚 Resources

- [Railway Documentation](https://docs.railway.app)
- [Docker Documentation](https://docs.docker.com)
- [Earth Engine Docs](https://developers.google.com/earth-engine)
- [FastAPI Docs](https://fastapi.tiangolo.com)

---

## 🆘 Need Help?

- Railway Discord: [discord.gg/railway](https://discord.gg/railway)
- Railway Support: support@railway.app
- Earth Engine Forum: [Google Groups](https://groups.google.com/g/google-earth-engine-developers)

---

**🎉 That's it! Your Road Roughness Platform is now live on Railway!**
