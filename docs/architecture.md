# 🏗️ Architecture

## Design Philosophy

This project follows **Clean Architecture** (Robert C. Martin) with **Hexagonal Architecture** (Ports & Adapters) to achieve:

- **Independence from frameworks** — Business logic has zero external dependencies
- **Testability** — Every layer can be tested in isolation with mocked dependencies
- **Independence from UI** — The core pipeline can be driven by CLI, API, or Colab
- **Independence from external agencies** — Swapping Ollama for GPT-4, or SadTalker for Wav2Lip, requires changing only one adapter

---

## Layer Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Presentation Layer                     │
│  CLI (argparse + Rich)    │    Google Colab Cell          │
├─────────────────────────────────────────────────────────┤
│                    Application Layer                     │
│  PipelineOrchestrator  │  Use Cases (single operations)  │
│  DTOs                  │  Pipeline Modes (full / test)   │
├─────────────────────────────────────────────────────────┤
│                      Domain Layer                        │
│  Entities (Topic, Story, Voice, Video)                   │
│  Value Objects (Language, Status, Privacy)                │
│  Ports/Interfaces (ABC-based contracts)                  │
│  Domain Exceptions (typed error hierarchy)                │
├─────────────────────────────────────────────────────────┤
│                   Infrastructure Layer                    │
│  Google Sheets (TopicRepository)                         │
│  Ollama (LLMService, StoryGenerator, MetadataGenerator)  │
│  Edge TTS (VoiceGenerator)                               │
│  SadTalker (AvatarAnimator)                              │
│  Whisper (SubtitleGenerator)                             │
│  SDXL (BackgroundGenerator)                              │
│  MoviePy (VideoComposer)                                 │
│  YouTube (VideoUploader)                                 │
│  Google Drive (StorageService)                           │
│  Telegram (NotificationService)                          │
├─────────────────────────────────────────────────────────┤
│                     Cross-Cutting                        │
│  Pydantic Settings  │  Structured Logging  │  Retry      │
│  GPU Memory Manager │  DI Container  │  Pipeline Timer   │
└─────────────────────────────────────────────────────────┘
```

---

## Key Architecture Decisions

### ADR-1: Hexagonal Architecture (Ports & Adapters)

**Context:** The pipeline integrates 10+ external services (Ollama, SadTalker, YouTube API, etc.). Tightly coupling business logic to these services would make testing difficult and vendor lock-in inevitable.

**Decision:** Define abstract interfaces (Ports) in the domain layer. Implement concrete adapters in the infrastructure layer. Wire them together via a DI Container.

**Consequence:** Any external service can be replaced by implementing a new adapter. Unit tests use mock implementations of ports.

### ADR-2: GPU Memory Lifecycle Management

**Context:** Colab T4 GPUs have only 15GB VRAM. Running Ollama (LLM), SadTalker, Whisper, and SDXL concurrently causes OOM crashes.

**Decision:** Each GPU-intensive step runs inside a `gpu_context()` manager that automatically frees VRAM afterwards. The pipeline unloads models between stages.

**Consequence:** Predictable GPU memory usage. Pipeline stages can run sequentially on constrained hardware.

### ADR-3: Pydantic Settings for Configuration

**Context:** Configuration was scattered across a JSON file with hardcoded paths and no validation.

**Decision:** Use `pydantic-settings` with nested config groups, type validation, and `.env` file support.

**Consequence:** Configuration errors are caught at startup. All settings are type-safe and documented.

### ADR-4: Use Case Pattern

**Context:** The original `main.py` had all logic in one `run_pipeline()` function.

**Decision:** Split into individual Use Cases, each handling one operation with clear input/output contracts.

**Consequence:** Each operation is independently testable, reusable, and can be orchestrated in different pipeline modes.

---

## Data Flow

```
Google Sheets ──► TopicRepository.get_next_pending()
                         │
                         ▼
                  StoryGenerator.generate()
                         │
                         ▼
                  VoiceGenerator.synthesize()
                         │
                         ├──► AvatarAnimator.animate()
                         ├──► SubtitleGenerator.transcribe()
                         └──► BackgroundGenerator.generate()
                                      │
                                      ▼
                              VideoComposer.compose()
                                      │
                              ┌───────┼───────┐
                              ▼       ▼       ▼
                         YouTube   Drive  Telegram
```

## Dependency Injection

The `Container` class in `core/container.py` lazily resolves all ports to their concrete adapters. Each adapter is created once and cached:

```python
settings = Settings()           # Load from .env
container = Container(settings)  # Wire dependencies
orchestrator = PipelineOrchestrator(container)
result = orchestrator.run(mode="full")
```
