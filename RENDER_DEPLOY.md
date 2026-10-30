# Deploy to Render - Step by Step

## Prerequisites
- GitHub account
- Render account (sign up at https://render.com)
- Google Earth Engine service account key (JSON file)

---

## Step 1: Push to GitHub

```bash
git add .
git commit -m "Ready for Render deployment"
git push
```

---

## Step 2: Create Service Account (if not done)

1. Go to https://console.cloud.google.com/iam-admin/serviceaccounts
2. Select project: `arctic-hybrid-462806-c9`
3. Click "CREATE SERVICE ACCOUNT"
4. Name: `render-earthengine`
5. Grant role: "Earth Engine Resource Admin"
6. Create JSON key and download it
7. Open the JSON file and copy ALL contents

---

## Step 3: Deploy on Render

### Method A: Using Dashboard (Recommended)

1. **Login to Render**
   - Go to https://dashboard.render.com/
   - Sign in with GitHub

2. **Create New Web Service**
   - Click "New +" button
   - Select "Web Service"

3. **Connect Repository**
   - Click "Connect account" if needed
   - Find and select your `Road_Roughness` repository
   - Click "Connect"

4. **Configure Service**
   - **Name:** `road-roughness-app`
   - **Region:** Oregon (US West)
   - **Branch:** `main`
   - **Runtime:** Docker
   - **Plan:** Starter ($7/month) or Free (limitations apply)

5. **Add Environment Variables**
   Click "Advanced" then add:
   
   | Key | Value |
   |-----|-------|
   | `GEE_PROJECT` | `arctic-hybrid-462806-c9` |
   | `GEE_SERVICE_ACCOUNT_KEY` | Paste entire JSON from Step 2 |
   | `GOOGLE_MAPS_API_KEY` | Your Google Maps API key (optional) |

6. **Add Persistent Disk (Important!)**
   - Scroll to "Disk" section
   - Click "Add Disk"
   - Name: `storage`
   - Mount Path: `/app/storage`
   - Size: 10 GB
   - Click "Save"

7. **Deploy**
   - Click "Create Web Service"
   - Wait 5-10 minutes for first deployment

### Method B: Using render.yaml (Auto-deploy)

If you have `render.yaml` in your repo:

1. Go to https://dashboard.render.com/
2. Click "New +" → "Blueprint"
3. Connect your repository
4. Render auto-detects `render.yaml`
5. Add environment variables in the dashboard
6. Click "Apply"

---

## Step 4: Configure Environment Variables (After Creation)

If you didn't add them during setup:

1. Go to your service dashboard
2. Click "Environment" in left sidebar
3. Add each variable:
   - Click "Add Environment Variable"
   - Key: `GEE_SERVICE_ACCOUNT_KEY`
   - Value: Paste entire JSON
   - Click "Save Changes"

Service will auto-redeploy after adding variables.

---

## Step 5: Test Your Deployment

After deployment completes (Status: "Live"):

1. **Get Your URL**
   - Shows at top: `https://road-roughness-app.onrender.com`

2. **Test Homepage**
   - Visit: `https://road-roughness-app.onrender.com`
   - Should see map and app interface

3. **Test API**
   - Visit: `https://road-roughness-app.onrender.com/api/config`
   - Should return JSON with version info

---

## Deployment Features

✅ **Persistent Storage** - Files saved in `/storage` persist across deploys
✅ **Full OpenCV Support** - All image processing works
✅ **No Timeout Issues** - Runs as long as needed
✅ **Automatic HTTPS** - Render provides SSL certificate
✅ **Auto-Deploy** - Pushes to GitHub trigger redeployment

---

## Troubleshooting

### Build Fails

**Check logs:**
- Dashboard → Your Service → "Logs" tab
- Look for error during Docker build

**Common issues:**
- Missing system dependencies → Already in Dockerfile
- pip install fails → Check requirements.txt

### App Doesn't Start

**Check runtime logs:**
- Dashboard → "Logs" tab → Select "Latest Deploy"

**Common issues:**
- Port mismatch → Already set to 0.0.0.0:8000
- Missing env vars → Add in Environment tab

### Earth Engine Fails

**Error:** "Please authenticate"
**Fix:** Add `GEE_SERVICE_ACCOUNT_KEY` environment variable

### Storage Not Persisting

**Error:** Files disappear after redeploy
**Fix:** 
1. Dashboard → Your Service → "Disk" tab
2. Add disk: mount to `/app/storage`

---

## Cost Estimate

**Free Plan:**
- ✅ 750 hours/month free
- ⚠️ Spins down after 15 min inactivity (slow first load)
- ⚠️ No persistent disk
- ⚠️ 512 MB RAM

**Starter Plan ($7/month):**
- ✅ Always on (no spin down)
- ✅ 10 GB persistent disk included
- ✅ 512 MB RAM
- ✅ Good for this app

**Standard Plan ($25/month):**
- ✅ 2 GB RAM
- ✅ Faster processing
- ✅ More concurrent users

---

## Update Your App

After making code changes:

```bash
git add .
git commit -m "Update feature"
git push
```

Render auto-deploys in 3-5 minutes!

---

## Custom Domain (Optional)

1. Dashboard → Your Service → "Settings"
2. Scroll to "Custom Domains"
3. Click "Add Custom Domain"
4. Enter: `roadapp.yourdomain.com`
5. Add CNAME record in your DNS:
   - Name: `roadapp`
   - Value: `road-roughness-app.onrender.com`
6. Wait for DNS propagation (5-30 min)

---

## Monitoring

**View Logs:**
- Dashboard → Your Service → "Logs"
- Real-time log streaming

**Metrics:**
- Dashboard → Your Service → "Metrics"
- CPU, Memory, Request count

**Alerts:**
- Dashboard → Account Settings → Notifications
- Get email when service goes down

---

## Summary

```bash
# 1. Push to GitHub
git push

# 2. In Render Dashboard:
# - New Web Service
# - Connect GitHub repo
# - Runtime: Docker
# - Add environment variables
# - Add persistent disk
# - Deploy

# 3. Done! Your app is live at:
# https://road-roughness-app.onrender.com
```

That's it! Full-featured deployment with persistent storage.
