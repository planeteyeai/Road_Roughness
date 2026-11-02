# 🚀 Railway Deployment - Quick Start

## Step-by-Step Method

### 1. Prepare Google Earth Engine Service Account

```
1. Go to: https://console.cloud.google.com
2. Create/Select a project
3. IAM & Admin → Service Accounts → CREATE SERVICE ACCOUNT
4. Name: railway-road-roughness → CREATE AND CONTINUE → DONE
5. Click the service account → KEYS → ADD KEY → Create new key
6. Choose JSON → CREATE → Download the file
7. Go to: https://code.earthengine.google.com
8. Register the service account email (from the JSON file)
```

### 2. Push Code to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### 3. Deploy on Railway

```
1. Go to: https://railway.app
2. Sign in with GitHub
3. Click: New Project
4. Select: Deploy from GitHub repo
5. Choose your repository
6. Wait for Railway to detect the Dockerfile
```

### 4. Set Environment Variables

Click your service → **Variables** → **Raw Editor**, paste this:

```env
GEE_PROJECT=YOUR_GEE_PROJECT_ID
GEE_SERVICE_ACCOUNT_JSON=PASTE_YOUR_SERVICE_ACCOUNT_JSON_HERE
RR_HOST=0.0.0.0
RR_PORT=8000
CORS_ORIGINS=*
SERVE_FRONTEND=true
KEEP_ONLY_LATEST_PROJECT=true
DEFAULT_CLOUD_PCT=40
NDWI_WORKERS=4
```

**Important**: 
- Replace `YOUR_GEE_PROJECT_ID` with your Google Cloud project ID
- Open the downloaded service account JSON file, copy ALL of its content
- Replace `PASTE_YOUR_SERVICE_ACCOUNT_JSON_HERE` with the full JSON

### 5. Add Storage Volume (Optional)

```
Variables tab → New Volume
Mount Path: /app/road_roughness/backend/storage
Size: 1GB (or more if needed)
```

### 6. Deploy & Access

```
Railway deploys automatically!

Get your URL:
Settings → Domains → Copy the Railway-provided URL

Access your app:
https://your-app-name.up.railway.app
```

---

## ✅ Verification Checklist

After deployment, verify:

- [ ] App URL opens without errors
- [ ] API endpoint responds: `https://your-app.up.railway.app/api/config`
- [ ] Frontend loads the map interface
- [ ] No errors in Railway logs
- [ ] Health check passes (Railway shows "Healthy")

---

## 🧪 Test Locally First (Optional)

Before deploying to Railway, test locally with Docker:

```bash
# 1. Copy environment template
cp .env.docker.example .env

# 2. Edit with your credentials
nano .env

# 3. Build and run
docker-compose up

# 4. Open browser
http://localhost:8000
```

---

## 🐛 Common Issues & Fixes

### Issue: Build fails on Railway
**Fix**: Check Dockerfile is in repository root, commit all files

### Issue: App starts then crashes
**Fix**: Check Railway logs, verify GEE_SERVICE_ACCOUNT_JSON is complete

### Issue: Earth Engine authentication error
**Fix**: 
1. Verify service account email is registered at code.earthengine.google.com
2. Enable Earth Engine API in Google Cloud Console
3. Check GEE_PROJECT matches your Google Cloud project ID

### Issue: Can't upload KML files
**Fix**: Add a storage volume (see Step 5)

---

## 📊 What Happens Next

After successful deployment:

1. **First Request**: May take 30-60 seconds (cold start)
2. **Subsequent Requests**: Fast response
3. **Auto-scaling**: Railway scales based on traffic
4. **Auto-sleep**: Free tier sleeps after inactivity

---

## 💰 Cost Estimate

### Railway Free Tier
- $5 credit per month
- Good for: Testing, light usage
- Limitations: Sleeps after inactivity

### Railway Hobby Plan ($5/month)
- Better for: Regular use
- No sleep
- 500GB bandwidth

### Typical Usage Costs
- Small project: ~$5-10/month
- Medium project: ~$10-20/month
- Storage: ~$0.000463/GB-hour

---

## 🔐 Security Tips

1. ✅ Never commit `.env` or JSON key files
2. ✅ Use Railway environment variables only
3. ✅ Change `CORS_ORIGINS` from `*` to your domain in production
4. ✅ Use service accounts (not personal credentials)
5. ✅ Regularly review Railway access logs

---

## 📞 Support

**Railway Issues**:
- Discord: https://discord.gg/railway
- Docs: https://docs.railway.app

**Earth Engine Issues**:
- Forum: https://groups.google.com/g/google-earth-engine-developers
- Docs: https://developers.google.com/earth-engine

**App Issues**:
- Check Railway logs first
- Test locally with Docker to isolate issue

---

## ⏭️ Next Steps

After deployment:

1. **Custom Domain**: Railway Settings → Domains → Add custom domain
2. **CI/CD**: Auto-deploy on git push (enabled by default)
3. **Monitoring**: Check Railway Metrics tab regularly
4. **Backups**: Download project data from storage volume periodically
5. **Production**: Update `CORS_ORIGINS` to your domain

---

**🎉 Congratulations! Your Road Roughness Platform is now live on Railway!**

Access your app at: `https://your-app.up.railway.app`
