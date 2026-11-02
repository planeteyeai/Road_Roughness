# 🚀 Step-by-Step Railway Deployment

## Complete Visual Guide - Both Backend & Frontend Together

---

## 📋 Before You Start

Make sure you have:
- ✅ GitHub account
- ✅ Railway account (sign up at railway.app)
- ✅ Your code pushed to GitHub
- ✅ 15 minutes of time

---

## Part 1: Get Google Earth Engine Service Account (5 minutes)

### Step 1.1: Go to Google Cloud Console

```
Open: https://console.cloud.google.com
```

### Step 1.2: Select or Create Project

- Click on project dropdown at the top
- Either select your existing project: `arctic-hybrid-462806-c9`
- Or create a new project

### Step 1.3: Create Service Account

1. In the left menu, click: **IAM & Admin**
2. Click: **Service Accounts**
3. Click: **+ CREATE SERVICE ACCOUNT** (blue button at top)
4. Fill in:
   - **Service account name:** `railway-road-roughness`
   - **Service account ID:** (auto-filled)
   - **Description:** "Railway deployment for Road Roughness Platform"
5. Click: **CREATE AND CONTINUE**
6. Skip the optional steps, click: **DONE**

### Step 1.4: Create JSON Key

1. You'll see your new service account in the list
2. Click on it (the email address)
3. Click on **KEYS** tab (at the top)
4. Click: **ADD KEY** → **Create new key**
5. Choose format: **JSON**
6. Click: **CREATE**
7. A JSON file will download (keep it safe!)

### Step 1.5: Register with Earth Engine

1. Open: https://code.earthengine.google.com
2. Sign in with your Google account
3. If prompted, register for Earth Engine
4. Once in, click **Assets** in the left sidebar
5. Click the gear icon (settings)
6. Find the option to add your service account email
7. The email is in the JSON file you downloaded: `"client_email": "..."`
8. Add it and save

**✅ Part 1 Complete! You now have a service account JSON file.**

---

## Part 2: Push Code to GitHub (2 minutes)

### Step 2.1: Add All Files

```bash
git add .
```

### Step 2.2: Commit

```bash
git commit -m "Add Railway deployment configuration"
```

### Step 2.3: Push

```bash
git push origin main
```

Or if you're using `master` branch:
```bash
git push origin master
```

**✅ Part 2 Complete! Your code is on GitHub.**

---

## Part 3: Create Railway Project (3 minutes)

### Step 3.1: Go to Railway

```
Open: https://railway.app
```

### Step 3.2: Sign In

- Click **Login**
- Choose **Sign in with GitHub** (recommended)
- Authorize Railway to access your GitHub

### Step 3.3: Create New Project

1. You'll see the Railway dashboard
2. Click: **+ New Project** (big button)
3. Click: **Deploy from GitHub repo**
4. Select your repository from the list
   - If you don't see it, click "Configure GitHub App" to add it
5. Railway will automatically:
   - Detect the `Dockerfile`
   - Start building
   - Show "Building..." status

### Step 3.4: Wait for Initial Build

- The build will take 2-4 minutes
- You'll see build logs scrolling
- **Don't worry if it crashes** - we haven't set environment variables yet!

**✅ Part 3 Complete! Railway project created.**

---

## Part 4: Set Environment Variables (5 minutes)

### Step 4.1: Click on Your Service

- In Railway dashboard, click on your service (the box with your app name)
- This opens the service details

### Step 4.2: Go to Variables Tab

- Click the **Variables** tab (at the top)
- You'll see existing variables (if any)

### Step 4.3: Use Raw Editor

1. Click the **RAW EDITOR** button (top right)
2. This opens a text editor

### Step 4.4: Prepare Your Variables

Open the file `RAILWAY_VARIABLES.txt` in your project root.

**IMPORTANT: Edit the template BEFORE copying:**

1. Open your downloaded service account JSON file in a text editor
2. Copy the ENTIRE JSON content (from `{` to `}`)
3. In `RAILWAY_VARIABLES.txt`, replace `YOUR_SERVICE_ACCOUNT_JSON_HERE` with the actual JSON
4. Make sure the JSON is on ONE line

Example:
```
Before:
GEE_SERVICE_ACCOUNT_JSON=YOUR_SERVICE_ACCOUNT_JSON_HERE

After:
GEE_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"arctic-hybrid-462806-c9",...}
```

### Step 4.5: Paste Variables

1. Select ALL content from `RAILWAY_VARIABLES.txt` (after you edited it)
2. Copy it (Ctrl+C or Cmd+C)
3. Paste into Railway's Raw Editor
4. Click: **Update Variables** (green button)

### Step 4.6: Automatic Redeploy

- Railway will automatically redeploy with the new variables
- This takes 3-4 minutes
- Watch the "Deployments" tab for progress

**✅ Part 4 Complete! Environment variables configured.**

---

## Part 5: Add Persistent Storage (2 minutes) - OPTIONAL

### Step 5.1: Still in Variables Tab

- Scroll down to the **VOLUMES** section

### Step 5.2: Add Volume

1. Click: **+ New Volume**
2. Mount Path: `/app/road_roughness/backend/storage`
3. Click: **Add**

### Step 5.3: Redeploy

- Railway will redeploy again (automatically)
- This ensures your project data persists between deployments

**✅ Part 5 Complete! Persistent storage added.**

---

## Part 6: Get Your URL & Test (2 minutes)

### Step 6.1: Go to Settings Tab

- Click the **Settings** tab

### Step 6.2: Generate Domain

1. Scroll to **DOMAINS** section
2. If you see "Generate Domain" button, click it
3. Railway will create a URL like: `https://your-app-name-production.up.railway.app`
4. Copy this URL

### Step 6.3: Wait for Healthy Status

- Go back to the main service view
- Wait for the status to show **green dot** with "Healthy"
- This means your app is running

### Step 6.4: Open Your App

1. Click on the URL or paste it in your browser
2. You should see:
   - ✅ Map interface loads
   - ✅ Leaflet map displays
   - ✅ Drawing tools visible
   - ✅ Upload button visible

### Step 6.5: Check API

Open: `https://your-app-name.up.railway.app/api/config`

You should see JSON like:
```json
{
  "version": "1.6",
  "gee_project": "arctic-hybrid-462806-c9",
  ...
}
```

### Step 6.6: Test Functionality

1. **Draw a line** on the map
2. **Set parameters** (dates, cloud cover, etc.)
3. **Click "Generate Lane KMLs"**
4. If it works without errors, you're good!

**✅ Part 6 Complete! Your app is live and working!**

---

## 🎉 Deployment Complete!

### What You Deployed

✅ **Backend (FastAPI):**
- Running on port 8000
- Earth Engine integration
- All API endpoints

✅ **Frontend (HTML/CSS/JS):**
- Served by the backend
- Map interface
- All interactive features

✅ **Storage:**
- Persistent storage for projects
- Images and reports saved

### Your URLs

- **App:** `https://your-app-name.up.railway.app`
- **API:** `https://your-app-name.up.railway.app/api/config`
- **Docs:** `https://your-app-name.up.railway.app/docs`

---

## ✅ Verification Checklist

Verify everything works:

- [ ] Railway shows "Healthy" status (green dot)
- [ ] App URL opens without errors
- [ ] Map displays correctly
- [ ] Can draw median line on map
- [ ] Can upload KML file
- [ ] Lane generation works
- [ ] NDWI download starts (test with small area)
- [ ] No errors in browser console (F12)
- [ ] No errors in Railway logs

---

## 🔍 How to Check Railway Logs

If something doesn't work:

1. Go to Railway dashboard
2. Click on your service
3. Click **Deployments** tab
4. Click on the latest deployment
5. View the logs - look for:
   - ✅ "Road Roughness Platform backend 1.6"
   - ✅ "Uvicorn running on..."
   - ✅ "Earth Engine initialized"
   - ❌ Any error messages

---

## 🐛 Common Issues & Fixes

### Issue 1: Build Fails

**Symptom:** Deployment shows "Failed" status

**Fix:**
1. Check that `Dockerfile` is in repository root
2. Ensure all files are committed and pushed
3. Check build logs for specific errors

### Issue 2: App Crashes After Build

**Symptom:** Build succeeds but app shows "Crashed"

**Fix:**
1. Check Railway logs for error message
2. Most common: `GEE_SERVICE_ACCOUNT_JSON` is incomplete
3. Go to Variables tab, verify the JSON is complete
4. Should start with `{` and end with `}`

### Issue 3: "Earth Engine could not start"

**Symptom:** Error in logs about Earth Engine

**Fix:**
1. Verify service account is registered at code.earthengine.google.com
2. Check `GEE_PROJECT` matches your Google Cloud project ID
3. Ensure Earth Engine API is enabled in Google Cloud Console

### Issue 4: Frontend Shows Blank Page

**Symptom:** URL opens but shows blank/white page

**Fix:**
1. Check browser console (F12) for errors
2. Verify `SERVE_FRONTEND=true` in Variables
3. Check `FRONTEND_DIR=../frontend` in Variables

### Issue 5: CORS Errors

**Symptom:** API calls fail with CORS error

**Fix:**
1. Set `CORS_ORIGINS=*` in Variables
2. Or set to your specific Railway URL

### Issue 6: Storage Not Persisting

**Symptom:** Project data disappears after redeployment

**Fix:**
1. Add a Volume (see Part 5 above)
2. Mount path: `/app/road_roughness/backend/storage`

---

## 🔄 How to Update Your App

### Method 1: Git Push (Automatic)

```bash
# Make changes to your code
git add .
git commit -m "Your changes"
git push origin main

# Railway automatically detects and redeploys!
```

### Method 2: Manual Redeploy

1. Railway dashboard → Your service
2. Click the three dots (...)
3. Click **Redeploy**

### Method 3: Update Environment Variables

1. Variables tab → Raw Editor
2. Make changes
3. Click **Update Variables**
4. Railway redeploys automatically

---

## 💰 Monitor Your Costs

### Check Usage

1. Railway dashboard → Account (top right)
2. Click **Usage**
3. See your current usage and costs

### Typical Costs

- **Free tier:** $5 credit/month
- **This app:** Usually $3-8/month
- **With storage:** Add ~$0.50-2/month

### Save Money

- Set `KEEP_ONLY_LATEST_PROJECT=true` (already set)
- Lower `NDWI_WORKERS` to 2 if needed
- Use the free tier for testing

---

## 📊 Both Backend & Frontend Deployed

### Why This Works

Your `SERVE_FRONTEND=true` setting means:
- Backend (FastAPI) runs on port 8000
- Backend ALSO serves frontend static files
- Everything in ONE Railway service
- Simpler deployment, lower cost

### Architecture

```
Railway Service (One Container)
│
├── Backend (FastAPI)
│   ├── Port 8000
│   ├── API endpoints (/api/*)
│   ├── Earth Engine integration
│   └── Serves frontend at /
│
└── Frontend (Static Files)
    ├── index.html
    ├── styles.css
    ├── app.js
    └── All assets
```

---

## 🎓 Next Steps

### 1. Add Custom Domain (Optional)

1. Settings tab → Domains
2. Add your domain
3. Update DNS records
4. Update `CORS_ORIGINS` to your domain

### 2. Production Settings

```env
CORS_ORIGINS=https://your-domain.com
KEEP_ONLY_LATEST_PROJECT=false
NDWI_WORKERS=8
```

### 3. Set Up Monitoring

- Check Railway Metrics tab daily
- Set up alerts in Railway
- Monitor costs in Usage tab

### 4. Backup Data

- Periodically download projects
- Use Railway volume backups (if available)
- Keep service account JSON safe

---

## 🆘 Need Help?

### Railway Support

- Dashboard: https://railway.app/dashboard
- Docs: https://docs.railway.app
- Discord: https://discord.gg/railway (very active!)
- Status: https://status.railway.app

### Earth Engine Support

- Console: https://code.earthengine.google.com
- Docs: https://developers.google.com/earth-engine
- Forum: https://groups.google.com/g/google-earth-engine-developers

### Check Railway Logs First!

Most issues can be diagnosed from the logs:
1. Railway dashboard
2. Your service
3. Deployments tab
4. Latest deployment logs

---

## 📝 Summary

You just deployed:

✅ FastAPI backend with Earth Engine  
✅ Static frontend with Leaflet maps  
✅ Persistent storage for projects  
✅ Automatic HTTPS (Railway)  
✅ Health monitoring  
✅ Auto-restart on failures  

**All in ONE Railway service, running together!**

Your app is live at: `https://your-app-name.up.railway.app`

**Congratulations! 🎉**

---

**Total time:** ~15-20 minutes  
**Monthly cost:** ~$3-8 (within free tier for testing)  
**Complexity:** Low (one service, automatic builds)

**You did it!** 🚀
