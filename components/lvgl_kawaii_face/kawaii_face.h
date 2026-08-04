#pragma once

#include "esphome/core/component.h"
#include "esphome/core/automation.h"
#include "esphome/core/log.h"

#include <cctype>
#include <functional>
#include <string>
#include <utility>
#include <vector>

#ifdef USE_LVGL
// LvCompound / LvPageType, so a page id can be used as the face's parent.
#include "esphome/components/lvgl/lvgl_esphome.h"
// Pulls in <lvgl.h> (for lv_obj_t / lv_lock / lv_unlock) and the kawaii face
// C API. The header carries extern "C" guards so the symbols compiled from
// lvgl_kawaii_face.c link cleanly into this C++ translation unit.
#include "lvgl_kawaii_face.h"
#endif

namespace esphome {
namespace lvgl_kawaii_face {

static const char *const TAG = "kawaii_face";

#ifdef USE_LVGL
// The generated code resolves `parent_id` to whatever variable the lvgl
// component declared for that id. A plain widget is an `lv_obj_t *`, while a
// page — or any compound widget — is a wrapper object owning one. These
// overloads let the generated lambda hand us either kind without the Python
// side having to know which it got.
inline lv_obj_t *kawaii_parent_obj(lv_obj_t *obj) { return obj; }
inline lv_obj_t *kawaii_parent_obj(lvgl::LvCompound *compound) {
  return compound == nullptr ? nullptr : compound->obj;
}
inline lv_obj_t *kawaii_parent_obj(lvgl::LvPageType *page) { return page == nullptr ? nullptr : page->obj; }
#endif

/**
 * ESPHome wrapper around the lvgl_kawaii_face C component.
 *
 * The underlying C component is a singleton (one animated face per device),
 * so a single KawaiiFaceComponent instance should be configured. It creates
 * the face inside an LVGL parent object — either a widget you declare in the
 * `lvgl:` config (referenced by id) or the active screen when none is given —
 * and exposes the emotion as an ESPHome action so it can react to anything,
 * most notably the `voice_assistant:` pipeline triggers.
 */
class KawaiiFaceComponent : public Component {
 public:
#ifdef USE_LVGL
  // The parent is passed as a *getter*, not a pointer: LVGL widget and page
  // variables are globals the lvgl component only assigns while the generated
  // setup() runs, so reading one at configuration time would capture a null
  // pointer — which silently fell back to lv_screen_active() and put the face
  // on whichever page happened to be showing (always the first one).
  void set_parent_getter(std::function<lv_obj_t *()> getter) { this->parent_getter_ = std::move(getter); }
  void set_bg_color(uint32_t rgb) {
    this->bg_color_ = lv_color_hex(rgb);
    this->bg_color_set_ = true;
  }
#endif
  void set_animation_speed(uint32_t ms) { this->animation_speed_ = ms; }
  void set_blink_interval(uint32_t ms) { this->blink_interval_ = ms; }
  void set_auto_blink(bool enable) { this->auto_blink_ = enable; }
  void set_smooth(bool smooth) { this->smooth_ = smooth; }
  void set_initial_emotion(const std::string &emotion) { this->initial_emotion_ = emotion; }

  // Append a keyword that, when found (case-insensitive) in a response, selects
  // the given emotion. Rules are evaluated in the order emotions are first
  // declared; the first matching keyword wins. Configured from YAML; if none
  // are configured, sensible FR/EN defaults are installed in setup().
  void add_response_keyword(const std::string &emotion, const std::string &keyword) {
    std::string kw = to_lower_(keyword);
    for (auto &rule : this->response_rules_) {
      if (rule.emotion == emotion) {
        rule.keywords.push_back(kw);
        return;
      }
    }
    this->response_rules_.push_back(ResponseRule{emotion, {kw}});
  }
  // Emotion used when a response matches no keyword.
  void set_response_fallback(const std::string &emotion) { this->response_fallback_ = emotion; }

  // Run after the lvgl component (PROCESSOR priority) has created its
  // display, screens and widgets.
  float get_setup_priority() const override { return setup_priority::LATE; }

  void setup() override {
    if (this->response_rules_.empty())
      this->install_default_response_rules_();
#ifdef USE_LVGL
    // Route the C component's thread-safety hooks through LVGL's own guard.
    // ESPHome drives lv_timer_handler() on the main loop, so these are
    // uncontended here, but wiring them keeps the face correct if an emotion is
    // ever set from another task. Captureless lambdas adapt lv_lock/lv_unlock
    // to the expected void(void) signature regardless of their return type.
    face_set_lvgl_lock_fns([]() { lv_lock(); }, []() { lv_unlock(); });
#endif
  }

  // Deferred init: by the first loop() the LVGL stack is fully up, every
  // widget and page global has been assigned, and the parent can be laid out.
  void loop() override {
#ifdef USE_LVGL
    if (this->initialized_)
      return;

    // Retries are throttled and bounded: the parent may need a few frames to
    // get a size, but a parent that never gets one must not spin the loop and
    // flood the log forever.
    const uint32_t now = millis();
    if (this->attempts_ != 0 && now - this->last_attempt_ < INIT_RETRY_INTERVAL_MS)
      return;
    this->last_attempt_ = now;
    this->attempts_++;

    lv_obj_t *parent = this->parent_getter_ ? this->parent_getter_() : nullptr;
    if (this->parent_getter_ && parent == nullptr) {
      // Falling back to the active screen here is exactly the bug this getter
      // exists to prevent, so treat it as an error instead.
      ESP_LOGE(TAG, "Configured parent_id is not a valid LVGL object yet");
      this->fail_or_retry_();
      return;
    }

    face_config_t cfg{};
    cfg.parent = parent;  // nullptr -> fills the active screen
    cfg.animation_speed = this->animation_speed_;
    cfg.blink_interval = this->blink_interval_;
    cfg.auto_blink = this->auto_blink_;
    cfg.bg_color_set = this->bg_color_set_;
    if (this->bg_color_set_)
      cfg.bg_color = this->bg_color_;

    esp_err_t err = face_animation_init(&cfg);
    if (err != ESP_OK) {
      // Either the parent has no size yet or the canvas buffers would not fit.
      ESP_LOGW(TAG, "face_animation_init failed (err %d), attempt %u", (int) err, (unsigned) this->attempts_);
      this->fail_or_retry_();
      return;
    }

    this->initialized_ = true;
    // Everything from here on is driven by the LVGL timer, so this component
    // has nothing left to do on the main loop.
    this->disable_loop();
    ESP_LOGCONFIG(TAG, "Kawaii face initialised (speed %ums, blink %ums, auto_blink %s)",
                  (unsigned) this->animation_speed_, (unsigned) this->blink_interval_,
                  this->auto_blink_ ? "YES" : "NO");

    if (this->has_pending_)
      this->apply_emotion_(this->pending_emotion_);
    else if (!this->initial_emotion_.empty())
      this->apply_emotion_(this->initial_emotion_);
#endif
  }

  void dump_config() override {
    ESP_LOGCONFIG(TAG, "Kawaii Face:");
#ifdef USE_LVGL
    ESP_LOGCONFIG(TAG, "  parent: %s", this->parent_getter_ ? "configured widget/page" : "active screen");
#endif
    ESP_LOGCONFIG(TAG, "  animation_speed: %u ms", (unsigned) this->animation_speed_);
    ESP_LOGCONFIG(TAG, "  blink_interval: %u ms", (unsigned) this->blink_interval_);
    ESP_LOGCONFIG(TAG, "  auto_blink: %s", this->auto_blink_ ? "YES" : "NO");
    ESP_LOGCONFIG(TAG, "  smooth transitions: %s", this->smooth_ ? "YES" : "NO");
    if (!this->initial_emotion_.empty())
      ESP_LOGCONFIG(TAG, "  initial_emotion: %s", this->initial_emotion_.c_str());
  }

  // Public API — change the displayed emotion by name. Safe to call before
  // initialisation completes; the last request is applied once ready.
  void set_emotion(const std::string &emotion) {
#ifdef USE_LVGL
    if (!this->initialized_) {
      this->pending_emotion_ = emotion;
      this->has_pending_ = true;
      return;
    }
    this->apply_emotion_(emotion);
#endif
  }

  // Pick an emotion from the content of a response (e.g. the voice-assistant
  // TTS text in on_tts_start). Matches the configured keyword rules, falling
  // back to `response_fallback_` when nothing matches. This is how the face
  // "follows" what the LLM actually says.
  void set_emotion_from_text(const std::string &text) {
    std::string r = to_lower_(text);
    for (const auto &rule : this->response_rules_) {
      for (const auto &kw : rule.keywords) {
        if (!kw.empty() && r.find(kw) != std::string::npos) {
          ESP_LOGD(TAG, "Response matched '%s' -> %s", kw.c_str(), rule.emotion.c_str());
          this->set_emotion(rule.emotion);
          return;
        }
      }
    }
    this->set_emotion(this->response_fallback_);
  }

 protected:
  // Roughly 5s of retries at 250ms — long enough for the first frames to lay
  // the parent out, short enough that a misconfiguration is reported quickly.
  static constexpr uint32_t INIT_RETRY_INTERVAL_MS = 250;
  static constexpr uint8_t MAX_INIT_ATTEMPTS = 20;

  void fail_or_retry_() {
    if (this->attempts_ < MAX_INIT_ATTEMPTS)
      return;
    ESP_LOGE(TAG,
             "Giving up after %u attempts. Check that parent_id points at a widget "
             "with a non-zero width/height, and that enough RAM is free.",
             (unsigned) MAX_INIT_ATTEMPTS);
    this->mark_failed();
  }

  static std::string to_lower_(const std::string &in) {
    std::string out = in;
    for (auto &c : out)
      c = (char) std::tolower((unsigned char) c);
    return out;
  }

  // Default FR/EN keyword rules, evaluated top to bottom. Negative/error cues
  // are checked first so "désolé, je n'ai pas trouvé…" reads as sad even though
  // it may also contain neutral words.
  void install_default_response_rules_() {
    const struct {
      const char *emotion;
      std::vector<const char *> keywords;
    } DEFAULTS[] = {
        {"sad", {"désolé", "desole", "erreur", "impossible", "aucun", "échec",
                 "je n'ai pas", "sorry", "error", "couldn't", "can't", "cannot",
                 "failed", "unable", "not found", "no result"}},
        {"love", {"je t'aime", "i love you", "❤"}},
        {"confused", {"je ne comprends", "pas compris", "pas sûr", "not sure",
                      "don't understand", "didn't understand"}},
        {"surprised", {"attention", "alerte", "warning", "wow"}},
        {"happy", {"bravo", "super", "génial", "parfait", "d'accord", "c'est fait",
                   "terminé", "voici", "great", "done", "sure", "success",
                   "turned on", "turned off", "here is", "i've", "i have"}},
    };
    for (const auto &d : DEFAULTS)
      for (const char *kw : d.keywords)
        this->add_response_keyword(d.emotion, kw);
    ESP_LOGD(TAG, "Installed default response keyword rules");
  }

#ifdef USE_LVGL
  void apply_emotion_(const std::string &emotion) {
    face_emotion_t e;
    if (!name_to_emotion_(emotion, &e)) {
      ESP_LOGW(TAG, "Unknown emotion: '%s'", emotion.c_str());
      return;
    }
    ESP_LOGD(TAG, "Emotion -> %s%s", emotion.c_str(), this->smooth_ ? " (smooth)" : "");
    face_set_emotion(e, this->smooth_);
  }

  // Maps a lowercase name to a face_emotion_t. Besides the 17 expression names
  // from the C component it accepts a few aliases that read naturally when
  // wiring the voice-assistant pipeline (idle/listening/thinking/speaking/error).
  static bool name_to_emotion_(const std::string &name, face_emotion_t *out) {
    struct Entry {
      const char *name;
      face_emotion_t emotion;
    };
    static const Entry TABLE[] = {
        {"neutral", FACE_NEUTRAL},
        {"happy", FACE_HAPPY},
        {"worried", FACE_WORRIED},
        {"sad", FACE_SAD},
        {"surprised", FACE_SURPRISED},
        {"angry", FACE_ANGRY},
        {"sleepy", FACE_SLEEPY},
        {"wink", FACE_WINK},
        {"love", FACE_LOVE},
        {"playful", FACE_PLAYFUL},
        {"silly", FACE_SILLY},
        {"smirk", FACE_SMIRK},
        {"cry", FACE_CRY},
        {"working_hard", FACE_WORKING_HARD},
        {"excited", FACE_EXCITED},
        {"confused", FACE_CONFUSED},
        {"cool", FACE_COOL},
        {"blink", FACE_BLINK},
        // Voice-assistant friendly aliases:
        {"idle", FACE_NEUTRAL},
        {"listening", FACE_SURPRISED},
        {"thinking", FACE_WORKING_HARD},
        {"speaking", FACE_HAPPY},
        {"talking", FACE_HAPPY},
        {"error", FACE_SAD},
    };
    for (const auto &entry : TABLE) {
      if (name == entry.name) {
        *out = entry.emotion;
        return true;
      }
    }
    return false;
  }

  std::function<lv_obj_t *()> parent_getter_{};
  lv_color_t bg_color_{};
  bool bg_color_set_{false};
#endif

  uint32_t last_attempt_{0};
  uint8_t attempts_{0};

  uint32_t animation_speed_{30};
  uint32_t blink_interval_{3000};
  bool auto_blink_{true};
  bool smooth_{true};
  std::string initial_emotion_{};

  std::string pending_emotion_{};
  bool has_pending_{false};
  bool initialized_{false};

  struct ResponseRule {
    std::string emotion;
    std::vector<std::string> keywords;
  };
  std::vector<ResponseRule> response_rules_{};
  std::string response_fallback_{"speaking"};
};

// --- Action: set_emotion ---
template<typename... Ts> class KawaiiFaceSetEmotionAction : public Action<Ts...> {
 public:
  KawaiiFaceSetEmotionAction(KawaiiFaceComponent *parent) : parent_(parent) {}

  TEMPLATABLE_VALUE(std::string, emotion)

  void play(const Ts &...x) override { this->parent_->set_emotion(this->emotion_.value(x...)); }

 protected:
  KawaiiFaceComponent *parent_;
};

// --- Action: set_emotion_from_text (react to the response content) ---
template<typename... Ts> class KawaiiFaceSetEmotionFromTextAction : public Action<Ts...> {
 public:
  KawaiiFaceSetEmotionFromTextAction(KawaiiFaceComponent *parent) : parent_(parent) {}

  TEMPLATABLE_VALUE(std::string, text)

  void play(const Ts &...x) override { this->parent_->set_emotion_from_text(this->text_.value(x...)); }

 protected:
  KawaiiFaceComponent *parent_;
};

}  // namespace lvgl_kawaii_face
}  // namespace esphome
