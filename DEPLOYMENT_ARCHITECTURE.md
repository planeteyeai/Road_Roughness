# Railway Deployment Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Railway Platform                         │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    Docker Container                         │ │
│  │                                                             │ │
│  │  ┌─────────────────┐        ┌──────────────────┐          │ │
│  │  │   Frontend      │        │     Backend      │          │ │
│  │  │  (Static Files) │───────▶│   FastAPI App    │          │ │
│  │  │  - HTML/CSS/JS  │        │   - Python 3.10  │          │ │
│  │  │  - Leaflet Map  │        │   - Uvicorn      │          │ │
│  │  └─────────────────┘        └──────────────────┘          │ │
│  │          │                           │                      │ │
│  │          │                           ▼                      │ │
│  │          │                  ┌──────────────────┐           │ │
│  │          │                  │  Earth Engine    │           │ │
│  │          │                  │   Integration    │           │ │
│  │          │                  └──────────────────┘           │ │
│  │          │                           │                      │ │
│  │          │                           ▼                      │ │
│  │          │                  ┌──────────────────┐           │ │
│  │          └─────────────────▶│   Port 8000      │           │ │
│  │                             └──────────────────┘           │ │
│  │                                     │                       │ │
│  └─────────────────────────────────────┼───────────────────────┘ │
│                                        │                         │
│                     ┌──────────────────┼──────────────────┐      │
│                     │  Persistent Storage Volume          │      │
│                     │  /app/road_roughness/backend/storage│      │
│                     │  - Project files                     │      │
│                     │  - Generated reports                 │      │
│                     │  - NDWI images                       │      │
│                     └─────────────────────────────────────┘      │
│                                                                   │
└───────────────────────────────────┬───────────────────────────────┘
                                    │
                                    │ HTTPS
                                    ▼
                        ┌─────────────────────┐
                        │  Public Internet    │
                        │  your-app.railway   │
                        └─────────────────────┘
                                    │
                                    ▼
                            ┌───────────────┐
                            │  End Users    │
                            └───────────────┘
```

---

## Docker Image Layers

```
┌─────────────────────────────────────────────────┐
│ Base Layer: python:3.10-slim (~150MB)           │
└─────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│ System Dependencies (~20MB)                      │
│ - libgeos-c1v5, libproj25, libgdal30            │
│ - libgl1, libglib2.0-0                          │
└─────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│ Python Dependencies (~80MB)                      │
│ - fastapi, uvicorn, earthengine-api             │
│ - numpy, pandas, opencv-python, etc.            │
└─────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│ Application Code (~5MB)                          │
│ - Backend Python files                           │
│ - Frontend static files                          │
└─────────────────────────────────────────────────┘
                    │
                    ▼
        Total Image Size: ~250MB
```

---

## Request Flow

### 1. User Accesses Frontend
```
User Browser
    │
    ▼
https://your-app.railway.app/
    │
    ▼
Railway Load Balancer
    │
    ▼
Docker Container (Port 8000)
    │
    ▼
FastAPI serves index.html
    │
    ▼
User sees map interface
```

### 2. User Uploads Median Line KML
```
User Browser (JavaScript)
    │
    ▼
POST /api/projects/create
    │
    ▼
FastAPI Backend
    │
    ├─▶ Save KML to storage
    │
    └─▶ Generate lane KMLs
        │
        └─▶ Return project_id
            │
            ▼
        Browser updates UI
```

### 3. User Requests NDWI Images
```
User Browser (JavaScript)
    │
    ▼
POST /api/ndwi/process
    │
    ▼
FastAPI Backend
    │
    ├─▶ Authenticate with Earth Engine
    │   (using GEE_SERVICE_ACCOUNT_JSON)
    │
    ├─▶ Query Sentinel-2 imagery
    │   │
    │   └─▶ Google Earth Engine API
    │       │
    │       └─▶ Download images
    │
    ├─▶ Process images (NDWI calculation)
    │
    ├─▶ Save to storage volume
    │
    └─▶ Return status
        │
        ▼
    Browser shows results
```

### 4. User Generates Report
```
User Browser (JavaScript)
    │
    ▼
POST /api/reports/generate
    │
    ▼
FastAPI Backend
    │
    ├─▶ Calculate roughness (RI/IRI)
    │
    ├─▶ Generate Excel report
    │
    ├─▶ Generate PDF report
    │
    ├─▶ Save to storage volume
    │
    └─▶ Return download links
        │
        ▼
    User downloads reports
```

---

## Environment Variables Flow

```
Railway Dashboard
    │
    │ Set variables:
    │ - GEE_PROJECT
    │ - GEE_SERVICE_ACCOUNT_JSON
    │ - RR_HOST, RR_PORT, etc.
    │
    ▼
Container Runtime
    │
    ▼
app/config.py reads from os.environ
    │
    ├─▶ GEE_PROJECT → app/gee_auth.py
    │   │
    │   └─▶ Initialize Earth Engine
    │
    ├─▶ RR_HOST, RR_PORT → main.py
    │   │
    │   └─▶ Start uvicorn server
    │
    └─▶ Other settings → Various modules
```

---

## Storage Architecture

```
Container Filesystem (Ephemeral)
├── /app/
│   └── road_roughness/
│       ├── backend/
│       │   ├── app/
│       │   │   ├── api.py
│       │   │   ├── ndwi.py
│       │   │   └── ...
│       │   ├── main.py
│       │   └── storage/  ◄──────┐
│       │                        │
│       └── frontend/            │
│           ├── index.html       │
│           └── ...              │
│                                │
│                                │ Mounted Volume
│                                │ (Persistent)
└────────────────────────────────┘

Railway Storage Volume
├── projects/
│   ├── 117e688821/
│   │   ├── input/
│   │   │   └── median_line.kml
│   │   ├── ndwi/
│   │   │   └── 2026-10-28.../
│   │   │       └── images/
│   │   └── reports/
│   │       ├── report.pdf
│   │       └── report.xlsx
│   └── [other projects]/
```

---

## Build Process

```
GitHub Repository
    │
    │ Push code
    │
    ▼
Railway detects change
    │
    ▼
Trigger build
    │
    ├─▶ Read Dockerfile
    │
    ├─▶ Stage 1: Builder
    │   │
    │   ├─▶ Pull python:3.10-slim
    │   ├─▶ Install build dependencies
    │   ├─▶ Create virtual environment
    │   └─▶ Install Python packages
    │
    ├─▶ Stage 2: Runtime
    │   │
    │   ├─▶ Pull python:3.10-slim (fresh)
    │   ├─▶ Install runtime dependencies
    │   ├─▶ Copy virtual environment from Stage 1
    │   ├─▶ Copy application code
    │   └─▶ Set permissions
    │
    └─▶ Create final image (~250MB)
        │
        ▼
    Push to Railway registry
        │
        ▼
    Deploy to container
        │
        ├─▶ Mount storage volume
        ├─▶ Inject environment variables
        ├─▶ Start container
        │
        └─▶ Health check
            │
            ├─▶ Success ✓
            │   │
            │   └─▶ Route traffic to new container
            │
            └─▶ Failure ✗
                │
                └─▶ Keep old container running
```

---

## Scaling Architecture

```
Low Traffic:
┌──────────────┐
│ 1 Container  │  ◄── User Requests
│  (256MB RAM) │
└──────────────┘

Medium Traffic:
┌──────────────┐
│ Container 1  │  ◄── User Requests (50%)
└──────────────┘
┌──────────────┐
│ Container 2  │  ◄── User Requests (50%)
└──────────────┘

High Traffic:
┌──────────────┐
│ Container 1  │  ◄── User Requests (33%)
└──────────────┘
┌──────────────┐
│ Container 2  │  ◄── User Requests (33%)
└──────────────┘
┌──────────────┐
│ Container 3  │  ◄── User Requests (33%)
└──────────────┘

Note: All containers share the same storage volume
```

---

## Security Layers

```
┌─────────────────────────────────────────────┐
│ Railway Platform Security                    │
│ - TLS/HTTPS encryption                       │
│ - DDoS protection                            │
│ - Network isolation                          │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│ Container Security                           │
│ - Non-root user (appuser)                   │
│ - Minimal attack surface                    │
│ - No shell access                           │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│ Application Security                         │
│ - CORS configuration                         │
│ - Environment-based secrets                  │
│ - Service account auth (not personal)       │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│ Data Security                                │
│ - Encrypted at rest (Railway volume)        │
│ - Encrypted in transit (HTTPS)              │
│ - Isolated storage per project              │
└─────────────────────────────────────────────┘
```

---

## Monitoring & Health

```
┌─────────────────────────────────────────────┐
│          Railway Monitoring                  │
├─────────────────────────────────────────────┤
│                                              │
│  ┌──────────────┐  ┌──────────────┐        │
│  │   Metrics    │  │     Logs     │        │
│  ├──────────────┤  ├──────────────┤        │
│  │ - CPU usage  │  │ - App logs   │        │
│  │ - Memory     │  │ - Build logs │        │
│  │ - Network    │  │ - Error logs │        │
│  │ - Disk I/O   │  └──────────────┘        │
│  └──────────────┘                           │
│                                              │
│  ┌──────────────────────────────┐          │
│  │      Health Checks           │          │
│  ├──────────────────────────────┤          │
│  │ GET /api/config              │          │
│  │ Every 30 seconds             │          │
│  │ Timeout: 10s                 │          │
│  │ Auto-restart on failure      │          │
│  └──────────────────────────────┘          │
│                                              │
└─────────────────────────────────────────────┘
```

---

## Cost Components

```
┌─────────────────────────────────────────────┐
│              Railway Costs                   │
├─────────────────────────────────────────────┤
│                                              │
│  Compute (CPU + Memory)                     │
│  └─▶ ~$0.000463/GB-hour                    │
│      Based on actual usage                   │
│                                              │
│  Storage Volume                              │
│  └─▶ ~$0.10/GB-month                       │
│      For persistent data                     │
│                                              │
│  Network (Bandwidth)                         │
│  └─▶ Included in plan                       │
│      No additional charge                    │
│                                              │
│  Build Time                                  │
│  └─▶ Free                                   │
│      Unlimited builds                        │
│                                              │
└─────────────────────────────────────────────┘

Example Monthly Cost:
- Container running 24/7: ~$3-5
- Storage (5GB): ~$0.50
- Total: ~$3.50-5.50/month
```

---

## Deployment Timeline

```
Code Push
    │ 0:00
    ▼
Railway detects change
    │ 0:05
    ▼
Start build (Stage 1: Builder)
    │ 0:10 - Install build deps
    │ 0:30 - Install Python packages
    ▼
Stage 2: Runtime
    │ 2:00 - Install runtime deps
    │ 2:15 - Copy files
    ▼
Push image to registry
    │ 2:30 - Upload layers
    ▼
Deploy container
    │ 3:00 - Start container
    │ 3:10 - Health check
    ▼
Live! ✓
    │ 3:30 - Total time
    ▼
Route traffic to new version

Total: ~3-4 minutes from push to live
```

---

This architecture provides:
- ✅ Scalability (auto-scaling containers)
- ✅ Reliability (health checks, auto-restart)
- ✅ Security (TLS, non-root, service accounts)
- ✅ Performance (optimized image, CDN)
- ✅ Observability (logs, metrics, health)
- ✅ Cost-efficiency (pay per use, small image)
