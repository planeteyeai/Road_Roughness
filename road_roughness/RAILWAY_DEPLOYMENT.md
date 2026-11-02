# Railway Deployment Guide for Road Roughness Platform

## Overview
This guide will help you deploy the Road Roughness Platform on Railway. The application consists of:
- **Backend**: FastAPI Python application
- **Frontend**: Static HTML/CSS/JS files (served by the backend)

## Prerequisites

1. **Railway Account**: Sign up at [railway.app](https://railway.app)
2. **GitHub Account**: Your code should be in a GitHub repository
3. **Google Earth Engine Access**: You'll need a GEE project ID and authentication

## Step-by-Step Deployment

### Step 1: Prepare Your Repository

First, we need to create Railway-specific configuration files.

#### 1.1 Create `railway.toml` (Railway Configuration)
This file tells Railway how to build and run your application.

#### 1.2 Create `Procfile` (Process Definition)
This defines the command to start your application.

#### 1.3 Update `.env.example` for Railway
Add Railway-specific environment variables.

### Step 2: Push to GitHub

```bash
git add .
git commit -m "Add Railway deployment configuration"
git push origin main
```

### Step 3: Create New Project on Railway

1. Go to [railway.app](https://railway.app)
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose your repository: `your-username/road_roughness`
5. Railway will automatically detect it's a Python project

### Step 4: Configure Environment Variables

In the Railway dashboard, go to your project and click on **Variables** tab. Add these:

**Required Variables:**
```
RR_HOST=0.0.0.0
RR_PORT=8000
CORS_ORIGINS=*
SERVE_FRONTEND=true
FRONTEND_DIR=../frontend
GEE_PROJECT=your-gee-project-id
KEEP_ONLY_LATEST_PROJECT=true
DEFAULT_CLOUD_PCT=40
NEAREST_SEARCH_DAYS=90
NDWI_WORKERS=4
```

**Optional Variables:**
```
GOOGLE_MAPS_API_KEY=your-google-maps-api-key-if-you-have-one
DEFAULT_CHAINAGE_START_KM=0.000
DEFAULT_INTERVAL_M=1.0
DEFAULT_MEDIAN_OFFSET_M=1.0
DEFAULT_LANE_COUNT=4
DEFAULT_LANE_WIDTH_M=3.40
DEFAULT_BIN_KM=0.100
```

**Important Notes:**
- `RR_HOST` must be `0.0.0.0` (not 127.0.0.1) for Railway
- Railway will automatically set `PORT` but we use `RR_PORT`
- Set `CORS_ORIGINS=*` or specify your domain after deployment

### Step 5: Handle Google Earth Engine Authentication

This is the tricky part. Earth Engine requires authentication which is normally interactive.

**Option A: Service Account (Recommended for Production)**

1. Create a GEE Service Account:
   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - Navigate to IAM & Admin → Service Accounts
   - Create a new service account
   - Download the JSON key file

2. Add the service account to your GEE project:
   - Go to [Earth Engine Code Editor](https://code.earthengine.google.com)
   - Register the service account email

3. In Railway, add the service account credentials:
   - Either as `GEE_SERVICE_ACCOUNT_JSON` environment variable (the entire JSON content)
   - Or upload the key file and reference it with `GOOGLE_APPLICATION_CREDENTIALS`

**Option B: Pre-authenticated Credentials (Simpler but Less Secure)**

1. Authenticate locally first:
   ```bash
   earthengine authenticate
   ```

2. Copy your credentials file (usually at `~/.config/earthengine/credentials`)

3. You'll need to include this in your deployment (see code modifications below)

### Step 6: Add Volume for Persistent Storage

Railway provides ephemeral storage by default. For persistent file storage:

1. In Railway dashboard, go to your service
2. Click **"Variables"** → **"Add Volume"**
3. Mount path: `/app/road_roughness/backend/storage`
4. This ensures your project data persists between deployments

### Step 7: Deploy

Railway will automatically deploy when you push to your connected branch. To manually redeploy:

1. Go to your Railway project dashboard
2. Click **"Deploy"** or push a new commit

### Step 8: Get Your Deployment URL

1. Railway will provide a public URL like: `https://your-app.up.railway.app`
2. Your API will be at: `https://your-app.up.railway.app/api/config`
3. Frontend will be at: `https://your-app.up.railway.app/`

### Step 9: Update Frontend Config (if needed)

If you deploy frontend separately, update `frontend/js/config.js`:
```javascript
window.RR_CONFIG = {
  API_BASE: "https://your-app.up.railway.app",
};
```

## Troubleshooting

### Deployment Fails
- Check the build logs in Railway dashboard
- Ensure all dependencies in `requirements.txt` are installable
- Verify Python version (3.10+)

### App Starts But Crashes
- Check runtime logs in Railway dashboard
- Verify environment variables are set correctly
- Ensure GEE authentication is properly configured

### Storage Issues
- Make sure volume is mounted at correct path
- Check write permissions in logs
- Verify `RR_STORAGE` environment variable

### CORS Errors
- Update `CORS_ORIGINS` to include your frontend domain
- Or use `*` for development

### Earth Engine Errors
- Verify `GEE_PROJECT` is correct
- Ensure service account has proper permissions
- Check if Earth Engine API is enabled in Google Cloud Console

## Cost Considerations

Railway pricing:
- **Free Tier**: $5 credit/month (good for testing)
- **Hobby Plan**: $5/month + usage
- **Pro Plan**: $20/month + usage

Tips to reduce costs:
- Use persistent volumes wisely
- Set `KEEP_ONLY_LATEST_PROJECT=true` to save storage
- Monitor CPU/memory usage
- Consider sleeping the service when not in use

## Alternative: Docker Deployment

If Railway's Python support doesn't work well, you can create a `Dockerfile` (see separate section below).

## Security Recommendations

1. **Never commit** `.env` files with real credentials
2. Use Railway's **environment variables** for all secrets
3. Set specific `CORS_ORIGINS` for production
4. Use **service accounts** for GEE authentication
5. Consider adding authentication to your API endpoints
6. Use HTTPS only (Railway provides this by default)

## Monitoring

1. Check Railway **Metrics** tab for:
   - CPU usage
   - Memory usage
   - Network traffic

2. Monitor **Logs** for:
   - API errors
   - GEE authentication issues
   - Storage problems

3. Set up **alerts** for downtime or high resource usage

## Support

- Railway Docs: https://docs.railway.app
- Railway Discord: https://discord.gg/railway
- Earth Engine: https://developers.google.com/earth-engine

---

**Next Steps**: Continue to the files that need to be created below.
