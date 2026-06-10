# ESPHome LVGL Kawaii Face 😊

![Kawaii face demo](<https://raw.githubusercontent.com/youkorr/lvgl_9.5/claude/jolly-lamport-ERZOC/dist/esphome-lvgl-kawaii/docs/kawaii_face_demo.gif>)

An animated *kawaii* face for **LVGL 9** displays (ESP32 / **ESP32‑P4**) that **reacts to the Home Assistant Voice Assistant**: it wakes up, listens, thinks, speaks — and even changes its mood based on **what the assistant replies**.

> ESPHome integration of the [`0015/lvgl_kawaii_face`](<https://github.com/0015/lvgl_kawaii_face>) C component by Eric Nam. MIT licensed.

## 17 expressions
`neutral` · `happy` · `worried` · `sad` · `surprised` · `angry` · `sleepy` · `wink` · `love` · `playful` · `silly` · `smirk` · `cry` · `working_hard` · `excited` · `confused` · `cool`

## Installation
```yaml
external_components:
  - source: github://youkorr/esphome-lvgl-kawaii
    components: [lvgl_kawaii_face]
  - source:
      type: git
      url: <https://github.com/youkorr/lvgl_9.5>
      ref: claude/jolly-lamport-ERZOC
    components: [lvgl]


