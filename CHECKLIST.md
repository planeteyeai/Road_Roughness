# Railway Deployment Checklist ✓

Use this checklist to ensure a smooth deployment to Railway.

## 📋 Pre-Deployment

### Google Earth Engine Setup
- [ ] Google Cloud project created
- [ ] Service account created in Google Cloud Console
- [ ] Service account key (JSON) downloaded
- [ ] Service account email registered at code.earthengine.google.com
- [ ] Earth Engine API enabled in Google Cloud Console
- [ ] GEE_PROJECT ID noted (e.g., `my-project-123456`)

### Code Repository
- [ ] All code committed to Git
- [ ] Code pushed to GitHub
- [ ] Dockerfile in repository root
- [ ] .dockerignore in repository root
- [ ] No .env files committed (check .gitignore)
- [ ] No service account JSON files committed

### Railway Account
- [ ] Railway account created at railway.app
- [ ] GitHub connected to Railway
- [ ] Payment method added (if using paid plan)

---

## 🚀 Deployment

### Railway Project Setup
- [ ] New project created in Railway
- [ ] GitHub repository connected
- [ ] Railway detected Dockerfile
- [ ] Initial deployment triggered

### Environment Variables
- [ ] `GEE_PROJECT` set
- [ ] `GEE_SERVICE_ACCOUNT_JSON` set (full JSON content)
- [ ] `RR_HOST` set to `0.0.0.0`
- [ ] `RR_PORT` set to `8000`
- [ ] `CORS_ORIGINS` set (use `*` for testing)
- [ ] `SERVE_FRONTEND` set to `true`
- [ ] Optional variables set if needed:
  - [ ] `DEFAULT_CLOUD_PCT`
  - [ ] `NDWI_WORKERS`
  - [ ] `KEEP_ONLY_LATEST_PROJECT`
  - [ ] `GOOGLE_MAPS_API_KEY`

### Storage Configuration
- [ ] Persistent volume created (if needed)
- [ ] Mount path: `/app/road_roughness/backend/storage`
- [ ] Volume size appropriate (start with 1GB)

### Deployment Status
- [ ] Build completed successfully
- [ ] Container started
- [ ] Health check passing
- [ ] Railway shows "Healthy" status
- [ ] No errors in deployment logs

---

## ✅ Post-Deployment Verification

### Basic Functionality
- [ ] Railway URL accessible (https://your-app.up.railway.app)
- [ ] Frontend loads without errors
- [ ] Map interface displays correctly
- [ ] API endpoint responds: `/api/config`
- [ ] No console errors in browser

### Core Features
- [ ] Can draw median line on map
- [ ] Can upload KML file
- [ ] Lane generation works
- [ ] NDWI image download starts
- [ ] Earth Engine authentication successful
- [ ] Images appear in project folder
- [ ] Report generation works
- [ ] Can download Excel reports
- [ ] Can download PDF reports

### Monitoring
- [ ] Reviewed Railway logs (no critical errors)
- [ ] Checked Railway metrics (CPU, memory normal)
- [ ] Health check endpoint working
- [ ] No timeout errors

---

## 🔒 Security Checklist

### Credentials
- [ ] Service account JSON not in Git history
- [ ] No .env files in repository
- [ ] All secrets in Railway environment variables only
- [ ] Service account has minimal necessary permissions

### Configuration
- [ ] CORS_ORIGINS set appropriately for environment
- [ ] Using service account (not personal credentials)
- [ ] HTTPS enabled (Railway default)
- [ ] No sensitive data in logs

### Access Control
- [ ] Railway project access limited to team members
- [ ] GitHub repository access controlled
- [ ] Service account email not publicly exposed
- [ ] Railway dashboard 2FA enabled (recommended)

---

## 🎯 Production Readiness

### Performance
- [ ] Health checks configured and passing
- [ ] Storage volume size appropriate
- [ ] NDWI_WORKERS optimized for workload
- [ ] Cold start time acceptable (< 60s)

### Reliability
- [ ] Restart policy configured
- [ ] Error handling tested
- [ ] Storage volume backup plan in place
- [ ] Monitoring alerts set up (optional)

### Configuration
- [ ] CORS_ORIGINS set to specific domain (not `*`)
- [ ] KEEP_ONLY_LATEST_PROJECT configured appropriately
- [ ] All optional environment variables reviewed
- [ ] Frontend config.js updated if needed

### Documentation
- [ ] Team knows how to access Railway dashboard
- [ ] Team knows where environment variables are set
- [ ] Deployment process documented
- [ ] Troubleshooting steps available

---

## 🧪 Testing Checklist

### End-to-End Test
- [ ] Create new project with median line
- [ ] Generate lane KMLs
- [ ] Download NDWI images for date range
- [ ] Verify images downloaded correctly
- [ ] Generate roughness reports
- [ ] Download and verify Excel report
- [ ] Download and verify PDF report
- [ ] Check project data persisted in storage

### Error Handling
- [ ] Test with invalid KML file
- [ ] Test with out-of-range dates
- [ ] Test with no Sentinel-2 data available
- [ ] Verify error messages are clear
- [ ] Confirm app doesn't crash on errors

### Performance
- [ ] Test with small area (< 1 km)
- [ ] Test with medium area (1-10 km)
- [ ] Test with large area (> 10 km)
- [ ] Monitor Railway metrics during processing
- [ ] Verify memory doesn't exceed limits

---

## 🐛 Troubleshooting Steps

If something doesn't work, check these in order:

### 1. Check Railway Status
- [ ] Railway dashboard shows "Healthy"
- [ ] No recent deployment failures
- [ ] Latest deployment is active

### 2. Check Logs
- [ ] Review Railway logs for errors
- [ ] Look for Python tracebacks
- [ ] Check for Earth Engine errors
- [ ] Verify no missing environment variables

### 3. Verify Environment Variables
- [ ] All required variables present
- [ ] GEE_SERVICE_ACCOUNT_JSON is valid JSON
- [ ] GEE_PROJECT matches Google Cloud project
- [ ] No extra quotes or spaces in values

### 4. Test Earth Engine
- [ ] Service account registered with Earth Engine
- [ ] Earth Engine API enabled
- [ ] Service account has project access
- [ ] No rate limit errors

### 5. Check Storage
- [ ] Volume mounted correctly
- [ ] Write permissions OK
- [ ] Sufficient space available
- [ ] Files persisting between deploys

---

## 📊 Monitoring Checklist (Ongoing)

### Daily
- [ ] Check Railway health status
- [ ] Review error logs if any
- [ ] Verify backups if configured

### Weekly
- [ ] Review Railway metrics (CPU, memory, network)
- [ ] Check storage usage
- [ ] Review costs in Railway billing
- [ ] Check for Python/dependency updates

### Monthly
- [ ] Review Railway costs vs. budget
- [ ] Clean up old project data if needed
- [ ] Review and update environment variables
- [ ] Check for security updates

---

## 🎓 Knowledge Transfer Checklist

### Team Onboarding
- [ ] Railway dashboard access provided
- [ ] GitHub repository access provided
- [ ] Documentation shared (README_RAILWAY.md)
- [ ] Quick start guide reviewed (QUICK_START_RAILWAY.md)

### Key Information Shared
- [ ] Railway project URL
- [ ] GitHub repository URL
- [ ] Where environment variables are set
- [ ] How to view logs and metrics
- [ ] Who to contact for issues

### Emergency Procedures
- [ ] How to check Railway status
- [ ] How to view/download logs
- [ ] How to restart the service
- [ ] How to roll back deployment
- [ ] Emergency contacts documented

---

## 📈 Optimization Checklist

### Cost Optimization
- [ ] KEEP_ONLY_LATEST_PROJECT configured appropriately
- [ ] Storage volume size right-sized
- [ ] NDWI_WORKERS optimized (not too high)
- [ ] Monitoring Railway usage regularly

### Performance Optimization
- [ ] Cold start time acceptable
- [ ] NDWI_WORKERS tuned for performance
- [ ] Health check interval appropriate
- [ ] No unnecessary dependencies in requirements.txt

### Reliability Optimization
- [ ] Health checks configured correctly
- [ ] Restart policy set appropriately
- [ ] Error handling tested
- [ ] Logs reviewed for warnings

---

## ✨ Success Criteria

Your deployment is successful when ALL of these are true:

- ✅ Railway shows "Healthy" status
- ✅ App accessible at Railway URL
- ✅ Frontend loads without errors
- ✅ Can create project and draw median line
- ✅ Earth Engine authentication works
- ✅ NDWI images download successfully
- ✅ Reports generate correctly
- ✅ Storage persists between deploys
- ✅ No critical errors in logs
- ✅ Team can access and monitor the app

---

## 📝 Notes Section

Use this space for deployment-specific notes:

**Deployment Date:** _______________

**Railway URL:** _______________

**GEE Project ID:** _______________

**Team Members with Access:**
- _______________
- _______________
- _______________

**Special Configurations:**
_______________________________________________
_______________________________________________
_______________________________________________

**Known Issues:**
_______________________________________________
_______________________________________________
_______________________________________________

**Next Steps:**
_______________________________________________
_______________________________________________
_______________________________________________

---

**Last Updated:** 2026-11-02  
**Version:** 1.0

**Ready to deploy? Work through this checklist step by step!** ✓
