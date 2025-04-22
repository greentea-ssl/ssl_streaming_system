FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# PulseAudioクライアントライブラリ等のインストール (ホストOSに合わせる。Linuxの例)
# 音声再生のために必要になる場合がある
RUN apt-get update && apt-get install -y --no-install-recommends libpulse-dev alsa-utils && rm -rf /var/lib/apt/lists/*
# または apt-get install -y portaudio19-dev など、playsound3/代替ライブラリの依存関係を確認

COPY common/data_models.py ./common/
COPY audio_playback/audio_playback.py .

# CMD ["python", "main_audio_playback.py"] # 仮
CMD ["tail", "-f", "/dev/null"]