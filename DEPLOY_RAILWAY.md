# Railway Deployment Guide - Docker Method

## Quick Start (5 Steps)

### 1. Push Your Code to GitHub

```bash
git add .
git commit -m "Prepare for Railway deployment"
git push origin main
```

### 2. Create Railway Project

1. Go to [railway.app](https://railway.app) and sign in
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose your repository
5. Railway will auto-detect the Dockerfile

### 3. Set Environment Variables

In Railway dashboard → **Variables** tab, add:

```env
# Required
GEE_PROJECT=your-gee-project-id
GEE_SERVICE_ACCOUNT_JSON={"paste":"your","service":"account","json":"here"}

# Optional (defaults work fine)
RR_HOST=0.0.0.0
RR_PORT=8000
CORS_ORIGINS=*
SERVE_FRONTEND=true
DEFAULT_CLOUD_PCT=40
NDWI_WORKERS=4
```

**Important**: For `GEE_SERVICE_ACCOUNT_JSON`, copy the entire JSON content from your Google Cloud service account key file.

### 4. Add Persistent Storage (Optional but Recommended)

1. In Railway dashboard → Your service
2. **Variables** tab → **New Volume**
3. Mount path: `/app/road_roughness/backend/storage`
4. This keeps project data between deployments

### 5. Deploy

Railway deploys automatically. Get your URL from the **Settings** tab.

Your app will be at: `https://your-app.up.railway.app`

---

## Getting Google Earth Engine Service Account

### Step 1: Create Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Select your project (or create one)
3. **IAM & Admin** → **Service Accounts**
4. **Create Service Account**
   - Name: `railway-road-roughness`
   - Click **Create and Continue**
   - Skip role assignment (optional)
   - Click **Done**

### Step 2: Create Key

1. Click on the service account you just created
2. **Keys** tab → **Add Key** → **Create new key**
3. Choose **JSON** format
4. Download the JSON file

### Step 3: Register with Earth Engine

1. Go to [Earth Engine](https://code.earthengine.google.com)
2. Click on **Assets** tab
3. Register the service account email (from the JSON file)
   - Or use this URL: `https://code.earthengine.google.com/register`
   - Add the service account email as a writer

### Step 4: Copy JSON to Railway

1. Open the downloaded JSON file
2. Copy the **entire content**
3. In Railway, create variable: `GEE_SERVICE_ACCOUNT_JSON`
4. Paste the JSON content as the value

---

## Test Locally with Docker

Build the image:
```bash
docker build -t road-roughness .
```

Run with environment variables:
```bash
docker run -p 8000:8000 \
  -e GEE_PROJECT=your-project-id \
  -e "GEE_SERVICE_ACCOUNT_JSON=$(cat service-account.json)" \
  road-roughness
```

Open: http://localhost:8000

---

## Troubleshooting

### Build Fails
- Check Railway **Deployments** tab for logs
- Ensure Dockerfile is in root directory
- Verify all files are committed to Git

### App Crashes on Start
- Check **Logs** in Railway dashboard
- Verify `GEE_PROJECT` is set correctly
- Ensure service account JSON is valid (check for extra quotes)

### Earth Engine Errors
```
Error: Earth Engine could not start
```
**Fix**: 
1. Verify service account email is registered at code.earthengine.google.com
2. Check `GEE_SERVICE_ACCOUNT_JSON` has the complete JSON (no truncation)
3. Ensure your GEE project has Earth Engine API enabled

### Storage Not Persisting
- Add a volume in Railway (see Step 4 above)
- Or set `KEEP_ONLY_LATEST_PROJECT=true` to reduce storage needs

### CORS Errors
- Set `CORS_ORIGINS` to your frontend domain
- Or use `*` for development (not recommended for production)

---

## Advanced Configuration

### Custom Domain
1. Railway **Settings** → **Domains**
2. Add your custom domain
3. Update DNS records as shown
4. Update `CORS_ORIGINS` if needed

### Environment-Specific Variables
```env
# Production settings
CORS_ORIGINS=https://yourdomain.com
KEEP_ONLY_LATEST_PROJECT=false
NDWI_WORKERS=8

# Development settings
CORS_ORIGINS=*
KEEP_ONLY_LATEST_PROJECT=true
NDWI_WORKERS=2
```

### Monitoring
- Railway provides CPU/Memory/Network metrics
- Check **Metrics** tab for usage
- Set up alerts in Railway dashboard

---

## Cost Optimization

### Railway Pricing
- **Starter**: $5 credit/month (Free tier)
- **Developer**: $5/month + usage
- **Team**: $20/month + usage

### Tips to Save Money
1. Use persistent volume wisely (charges per GB)
2. Set `KEEP_ONLY_LATEST_PROJECT=true` to auto-cleanup
3. Consider pausing the service when not in use
4. Monitor CPU/Memory in Metrics tab
5. Optimize `NDWI_WORKERS` (fewer = less CPU)

---

## Security Best Practices

1. ✅ Never commit `.env` or service account JSON files
2. ✅ Use Railway environment variables for secrets
3. ✅ Set specific `CORS_ORIGINS` in production (not `*`)
4. ✅ Use service accounts (not personal credentials)
5. ✅ Enable HTTPS only (Railway does this by default)
6. ✅ Review Railway access logs periodically

---

## Quick Reference

### Railway CLI Commands
```bash
# Install CLI
npm i -g @railway/cli

# Login
railway login

# Link to project
railway link

# View logs
railway logs

# Set variable
railway variables --set KEY=value

# Deploy
railway up
```

### Useful URLs
- Railway Dashboard: https://railway.app/dashboard
- Railway Docs: https://docs.railway.app
- Earth Engine: https://code.earthengine.google.com
- Google Cloud Console: https://console.cloud.google.com

---

## Support

Need help?
- Railway Discord: https://discord.gg/railway
- Railway Docs: https://docs.railway.app
- Earth Engine Forum: https://groups.google.com/g/google-earth-engine-developers

---

**That's it! Your Road Roughness Platform should now be running on Railway. 🚂**
