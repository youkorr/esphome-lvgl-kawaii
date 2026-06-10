# ESPHome LVGL Kawaii Face 😊

![Kawaii face demo](<https://raw.githubusercontent.com/youkorr/lvgl_9.5/claude/jolly-lamport-ERZOC/dist/esphome-lvgl-kawaii/docs/kawaii_face_demo.gif>)

Un visage *kawaii* animé pour écran **LVGL 9** (ESP32 / **ESP32‑P4**) qui **réagit au Voice Assistant** de Home Assistant : il se réveille, écoute, réfléchit, parle — et change même d'humeur selon **le contenu de la réponse** du LLM.

> Intégration ESPHome du composant C [`0015/lvgl_kawaii_face`](<https://github.com/0015/lvgl_kawaii_face>) (Eric Nam). Licence MIT.

## 17 expressions
`neutral` · `happy` · `worried` · `sad` · `surprised` · `angry` · `sleepy` · `wink` · `love` · `playful` · `silly` · `smirk` · `cry` · `working_hard` · `excited` · `confused` · `cool`

## Installation
```yaml
external_components:
  - source:
      type: git
      url: <https://github.com/youkorr/esphome-lvgl-kawaii>
      ref: main
    components: [lvgl_kawaii_face]

