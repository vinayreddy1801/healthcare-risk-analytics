# load_synthea_to_bq.ps1
# Run this from PowerShell after uploading Synthea CSVs to GCS.
# Loads all 6 required Synthea tables into BigQuery raw dataset.

$PROJECT = "healthcare-risk-vinay"
$BUCKET  = "healthcare-risk-raw-vinay"
$DATASET = "raw"

$files = @("patients","encounters","conditions","procedures","medications","providers")

foreach ($f in $files) {
    Write-Host "Loading $f..." -ForegroundColor Cyan
    bq load `
        --autodetect `
        --source_format=CSV `
        --skip_leading_rows=1 `
        --allow_quoted_newlines `
        --allow_jagged_rows `
        "${PROJECT}:${DATASET}.${f}" `
        "gs://${BUCKET}/synthea/${f}.csv"
    Write-Host "✓ $f loaded" -ForegroundColor Green
}

Write-Host "`nAll tables loaded. Verify with:" -ForegroundColor Yellow
Write-Host "bq ls ${PROJECT}:${DATASET}"
