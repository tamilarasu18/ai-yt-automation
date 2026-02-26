# 🚀 Colab Quickstart

Run in Google Colab with a T4 GPU.

> **Runtime → Change runtime type → T4 GPU → Save**

## Cell 1: Mount Drive & Install

```python
from google.colab import drive
drive.mount('/content/drive')

!pip install -q -e "/content/drive/MyDrive/ai-youtube-automation[gpu]"
```

## Cell 2: Run Pipeline

```python
from ai_shorts.cli import _cmd_run
_cmd_run(mode="full", env_file="/content/drive/MyDrive/ai-youtube-automation/.env")
```

That's it. The pipeline handles everything automatically.
