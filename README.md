# 🔆 open-vtt: AI-generated Extended Audio Descriptions

_This project is archived / unsupported. For support with visual intelligence, see https://relantic.com_

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
Vertex AI accepts local media as inline request data. `open-vtt` handles the
configured inline-media budget automatically:
- **Smart Downsampling**: If your video is greater than the configured 7 MB default, it triggers an `ffmpeg` cascade.
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
- PyAV (`av`) for media probing and local Whisper decoding
- `ffmpeg` on your PATH for embedded-subtitle extraction and video downsampling
- Google Cloud Application Default Credentials (ADC) with Vertex AI access

### Installation

1. Install the Python dependencies:
   ```bash
   pip install -r requirements.txt
   # For Mac users with Apple Silicon (High Performance):
   pip install mlx-whisper
   ```

2. Configure ADC and select the Google Cloud project:
   ```bash
   gcloud auth application-default login
   export GOOGLE_CLOUD_PROJECT=your-project-id
   export GOOGLE_CLOUD_LOCATION=global
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
2. Downsample video if needed for the configured inline-media budget.
3. Send the local media inline to Gemini on Vertex AI for grounding and enhancement.
4. Save `{video}.log` (full reasoning) and `{video}.vtt` (final file).

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
        "project": null,
        "location": "global",
        "model": "gemini-2.5-flash",
        "temperature": 0.7,
        "thinking": "high",   // "high" | "low"
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

Tests `to_vtt_time()`, VTT extraction, config loading, and path handling.

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
