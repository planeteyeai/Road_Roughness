#!/bin/bash
# Railway deployment setup script

set -e

echo "🚂 Setting up Road Roughness Platform for Railway deployment..."

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "⚠ Railway CLI not found. Installing..."
    npm install -g @railway/cli
    echo "✓ Railway CLI installed"
else
    echo "✓ Railway CLI already installed"
fi

# Login to Railway
echo ""
echo "Please login to Railway (this will open your browser):"
railway login

# Create new project
echo ""
echo "Creating new Railway project..."
railway init

# Link to project
echo ""
echo "Linking to Railway project..."
railway link

# Set environment variables
echo ""
echo "Setting up environment variables..."

railway variables --set RR_HOST=0.0.0.0
railway variables --set RR_PORT=8000
railway variables --set CORS_ORIGINS="*"
railway variables --set SERVE_FRONTEND=true
railway variables --set FRONTEND_DIR=../frontend
railway variables --set KEEP_ONLY_LATEST_PROJECT=true
railway variables --set DEFAULT_CLOUD_PCT=40
railway variables --set NEAREST_SEARCH_DAYS=90
railway variables --set NDWI_WORKERS=4

echo ""
echo "⚠ IMPORTANT: You still need to set these variables manually:"
echo "  1. GEE_PROJECT=your-earth-engine-project-id"
echo "  2. GEE_SERVICE_ACCOUNT_JSON=your-service-account-json"
echo ""
echo "Set them with:"
echo "  railway variables --set GEE_PROJECT=your-project-id"
echo "  railway variables --set GEE_SERVICE_ACCOUNT_JSON='paste-json-here'"
echo ""

# Add volume for persistent storage
echo "Setting up persistent storage volume..."
echo "⚠ You need to add a volume manually in the Railway dashboard:"
echo "  1. Go to your project in Railway dashboard"
echo "  2. Click on your service"
echo "  3. Go to Variables tab"
echo "  4. Click 'New Volume'"
echo "  5. Mount path: /app/road_roughness/backend/storage"
echo ""

# Deploy
echo "Ready to deploy!"
echo ""
echo "To deploy, run:"
echo "  railway up"
echo ""
echo "Or push to your GitHub repo if linked to Railway."
echo ""
echo "✓ Setup complete!"
