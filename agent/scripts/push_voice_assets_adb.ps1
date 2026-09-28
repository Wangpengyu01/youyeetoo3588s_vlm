# Push voice runtime + ASR/TTS models after userdata wipe (~800MB+)
param(
    [string]$VoiceRoot = "C:\Users\wwff\Documents\youyeetoo3588s\voice"
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path "$VoiceRoot\sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu\lib\libsherpa-onnx-c-api.so")) {
    throw "Missing sherpa under $VoiceRoot"
}
adb shell "mkdir -p /userdata/voice"
Write-Host "[voice] sherpa runtime"
adb push "$VoiceRoot\sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu" /userdata/voice/sherpa-onnx-v1.12.8-linux-aarch64-shared-cpu
Write-Host "[voice] silero vad"
adb push "$VoiceRoot\silero_vad.onnx" /userdata/voice/silero_vad.onnx
Write-Host "[voice] streaming paraformer"
adb push "$VoiceRoot\sherpa-onnx-streaming-paraformer-bilingual-zh-en" /userdata/voice/sherpa-onnx-streaming-paraformer-bilingual-zh-en
if (Test-Path "$VoiceRoot\vits-melo-tts-zh_en") {
    Write-Host "[voice] vits TTS (demo fallback)"
    adb push "$VoiceRoot\vits-melo-tts-zh_en" /userdata/voice/vits-melo-tts-zh_en
}
$RepoVoiceScripts = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$RepoVoiceScripts = Join-Path $RepoVoiceScripts "voice\scripts"
if (Test-Path $RepoVoiceScripts) {
    adb push $RepoVoiceScripts /userdata/voice/scripts
}
adb shell "sed -i 's/backend: matcha/backend: vits/; s|matcha-icefall-zh-baker|vits-melo-tts-zh_en|' /userdata/agent/config/agent.yaml 2>/dev/null; sed -i 's/\r$//' /userdata/voice/scripts/*.sh 2>/dev/null; true"
Write-Host "[voice] done"
