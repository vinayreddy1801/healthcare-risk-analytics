#!/bin/bash
# setup.sh — One-command project bootstrap
set -e

echo "🏥 Setting up healthcare_risk project..."

# Python venv
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Copy env template
if [ ! -f .env ]; then
  cp .env.example .env
  echo "📋 Created .env from template — fill in your GCP_PROJECT_ID"
fi

# dbt deps
cd dbt
dbt deps
echo "✓ dbt packages installed"
cd ..

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit .env with your GCP_PROJECT_ID"
echo "  2. Run: gcloud auth application-default login"
echo "  3. Run: cd dbt && dbt seed && dbt run && dbt test"
echo "  4. Run: cd streamlit && streamlit run app.py"
