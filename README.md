# 🔆 open-vtt: AI-generated Extended Audio Descriptions

_This project is archived / unsupported. For support with visual intelligence, see https://relantic.com_

## AMPAV deployment and large-media testing

The AMPAV fork preserves the original Gemini API-key workflow and adds a
Vertex AI workflow authenticated with Google Application Default Credentials
(ADC). Both workflows use `gemini-3.1-pro-preview` by default.

### Brian: deploy on the AMPAV server

1. Install FFmpeg and create an isolated Python environment:

   ```bash
   sudo apt-get update
   sudo apt-get install -y ffmpeg python3-venv
   git clone https://github.com/AMPAV/open-vtt.git
   cd open-vtt
   # Before merge only: git switch AMPAV-219
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

   Use branch `AMPAV-219` for pre-merge testing; use `main` after the change is
   merged.

2. Configure the server process. An attached service account is preferred. If
   the server uses user ADC instead, run `gcloud auth application-default
   login --no-launch-browser` as the same operating-system user that runs
   open-vtt.

   ```bash
   export OPEN_VTT_GEMINI_BACKEND=vertex
   export GOOGLE_CLOUD_PROJECT=bl-libr-ampav-dev
   export GOOGLE_CLOUD_LOCATION=global
   export OPEN_VTT_GCS_BUCKET=bl-libr-ampav-dev-ampav
   export OPEN_VTT_GCS_PREFIX=open-vtt/staging
   ```

   The ADC principal needs permission to call Vertex AI and create, read, and
   delete objects in the staging bucket. `roles/aiplatform.user` on the project
   and `roles/storage.objectUser` on the bucket provide the usual required
   permissions. The Vertex AI and Cloud Storage APIs must be enabled. Store
   these environment settings in the server's service configuration rather
   than committing deployment-specific values.

3. Verify the deployment and start the player:

   ```bash
   .venv/bin/python open-vtt.py --check
   .venv/bin/python open-vtt.py --serve --port 8000
   ```

   The first file without embedded subtitles downloads Whisper's approximately
   139 MB `base` model into the service user's cache. The server therefore
   needs outbound access and a writable cache directory for that first run.

If a Gemini API key becomes available, set `GEMINI_API_KEY` and use
`OPEN_VTT_GEMINI_BACKEND=developer`. That path uses the original Gemini Files
API and does not require a GCS staging bucket. With backend `auto`, an API key
is preferred when present; otherwise open-vtt uses Vertex AI with ADC.

### Jon: test large media

Set the Vertex/ADC environment variables above and run:

```bash
.venv/bin/python open-vtt.py --convert /path/to/test-video.mp4
```

Use a 20–400 MB file to exercise GCS staging without FFmpeg downsampling. Use a
file over 400 MB to also exercise the original FFmpeg downsampling cascade.
The run should report the `vertex` backend, a temporary `gs://` staging URI,
and successful deletion of that temporary object. The generated baseline VTT,
full Gemini response log, and enhanced VTT are written beside the input media.
Do not remove the input until those outputs have been reviewed.

GCS avoids the inline request-size limit, but model limits still apply. Gemini
3.1 Pro currently supports approximately 45 minutes of video with audio or one
hour without audio. The tool deletes only the GCS object it creates; the local
input is never deleted.

**open-vtt** is a robust AI-powered pipeline for generating **Extended Audio Descriptions (Extended AD)**, addressing a critical requirement for the upcoming regulatory and compliance targets for accessibility.

It uses ffmpeg, Gemini, and Whisper to generate high-quality, accessible extended AD WebVTT subtitles that capture visual and semantic context.

Once generated, the enhanced VTT files can be used with the built-in player or with any other player that supports WebVTT subtitles.

_🍌-generated Overview Diagram_

<img height="300" alt="image" src="https://github.com/user-attachments/assets/f333e38d-0c06-4ed2-a097-2d7c4a92bc65" />


## 🎯 Why open-vtt?

Standard AI captioning tools often fail to meet professional accessibility guidelines for Extended Audio Descriptions (Extended AD):
- They ignore **visual context** (generating only dialogue).
- They lack **spatial awareness or orientation** ("Who is speaking? Where are they?").
- They hallucinate timestamps or drift over long videos.
- They do not differentiate between **curatorial context** (educational notes) and **visual description** (what is happening).

---
## Demo link & Player Screenshot ([try demo here](https://arnabdotorg.github.io/open-vtt/player.html))

<img height="300" alt="image" src="https://github.com/user-attachments/assets/15a36624-5e1f-4cce-ac70-2c873a5af92e" />

---

## 🏗 Architecture & Nuances

This tool is designed to work around the limitations of modern LLMs while maximizing their reasoning potential.

### 1. 🧠 Intelligent Pipeline with Gemini
We use Gemini for its multimodal capabilities, but we don't trust it blindly.
- **Two-Pass Generation**: The prompt forces a "Chronological Event Log" pass first to stabilize the model's understanding of time, followed by the rigorous VTT generation pass.
- **Grounding**: Uses Google Search to verify proper nouns, historical facts, and spelling (e.g., ensuring "Elijah Pierce" is spelled correctly based on context).
- **Reasoning over Narratives**: The prompt instructs the model to reason frame-by-frame, ensuring that descriptions fill the *gaps* in dialogue without colliding with speech.

### 2. 🗂️ Handling File Limits
The Gemini Developer API uses its managed Files service. The Vertex AI backend
stages larger local media in GCS and can send small files inline when no bucket
is configured:
- **Smart Downsampling**: If your video is greater than the configured 400 MB default, it triggers an `ffmpeg` cascade.
- **Resolution Preservation**: It tries reducing both resolution and frame rate until it is allowed by the file size budget.

### 3. 🗣️ Robust Transcription Fallback
A VTT file needs a "Canonical Timeline" to be accurate.
- **Extraction**: First, it checks for embedded subtitles (e.g., `mov_text`).
- **Whisper Fallback**: If no subtitles exist, it calls **OpenAI Whisper** locally.
  - On Apple Silicon, it uses `mlx-whisper` for 10x faster inference.
  - On other platforms, it falls back to standard `whisper`.

### 4. 🦾 W3C & WCAG Compliance
The output generates a structured document using standard WebVTT semantic tags:
- **`<v Description>`**: Visual descriptions for the blind (mapped to TTS).
- **`<v Speaker>`**: Speaker identification for the deaf.
- **`<v Curatorial>`**: Special extended notes for researchers (pauses the player).
- **`[Sound Effects]`**: DCMP-style bracketed cues for non-speech audio.

### 5. 😶‍🌫️ Hallucinations and Errors
LLMs make mistakes. We reduce these by using native subtitles if available, grounding the output using Web Search, and using a two-phase reasoning process. Since human transcriptions also have errors, these techniques can be adapted to human transcription as well. The goal for this tool is not to produce gold-standard descriptions, but to provide a path to feasibility when **no reasonable alternative exists**. We recommend using this tool as a starting point, and then manually editing the output to improve accuracy.

---

## 🚀 Usage

### Prerequisites
- Python 3.9+
- `ffmpeg` and `ffprobe` on your PATH
- A Gemini API key, or ADC with Vertex AI access
- A GCS staging bucket for large media through the ADC/Vertex backend
- PyAV (`av`) as a reduced-capability fallback when FFmpeg is unavailable

### Installation

1. Install the Python dependencies:
   ```bash
   pip install -r requirements.txt
   # For Mac users with Apple Silicon (High Performance):
   pip install mlx-whisper
   ```

2. Choose either the original API-key backend:

   ```bash
   cp secrets.example.json secrets.json
   # Add the key to secrets.json, or export GEMINI_API_KEY instead.
   export OPEN_VTT_GEMINI_BACKEND=developer
   ```

   Or configure the ADC/Vertex backend:

   ```bash
   gcloud auth application-default login
   export OPEN_VTT_GEMINI_BACKEND=vertex
   export GOOGLE_CLOUD_PROJECT=your-project-id
   export GOOGLE_CLOUD_LOCATION=global
   export OPEN_VTT_GCS_BUCKET=your-staging-bucket
   ```

On Google Cloud compute, use the attached service account as ADC instead of
running the interactive login command. The project and location can also be
set as `gemini.project` and `gemini.location` in `config.json`.

### Conversion Mode

Convert a video to a fully accessible VTT file:

```bash
python open-vtt.py --convert video.mp4
```

This will:
1. Extract or Transcribe audio.
2. Downsample video if needed (>400 MB by default).
3. Upload the prepared media through Gemini Files or temporary GCS staging.
4. Send the prepared media and baseline VTT to Gemini for grounding and enhancement.
5. Save `{video}.log` (full reasoning) and `{video}.vtt` (final file).

### Player Mode

Serve a local player to test your VTT files with specialized features (TTS, overlays, auto-scroll):

```bash
python open-vtt.py --serve
```

Then open `http://localhost:8000`.

---

## ⚙️ Configuration

Tweak the model behavior in `config.json`:

```json
{
    "gemini": {
        "backend": "auto",
        "project": null,
        "location": "global",
        "model": "gemini-3.1-pro-preview",
        "gcs_bucket": null,
        "gcs_prefix": "open-vtt/staging",
        "inline_max_size_mb": 15,
        "temperature": 0.7,
        "thinking": "high",
        "grounding": {
            "enabled": true,
            "source": "google_search"
        }
    }
}
```

---

## 🧪 Testing

### Python Tests
```bash
python open-vtt.py --test
```

Tests `to_vtt_time()`, VTT extraction, config loading, and path handling. The
additional unit suite in `tests/` covers API-key, ADC/GCS, cleanup, and media
fallback behavior without calling Gemini.

### JavaScript Tests
Open the player in a browser and run in console:
```javascript
OpenVTTTests.runAll()
```

Tests VTT parsing, voice type detection, and time utilities.

---

## 📜 Standards Reference

- **W3C WebVTT**: The Web Video Text Tracks Format standard for VTT files.
- **WCAG 2.2**: Success Criterion 1.2.7 (Extended Audio Description).
- **ADC Guidelines**: Audio Description Coalition standards for present-tense, neutral observation.
- **DCMP**: Described and Captioned Media Program guidelines for sound effects.
