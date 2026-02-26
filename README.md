<div align="center">

# 🤖 AI YouTube Shorts — Automated Video Pipeline

**Production-grade AI pipeline built with Clean Architecture that auto-generates and publishes motivational YouTube Shorts.**

_Story Generation → Voice Synthesis → Talking Avatar → Video Composition → Auto Upload_

[![CI](https://github.com/tamilarasu/ai-youtube-automation/actions/workflows/ci.yml/badge.svg)](https://github.com/tamilarasu/ai-youtube-automation/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org)
[![Architecture](https://img.shields.io/badge/architecture-Clean%20%2F%20Hexagonal-blueviolet)](docs/architecture.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](pyproject.toml)

</div>

---

## 🎬 Pipeline Flowchart

```mermaid
flowchart TD
    A["📋 Google Sheet<br/>(Topic Queue)"] --> B["1️⃣ Fetch Topic"]
    B --> C["2️⃣ Generate Story<br/>(Ollama LLM)"]
    C --> D{"Randomized<br/>320 Combos"}
    D --> E["3️⃣ Generate SEO<br/>(Title + Tags + Hashtags)"]
    E --> F["4️⃣ Generate 5 Prompts<br/>(Ollama → scene descriptions)"]
    F --> G["5️⃣ Generate 5 Images<br/>(Stable Diffusion)"]
    G --> H["6️⃣ Generate Audio<br/>(Edge TTS / Kokoro)"]
    H --> I["7️⃣ Animate Avatar<br/>(SadTalker)"]
    I --> J["8️⃣ Generate Subtitles<br/>(Whisper STT)"]
    J --> K["9️⃣ Compose Slideshow<br/>(MoviePy)"]
    K --> L{"Features"}

    L --> L1["🎵 Background Music<br/>(looped @ 1% vol)"]
    L --> L2["📝 Styled Subtitles<br/>(TextClip rendering)"]
    L --> L3["🖼️ 5 Images + Avatar<br/>(crossfade + overlay)"]

    L1 --> M["🔟 Upload YouTube<br/>(resumable + scheduler)"]
    L2 --> M
    L3 --> M

    M --> N["1️⃣1️⃣ Backup + Notify"]
    N --> O["💾 Google Drive"]
    N --> P["📱 Telegram"]

    style A fill:#4285F4,color:white
    style C fill:#EA4335,color:white
    style G fill:#9C27B0,color:white
    style H fill:#34A853,color:white
    style I fill:#FBBC05,color:white
    style K fill:#FF7043,color:white
    style M fill:#FF0000,color:white
```

---

## 🧠 System Architecture

```mermaid
graph TB
    subgraph PRESENTATION["🖥️ Presentation Layer"]
        CLI["CLI<br/>(argparse + Rich)"]
        API["FastAPI<br/>REST API"]
    end

    subgraph APPLICATION["⚙️ Application Layer"]
        Pipeline["Pipeline<br/>Orchestrator"]
        UC1["GenerateStory<br/>UseCase"]
        UC2["GenerateVoice<br/>UseCase"]
        UC3["CreateAvatar<br/>UseCase"]
        UC4["PublishVideo<br/>UseCase"]
    end

    subgraph DOMAIN["🏛️ Domain Layer (Core)"]
        Entities["Entities<br/>Topic, Story, Voice,<br/>VideoAsset, SceneSegment"]
        Ports["Ports (Interfaces)<br/>StoryGenerator, VoiceGenerator,<br/>BackgroundGenerator, etc."]
        VO["Value Objects<br/>Language, VideoMode,<br/>AssetType, VideoPrivacy"]
        Exceptions["Typed Exceptions<br/>PipelineError hierarchy"]
    end

    subgraph INFRASTRUCTURE["🔧 Infrastructure Layer"]
        Ollama["Ollama<br/>Adapter"]
        EdgeTTS["Edge TTS<br/>Adapter"]
        Kokoro["Kokoro TTS<br/>Adapter"]
        SadTalker["SadTalker<br/>Adapter"]
        SDXL["SDXL<br/>Adapter"]
        SD["Stable Diffusion<br/>Adapter"]
        MoviePy["MoviePy<br/>Composer"]
        YouTube["YouTube<br/>Uploader"]
        Sheets["Google Sheets<br/>Repository"]
        Drive["Google Drive<br/>Storage"]
        Whisper["Whisper<br/>Subtitles"]
        Telegram["Telegram<br/>Notifier"]
    end

    subgraph CORE["🧱 Core (Cross-cutting)"]
        Config["Settings<br/>(Pydantic)"]
        DI["Container<br/>(DI)"]
        Resilience["Retry<br/>Decorator"]
        GPU["GPU<br/>Manager"]
    end

    CLI --> Pipeline
    API --> Pipeline
    Pipeline --> UC1 & UC2 & UC3 & UC4
    UC1 & UC2 & UC3 & UC4 --> Ports
    Ports -.->|implements| Ollama & EdgeTTS & Kokoro & SadTalker & SDXL & SD & MoviePy & YouTube & Sheets & Drive & Whisper & Telegram
    DI -.->|resolves| Ollama & EdgeTTS & Kokoro & SadTalker & SDXL & SD & MoviePy & YouTube

    style DOMAIN fill:#E8F5E9,stroke:#4CAF50,stroke-width:2px
    style APPLICATION fill:#E3F2FD,stroke:#2196F3,stroke-width:2px
    style INFRASTRUCTURE fill:#FFF3E0,stroke:#FF9800,stroke-width:2px
    style PRESENTATION fill:#F3E5F5,stroke:#9C27B0,stroke-width:2px
    style CORE fill:#ECEFF1,stroke:#607D8B,stroke-width:2px
```

---

## 🔌 Config-Driven Adapter Selection

Swap adapters at runtime via `.env` — zero code changes:

```mermaid
flowchart LR
    subgraph ENV[".env Configuration"]
        E1["TTS_ENGINE=edge"]
        E2["IMAGE_ENGINE=sdxl"]
    end

    subgraph CONTAINER["DI Container"]
        C1{"tts_engine?"}
        C2{"image_engine?"}
    end

    subgraph ADAPTERS["Adapters"]
        A1["EdgeTTSVoiceGenerator"]
        A2["KokoroVoiceGenerator"]
        A3["SDXLBackgroundGenerator"]
        A4["StableDiffusionBackgroundGenerator"]
    end

    E1 --> C1
    E2 --> C2
    C1 -->|"edge"| A1
    C1 -->|"kokoro"| A2
    C2 -->|"sdxl"| A3
    C2 -->|"sd"| A4

    style A1 fill:#34A853,color:white
    style A2 fill:#4285F4,color:white
    style A3 fill:#EA4335,color:white
    style A4 fill:#FBBC05,color:white
```

---

## 📊 Domain Model

```mermaid
classDiagram
    class Topic {
        +str text
        +Language language
        +TopicStatus status
        +mark_processing()
        +mark_done()
        +mark_failed()
    }

    class Story {
        +str text
        +Language language
        +int word_count
        +validate(min, max)
    }

    class Voice {
        +Path audio_path
        +float duration_seconds
        +Language language
        +str voice_id
    }

    class VideoAsset {
        +Path path
        +AssetType asset_type
        +float duration_seconds
        +bool exists
    }

    class SceneSegment {
        +float start
        +float end
        +int image_number
        +str prompt
        +float duration
    }

    class VideoOutput {
        +Path local_path
        +str youtube_url
        +str drive_path
        +VideoMetadata metadata
        +str scheduled_time
        +VideoMode video_mode
    }

    class PipelineResult {
        +Topic topic
        +Story story
        +Voice voice
        +list~VideoOutput~ outputs
        +bool success
        +str error
    }

    Topic --> Story : generates
    Story --> Voice : synthesizes
    Voice --> VideoAsset : produces
    VideoAsset --> VideoOutput : composes
    PipelineResult --> Topic
    PipelineResult --> VideoOutput
```

---

## 🚨 Error Handling Strategy

```mermaid
flowchart TD
    PE["PipelineError (base)"] --> CE["ConfigurationError"]
    PE --> TFE["TopicFetchError"]
    PE --> SGE["StoryGenerationError"]
    PE --> VGE["VoiceGenerationError"]
    PE --> AAE["AvatarAnimationError"]
    PE --> SE["SubtitleError"]
    PE --> BGE["BackgroundGenerationError"]
    PE --> VCE["VideoCompositionError"]
    PE --> UE["UploadError"]
    PE --> NE["NotificationError ⚡"]

    NE -.->|"non-fatal"| CONT["Pipeline continues"]
    CE & TFE & SGE & VGE & AAE & BGE & VCE & UE -->|"fatal"| FAIL["Pipeline halts"]
    SE -.->|"graceful"| CONT

    style PE fill:#F44336,color:white
    style NE fill:#FF9800,color:white
    style SE fill:#FF9800,color:white
    style CONT fill:#4CAF50,color:white
    style FAIL fill:#B71C1C,color:white
```

---

## ⚡ Tech Stack

| Layer         | Technology                  | Purpose                                        |
| ------------- | --------------------------- | ---------------------------------------------- |
| **LLM**       | Ollama (Gemma 3 12B)        | Story generation, SEO metadata, image prompts  |
| **TTS**       | Edge TTS / Kokoro           | Voice synthesis (cloud or local, configurable) |
| **Avatar**    | SadTalker + GFPGAN          | Talking-head video generation                  |
| **STT**       | OpenAI Whisper              | Subtitle generation from audio                 |
| **Image Gen** | SDXL / Stable Diffusion 2.1 | 5 scene images per video (local GPU)           |
| **Video**     | MoviePy + FFmpeg            | Slideshow + avatar overlay + bgm + subtitles   |
| **Queue**     | Google Sheets API           | Topic management                               |
| **Upload**    | YouTube Data API v3         | Resumable upload with scheduling               |
| **Notify**    | Telegram Bot API            | Pipeline notifications                         |
| **Storage**   | Google Drive API            | Video backup                                   |
| **Config**    | Pydantic Settings           | Type-safe .env loading                         |
| **API**       | FastAPI + Uvicorn           | REST API for remote triggering                 |
| **DI**        | Custom Container            | Config-driven adapter selection                |
| **CI/CD**     | GitHub Actions              | Lint (Ruff) + Tests (Pytest)                   |

> **Total cost: $0** — All components are free-tier or open-source. No external API keys required.

---

## 🏗️ Clean Architecture Principles

| Principle                  | Implementation                                  |
| -------------------------- | ----------------------------------------------- |
| **Dependency Inversion**   | Domain ports (ABC) → Infrastructure adapters    |
| **Single Responsibility**  | One use case per operation                      |
| **Open/Closed**            | New adapters without modifying business logic   |
| **Interface Segregation**  | 13 focused port interfaces                      |
| **Separation of Concerns** | 5 distinct layers with clear boundaries         |
| **Dependency Injection**   | Container wires ports → adapters at startup     |
| **Fail-Safe Design**       | Typed exceptions, retry with backoff, fallbacks |
| **GPU Lifecycle**          | Context managers for VRAM management            |

---

## 📁 Project Structure

```
ai-youtube-automation-clean/
├── src/ai_shorts/
│   ├── domain/                    # 🏛️ Business core (zero dependencies)
│   │   ├── entities.py            # Topic, Story, Voice, VideoAsset, SceneSegment, VideoOutput
│   │   ├── value_objects.py       # Language, VideoMode, AssetType, VideoPrivacy
│   │   ├── ports.py               # 13 abstract interfaces (contracts)
│   │   └── exceptions.py          # 9 typed exceptions (one per pipeline stage)
│   │
│   ├── application/               # ⚙️ Use cases + orchestrator
│   │   ├── use_cases.py           # 7 use cases (GenerateStory, GenerateSceneImages, etc.)
│   │   └── pipeline.py            # PipelineOrchestrator (11-step sequencing)
│   │
│   ├── infrastructure/adapters/   # 🔧 External service implementations
│   │   ├── ollama.py              # LLM (story + metadata + 5 scene prompts)
│   │   ├── edge_tts.py            # Cloud TTS (Microsoft Edge)
│   │   ├── kokoro_tts.py          # Local TTS (CPU-friendly)
│   │   ├── sadtalker.py           # Avatar animation (talking head)
│   │   ├── whisper.py             # Speech-to-text subtitles
│   │   ├── sdxl.py                # SDXL image gen (local GPU)
│   │   ├── flux_image.py          # SD 2.1 + SceneImageGenerator (local GPU)
│   │   ├── moviepy_composer.py    # Slideshow + avatar overlay + bgm + subtitles
│   │   ├── youtube.py             # YouTube upload + scheduling
│   │   ├── google_sheets.py       # Topic queue (Google Sheets)
│   │   ├── google_drive.py        # Cloud backup
│   │   └── telegram.py            # Notifications
│   │
│   ├── presentation/              # 🖥️ User interfaces
│   │   └── api.py                 # FastAPI REST API (/generate, /batch, /health)
│   │
│   ├── core/                      # 🧱 Cross-cutting concerns
│   │   ├── config.py              # Pydantic Settings (type-safe .env)
│   │   ├── container.py           # DI Container (config-driven adapter wiring)
│   │   ├── resilience.py          # retry_with_backoff decorator
│   │   ├── gpu.py                 # GPU memory management
│   │   ├── timer.py               # Pipeline timing instrumentation
│   │   └── logging.py             # Structured logging setup
│   │
│   └── cli.py                     # CLI (run, setup, serve, batch)
│
├── assets/images/avatar.png       # Default avatar image
├── tests/                         # 31 unit tests
├── docs/                          # Architecture docs + setup guide
├── .github/workflows/ci.yml       # GitHub Actions CI
└── pyproject.toml                 # V2.0 — modern Python packaging
```

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/tamilarasu/ai-youtube-automation.git
cd ai-youtube-automation

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install
pip install -e ".[dev]"
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your API keys (see docs/SETUP.md)
```

### 3. Validate

```bash
ai-shorts setup
```

### 4. Run

```bash
ai-shorts run                              # Full pipeline
ai-shorts run --mode test                   # Test mode (story → voice → avatar only)
ai-shorts run --video-mode slideshow        # Slideshow mode (image-based, no avatar)
ai-shorts run --schedule "2026-03-01T10:00:00+05:30"  # Scheduled publish
```

### 5. API Mode

```bash
ai-shorts serve --port 8000                 # Start FastAPI server
# POST http://localhost:8000/generate {"topic": "...", "language": "en"}
```

### 6. Batch Mode

```bash
ai-shorts batch --input topics.json         # Process topics from JSON file
```

---

## 🧪 Testing

```bash
pytest tests/ -v            # Run 31 unit tests
pytest tests/ --cov         # Tests + coverage report
ruff check src/             # Lint
ruff format --check src/    # Format check
```

---

## 🌐 Supported Languages

| Language | Code | Voice | Subtitles | Story |
| -------- | ---- | ----- | --------- | ----- |
| Tamil    | `ta` | ✅    | ✅        | ✅    |
| English  | `en` | ✅    | ✅        | ✅    |
| Hindi    | `hi` | ✅    | ✅        | ✅    |

---

## ✨ V2.0 Features

| #   | Feature                     | What it does                                                |
| --- | --------------------------- | ----------------------------------------------------------- |
| 1   | **Randomized story styles** | 8 styles × 5 tones × 8 characters = 320 unique combinations |
| 2   | **Background music**        | Auto-looped at 1% volume via CompositeAudioClip             |
| 3   | **Styled subtitles**        | MoviePy TextClip with stroke, word-wrapping                 |
| 4   | **Scheduled upload**        | YouTube `publishAt` with auto privacy management            |
| 5   | **Kokoro TTS**              | Local CPU-friendly TTS, 100-word chunking                   |
| 6   | **Stable Diffusion**        | Local GPU image gen (SD 2.1, no API keys needed)            |
| 7   | **Image prompt gen**        | LLM summarizes story → image prompt                         |
| 8   | **FastAPI REST API**        | Remote pipeline triggering via HTTP                         |
| 9   | **Batch processing**        | JSON file → sequential pipeline runs                        |
| 10  | **Scene segments**          | Per-segment image generation domain model                   |
| 11  | **Slideshow mode**          | Image-based video without avatar                            |
| 12  | **Resumable upload**        | Chunked YouTube upload with progress %                      |

---

## 🛡️ Resilience Features

- **Retry with Exponential Backoff** — All external API calls (3 attempts, 2-60s delay)
- **GPU Memory Management** — Automatic VRAM cleanup between pipeline stages
- **Whisper Model Fallback** — `large-v3` → `medium` → `base` on GPU OOM
- **SadTalker Fallback** — Ken Burns zoom effect if GPU inference fails
- **Graceful Degradation** — Subtitles, notifications, and Drive save are non-fatal
- **Typed Exceptions** — Each pipeline stage has its own error type (9 total)
- **Config-Driven Swapping** — Switch adapters via `.env` without code changes

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built with Clean Architecture principles** ❤️

_Demonstrating production-grade Python engineering: SOLID, DDD, Hexagonal Architecture, and System Design_

</div>
