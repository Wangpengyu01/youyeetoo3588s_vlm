import sys
import time
import subprocess

sys.path.insert(0, '/userdata/agent')
from tts.tts_engine import TtsEngine

print('=== 1. Synthesizing test audio: 看看桌上放了什么 ===')
engine = TtsEngine()
wav_path = engine.synthesize('看看桌上放了什么', '/tmp/test_vision_ask.wav')
print(f'Generated: {wav_path}')

print('=== 2. Playing audio via speaker to microphone ===')
subprocess.run(['bash', '/userdata/voice/scripts/play_wav.sh', str(wav_path)])

print('=== 3. Waiting 6s for Xiao Lan vision processing & reply ===')
time.sleep(6)

print('=== 4. Recent Orchestrator Logs ===')
res = subprocess.run(['tail', '-n', '30', '/userdata/agent/logs/orchestrator.log'], capture_output=True, text=True)
print(res.stdout)
