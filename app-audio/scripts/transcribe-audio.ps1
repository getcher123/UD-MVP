param(
    [Parameter(Mandatory = $true)]
    [string]$AudioPath,

    [switch]$Diarize
)

$serviceUri = "http://localhost:8001/v1/transcribe"

try {
    $resolvedAudio = (Resolve-Path -LiteralPath $AudioPath -ErrorAction Stop).ProviderPath
} catch {
    Write-Error "Audio file '$AudioPath' not found."
    exit 1
}

try {
    $audioBytes = [System.IO.File]::ReadAllBytes($resolvedAudio)
} catch {
    Write-Error "Failed to read audio file '$resolvedAudio': $($_.Exception.Message)"
    exit 1
}

$base64 = [Convert]::ToBase64String($audioBytes)
$fileName = [System.IO.Path]::GetFileName($resolvedAudio)
$settings = [ordered]@{
    diar          = [bool]$Diarize
    language      = "ru"
    whisper_model = "medium"
}

$body = [ordered]@{
    audio_base64 = $base64
    filename     = $fileName
    settings     = $settings
} | ConvertTo-Json -Depth 6

try {
    $responseRaw = Invoke-WebRequest `
        -Method Post `
        -Uri $serviceUri `
        -ContentType "application/json" `
        -Body $body `
        -ErrorAction Stop
} catch {
    Write-Error "Request to $serviceUri failed: $($_.Exception.Message)"
    exit 1
}

$memoryStream = New-Object System.IO.MemoryStream
$responseRaw.RawContentStream.CopyTo($memoryStream)
$jsonUtf8 = [System.Text.Encoding]::UTF8.GetString($memoryStream.ToArray())

try {
    $response = $jsonUtf8 | ConvertFrom-Json
} catch {
    Write-Error "Failed to parse service response: $($_.Exception.Message)"
    exit 1
}

$encoding = New-Object System.Text.UTF8Encoding($false)

if ($Diarize) {
    if (-not $response.srt) {
        Write-Warning "Service response does not contain 'srt' data."
        exit 1
    }
    $outputPath = [System.IO.Path]::ChangeExtension($resolvedAudio, ".srt")
    [System.IO.File]::WriteAllText($outputPath, $response.srt, $encoding)
    Write-Host "Saved diarized SRT to $outputPath"
} else {
    if (-not $response.text) {
        Write-Warning "Service response does not contain 'text' data."
        exit 1
    }
    $outputPath = [System.IO.Path]::ChangeExtension($resolvedAudio, ".txt")
    [System.IO.File]::WriteAllText($outputPath, $response.text, $encoding)
    Write-Host "Saved transcript to $outputPath"
}
