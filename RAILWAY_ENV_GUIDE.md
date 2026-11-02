# 🔑 Railway Environment Variables - Complete Guide

## Environment Variables to Add on Railway

### ✅ REQUIRED Variables (Must Set)

Copy these to Railway Dashboard → Your Service → Variables → Raw Editor:

```env
GEE_PROJECT=your-gee-project-id
GEE_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"your-project","private_key_id":"xxx","private_key":"-----BEGIN PRIVATE KEY-----\nxxx\n-----END PRIVATE KEY-----\n","client_email":"your-service-account@your-project.iam.gserviceaccount.com","client_id":"xxx","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_x509_cert_url":"xxx"}
RR_HOST=0.0.0.0
RR_PORT=8000
CORS_ORIGINS=*
SERVE_FRONTEND=true
```

### 📝 RECOMMENDED Variables (Good to Set)

```env
KEEP_ONLY_LATEST_PROJECT=true
DEFAULT_CLOUD_PCT=40
NDWI_WORKERS=4
NEAREST_SEARCH_DAYS=90
```

### 🎨 OPTIONAL Variables (Set if needed)

```env
GOOGLE_MAPS_API_KEY=your-google-maps-api-key
DEFAULT_CHAINAGE_START_KM=0.000
DEFAULT_INTERVAL_M=1.0
DEFAULT_MEDIAN_OFFSET_M=1.0
DEFAULT_LANE_COUNT=4
DEFAULT_LANE_WIDTH_M=3.40
DEFAULT_BIN_KM=0.100
```

---

## 📖 Detailed Explanation of Each Variable

### 1. GEE_PROJECT
```
Example: arctic-hybrid-462806-c9
```
**What it is:** Your Google Cloud project ID that has Earth Engine enabled

**How to get it:**
1. Go to https://console.cloud.google.com
2. Look at the top of the page - your project ID is shown
3. Or click on project dropdown → Copy project ID

**Important:** This must match your Google Cloud project with Earth Engine enabled

---

### 2. GEE_SERVICE_ACCOUNT_JSON
```
Example: {"type":"service_account","project_id":"my-project",...}
```
**What it is:** The complete JSON content from your service account key file

**How to get it:**

**Step 1: Create Service Account**
1. Go to https://console.cloud.google.com
2. Select your project
3. Navigate to: **IAM & Admin → Service Accounts**
4. Click: **CREATE SERVICE ACCOUNT**
5. Name: `railway-road-roughness`
6. Click: **CREATE AND CONTINUE**
7. Skip role assignment (optional)
8. Click: **DONE**

**Step 2: Create Key**
1. Click on the service account you just created
2. Go to **Keys** tab
3. Click: **ADD KEY → Create new key**
4. Choose: **JSON**
5. Click: **CREATE**
6. A JSON file will download

**Step 3: Copy JSON Content**
1. Open the downloaded JSON file in a text editor
2. Copy the **ENTIRE** content (all of it)
3. Paste into Railway as the value for `GEE_SERVICE_ACCOUNT_JSON`

**Step 4: Register with Earth Engine**
1. Go to https://code.earthengine.google.com
2. Click on **Assets** (left sidebar)
3. Click the settings icon → **Cloud Project**
4. Add your service account email (from the JSON file, the `client_email` field)

**Important Notes:**
- Copy the ENTIRE JSON content (starts with `{` and ends with `}`)
- Don't add extra quotes around it in Railway
- Make sure no characters are missing
- The JSON should be on ONE line in Railway (no line breaks)

---

### 3. RR_HOST
```
Value: 0.0.0.0
```
**What it is:** The host address the server listens on

**Important:** MUST be `0.0.0.0` for Railway (not `127.0.0.1`)
- `0.0.0.0` = Listen on all network interfaces (required for Railway)
- `127.0.0.1` = Listen only locally (won't work on Railway)

---

### 4. RR_PORT
```
Value: 8000
```
**What it is:** The port your application listens on

**Note:** Railway automatically sets a `PORT` variable, but our app uses `RR_PORT`

---

### 5. CORS_ORIGINS
```
Development: *
Production: https://your-domain.com
```
**What it is:** Which domains can access your API

**Options:**
- `*` = Allow all domains (good for testing)
- `https://your-app.railway.app` = Only your Railway URL
- `https://your-domain.com` = Your custom domain

**Security Note:** Use `*` for development, but change to your specific domain for production

---

### 6. SERVE_FRONTEND
```
Value: true
```
**What it is:** Whether the backend should also serve the frontend files

**Important:** Set to `true` to deploy both backend and frontend together in one service
- `true` = Backend serves frontend (simpler, one deployment)
- `false` = Deploy frontend separately (more complex)

---

### 7. KEEP_ONLY_LATEST_PROJECT
```
Value: true
```
**What it is:** Auto-delete old projects to save storage space

**Options:**
- `true` = Keep only the most recent project (saves storage costs)
- `false` = Keep all projects (uses more storage)

**Cost Impact:** 
- `true` = Lower storage costs (recommended for testing)
- `false` = Higher storage costs (needed for production if you want history)

---

### 8. DEFAULT_CLOUD_PCT
```
Value: 40
```
**What it is:** Maximum cloud coverage (%) for Sentinel-2 images

**Explanation:**
- Lower = Fewer clouds, but fewer available images
- Higher = More available images, but may have more clouds
- Range: 0-100
- Recommended: 40

---

### 9. NDWI_WORKERS
```
Value: 4
```
**What it is:** Number of parallel workers downloading images from Earth Engine

**Performance vs Cost:**
- Higher = Faster downloads, more CPU usage, higher cost
- Lower = Slower downloads, less CPU usage, lower cost
- Range: 1-8
- Recommended: 4 for balance

**Optimization:**
- Testing/Light use: 2
- Normal use: 4
- Heavy use: 8

---

### 10. NEAREST_SEARCH_DAYS
```
Value: 90
```
**What it is:** How many days to search for Sentinel-2 images before/after the target date

**Explanation:**
- Higher = More likely to find images, but may be further from target date
- Lower = Images closer to target date, but may not find any
- Range: 30-180
- Recommended: 90

---

### 11. GOOGLE_MAPS_API_KEY (Optional)
```
Value: your-api-key-here
```
**What it is:** Google Maps API key for additional map layers

**Required?** No - the app works fine without it

**If you want Google Maps layers:**
1. Go to https://console.cloud.google.com
2. Enable: **Map Tiles API**
3. Create API key
4. Paste key here

---

## 🎯 How to Set Variables on Railway

### Method 1: Railway Dashboard (Recommended)

**Step 1: Go to Variables Tab**
1. Open your Railway project
2. Click on your service
3. Click **Variables** tab

**Step 2: Add Variables**

**Option A: Raw Editor (Easiest for multiple variables)**
1. Click **RAW EDITOR** button
2. Paste this template:

```env
GEE_PROJECT=your-gee-project-id
GEE_SERVICE_ACCOUNT_JSON={"paste":"your","json":"here"}
RR_HOST=0.0.0.0
RR_PORT=8000
CORS_ORIGINS=*
SERVE_FRONTEND=true
KEEP_ONLY_LATEST_PROJECT=true
DEFAULT_CLOUD_PCT=40
NDWI_WORKERS=4
NEAREST_SEARCH_DAYS=90
```

3. Replace `your-gee-project-id` with your actual project ID
4. Replace the JSON placeholder with your actual service account JSON
5. Click **Update Variables**

**Option B: One by One**
1. Click **New Variable** button
2. Enter variable name (e.g., `GEE_PROJECT`)
3. Enter value
4. Click **Add**
5. Repeat for each variable

---

### Method 2: Railway CLI

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Link to your project
railway link

# Set variables one by one
railway variables --set GEE_PROJECT=your-project-id
railway variables --set RR_HOST=0.0.0.0
railway variables --set RR_PORT=8000
railway variables --set CORS_ORIGINS="*"
railway variables --set SERVE_FRONTEND=true
railway variables --set KEEP_ONLY_LATEST_PROJECT=true

# For the JSON (use single quotes to wrap the entire JSON)
railway variables --set GEE_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'
```

---

## 🚀 Complete Deployment Steps

### Step 1: Prepare Service Account

```
1. Go to: https://console.cloud.google.com
2. IAM & Admin → Service Accounts → CREATE SERVICE ACCOUNT
3. Name: railway-road-roughness
4. Create → Done
5. Click service account → Keys → ADD KEY → Create new key
6. Choose JSON → CREATE
7. Download the JSON file
8. Go to: https://code.earthengine.google.com
9. Register the service account email
```

### Step 2: Push Code to GitHub

```bash
git add .
git commit -m "Deploy to Railway"
git push origin main
```

### Step 3: Create Railway Project

```
1. Go to: https://railway.app
2. Click: New Project
3. Click: Deploy from GitHub repo
4. Select your repository
5. Railway will detect Dockerfile and start building
```

### Step 4: Set Environment Variables

```
1. Click on your service (it will be building)
2. Click: Variables tab
3. Click: RAW EDITOR
4. Paste the template from above
5. Fill in your actual values:
   - Your GEE_PROJECT ID
   - Your service account JSON (open the downloaded file, copy ALL content)
6. Click: Update Variables
7. Railway will automatically redeploy with new variables
```

### Step 5: Add Persistent Storage (Optional but Recommended)

```
1. Still in Variables tab
2. Scroll down to VOLUMES section
3. Click: New Volume
4. Mount Path: /app/road_roughness/backend/storage
5. Click: Add
```

### Step 6: Get Your URL

```
1. Go to Settings tab
2. Under DOMAINS section
3. Click: Generate Domain
4. Copy your URL: https://your-app-name.up.railway.app
```

### Step 7: Access Your App

```
Open: https://your-app-name.up.railway.app

You should see:
✅ Map interface
✅ Upload KML button
✅ Draw tools
```

---

## ✅ Verification Checklist

After deployment, verify:

- [ ] Railway deployment shows "Active" with green dot
- [ ] No errors in deployment logs
- [ ] App URL opens (https://your-app.up.railway.app)
- [ ] Frontend loads with map
- [ ] No console errors in browser (F12)
- [ ] Can draw on map
- [ ] Can upload KML
- [ ] Earth Engine authentication works (try downloading images)

---

## 🐛 Troubleshooting Environment Variables

### Error: "Earth Engine could not start"

**Cause:** GEE_SERVICE_ACCOUNT_JSON is invalid or incomplete

**Fix:**
1. Go to Variables tab in Railway
2. Click on `GEE_SERVICE_ACCOUNT_JSON` variable
3. Verify the JSON is complete (starts with `{` ends with `}`)
4. Make sure no characters are cut off
5. Re-copy from the original JSON file if needed

### Error: "Failed to initialize EE with service account"

**Cause:** Service account not registered with Earth Engine

**Fix:**
1. Go to https://code.earthengine.google.com
2. Click Assets (left sidebar)
3. Register your service account email
4. The email is in the JSON file: `client_email` field

### Error: "Address already in use" or "Cannot bind to port"

**Cause:** RR_HOST is not set to `0.0.0.0`

**Fix:**
1. Go to Variables tab
2. Set `RR_HOST=0.0.0.0` (not 127.0.0.1)
3. Railway will redeploy

### Frontend not loading

**Cause:** SERVE_FRONTEND is not set to `true`

**Fix:**
1. Go to Variables tab
2. Set `SERVE_FRONTEND=true`
3. Railway will redeploy

### CORS errors in browser console

**Cause:** CORS_ORIGINS misconfigured

**Fix:**
1. Go to Variables tab
2. Set `CORS_ORIGINS=*` (for testing)
3. Or set to your specific domain for production

---

## 📊 Variable Priority

Railway loads variables in this order (later overrides earlier):

1. Default values in `app/config.py`
2. Railway environment variables
3. Railway secrets

**Important:** Railway environment variables override the `.env` file

---

## 🔒 Security Best Practices

### ✅ DO:
- Use Railway Variables for all secrets
- Set CORS_ORIGINS to your domain in production
- Use service account (not personal credentials)
- Keep service account JSON private
- Enable 2FA on Railway account

### ❌ DON'T:
- Commit `.env` files to Git
- Commit service account JSON files to Git
- Use `CORS_ORIGINS=*` in production
- Share your service account JSON publicly
- Hardcode credentials in code

---

## 💡 Pro Tips

1. **Test locally first:**
   ```bash
   cp .env.docker.example .env
   # Edit .env with your values
   docker-compose up
   ```

2. **Copy variables from local .env:**
   - If you have a working local `.env` file
   - You can copy the values to Railway
   - But DON'T commit the `.env` file to Git

3. **Use Railway CLI for quick updates:**
   ```bash
   railway variables --set NDWI_WORKERS=8
   ```

4. **Monitor after variable changes:**
   - Go to Deployments tab
   - Watch the logs during redeployment
   - Check for any errors

---

## 🎉 You're Done!

After setting these variables, Railway will automatically:
1. Redeploy your application
2. Use the new environment variables
3. Your app will be live at your Railway URL

**Both backend AND frontend are deployed together in one service because `SERVE_FRONTEND=true`**

Access your app at: `https://your-app-name.up.railway.app`

---

**Need more help?** See `QUICK_START_RAILWAY.md` or `README_RAILWAY.md`
