# lvgl_kawaii_face (ESPHome)

ESPHome wrapper around the [lvgl_kawaii_face](../../lvgl_kawaii_face-main) C
component — an animated kawaii face for LVGL 9. It draws eyes, eyebrows, blush
and a mouth on LVGL canvases with per-emotion animations, and exposes the
emotion as an ESPHome **action** so the face can react to your automations,
most notably the **voice assistant** pipeline.

The C source (`lvgl_kawaii_face.c` / `lvgl_kawaii_face.h`) is vendored here so
the component is self-contained when fetched via `external_components`.

## Configuration

```yaml
external_components:
  - source: github://youkorr/esphome-lvgl-kawaii
    components: [lvgl_kawaii_face]
  - source: github://youkorr/lvgl_9.5
    components: [lvgl, image, font]

# A plain LVGL object the face fills and scales to:
lvgl:
  pages:
    - id: page_face
      widgets:
        - obj:
            id: face_panel
            width: 240
            height: 240
            align: CENTER
            bg_opa: TRANSP
            border_width: 0
            pad_all: 0

lvgl_kawaii_face:
  id: face
  parent_id: face_panel       # optional; omit to fill the active screen
  initial_emotion: neutral
  animation_speed: 30ms       # timer interval (~33 FPS)
  blink_interval: 3000ms
  auto_blink: true
  smooth: true                # smooth transitions between expressions
```

| Option | Default | Description |
|---|---|---|
| `parent_id` | *(screen)* | id of an LVGL widget the face fills. Omit to use the active screen. |
| `animation_speed` | `30ms` | Animation update interval. |
| `blink_interval` | `3000ms` | Auto-blink period. |
| `auto_blink` | `true` | Enable automatic blinking. |
| `smooth` | `true` | Smoothly transition between expressions. |
| `initial_emotion` | `neutral` | Expression shown at boot. |
| `response_keywords` | *(FR/EN defaults)* | Map of `emotion: [keywords]` used by `set_emotion_from_text` to pick an expression from a response's text. |
| `response_fallback` | `speaking` | Expression used when a response matches no keyword. |

> The C component is a singleton — configure a single `lvgl_kawaii_face:` block.

## Action: `lvgl_kawaii_face.set_emotion`

```yaml
- lvgl_kawaii_face.set_emotion:
    id: face
    emotion: happy            # templatable (lambda allowed)
```

### Emotions

`neutral`, `happy`, `worried`, `sad`, `surprised`, `angry`, `sleepy`, `wink`,
`love`, `playful`, `silly`, `smirk`, `cry`, `working_hard`, `excited`,
`confused`, `cool`.

Voice-assistant friendly aliases: `idle`→neutral, `listening`→surprised,
`thinking`→working_hard, `speaking`/`talking`→happy, `error`→sad.

## Action: `lvgl_kawaii_face.set_emotion_from_text`

Makes the face **follow the content of the assistant's (LLM) response**: it
scans the text for keywords and applies the matching expression (first match
wins, case-insensitive), or `response_fallback` when nothing matches.

```yaml
voice_assistant:
  on_tts_start:                      # x = the response text being spoken
    - lvgl_kawaii_face.set_emotion_from_text:
        id: face
        text: !lambda return x;
```

Built-in defaults cover common FR/EN cues (errors→sad, praise→happy,
questions/uncertainty→confused, "je t'aime"→love, warnings→surprised).
Override them per emotion:

```yaml
lvgl_kawaii_face:
  id: face
  response_fallback: speaking
  response_keywords:
    sad: ["désolé", "erreur", "je n'ai pas", "sorry", "error"]
    happy: ["bravo", "super", "c'est fait", "done", "great"]
    confused: ["je ne comprends", "not sure"]
    love: ["je t'aime", "i love you"]
```

> Tip: for the most precise behaviour, prompt your LLM/agent to phrase replies
> with clear emotional cues, or have Home Assistant decide the emotion and call
> `set_emotion` directly.

## Voice assistant

Wire the actions into the standard `voice_assistant:` triggers — see
[`example.yaml`](example.yaml) for a complete, ready-to-adapt configuration:

```yaml
voice_assistant:
  on_wake_word_detected:
    - lvgl_kawaii_face.set_emotion: { id: face, emotion: excited }
  on_listening:
    - lvgl_kawaii_face.set_emotion: { id: face, emotion: listening }
  on_stt_end:
    - lvgl_kawaii_face.set_emotion: { id: face, emotion: thinking }
  on_tts_start:                                  # follow the response content
    - lvgl_kawaii_face.set_emotion_from_text: { id: face, text: !lambda 'return x;' }
  on_error:
    - lvgl_kawaii_face.set_emotion: { id: face, emotion: error }
  on_end:
    - lvgl_kawaii_face.set_emotion: { id: face, emotion: neutral }
```

## ESP32-P4 / PPA (e.g. Waveshare 7")

Fully compatible with LVGL 9.5 and the PPA-accelerated display path in this
repo — no special configuration:

- The face renders to **RGB565** canvases, matching the default
  `color_depth: 16` used on `mipi_dsi` panels.
- The PPA draw unit evaluates each task and **falls back to software** when a
  buffer isn't 16-byte aligned (or a rect is rounded / has opacity / a
  gradient), so the small face canvases never crash; cache coherency is handled
  by the unit (`esp_cache_msync`). PPA framebuffer rotation is unaffected.
- Works alongside `use_ppa: true` / `use_ppa_img: true`.

See [`example_esp32p4_waveshare.yaml`](example_esp32p4_waveshare.yaml) for a
board-specific snippet (1024×600, rotation 180, `okay_nabu`) to merge into your
existing config.

Canvas buffers (tens of KB) are allocated in internal RAM first, then PSRAM —
both PPA-accessible. Increase `face_panel` size for a larger face (PSRAM takes
over).
