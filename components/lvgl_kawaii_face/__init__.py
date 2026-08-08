"""
LVGL Kawaii Face for ESPHome.

Wraps the lvgl_kawaii_face C component (animated kawaii face for LVGL 9) and
exposes its emotion as an ESPHome action, so the face can react to anything —
most notably the `voice_assistant:` pipeline (listening / thinking / speaking /
error). See example.yaml for a full voice-assistant wiring.
"""

import esphome.automation as automation
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components.lvgl.types import lv_obj_t
from esphome.const import CONF_ID

CODEOWNERS = ["@youkorr"]
DEPENDENCIES = ["lvgl"]

CONF_PARENT_ID = "parent_id"
CONF_BG_COLOR = "bg_color"
CONF_ANIMATION_SPEED = "animation_speed"
CONF_BLINK_INTERVAL = "blink_interval"
CONF_AUTO_BLINK = "auto_blink"
CONF_SMOOTH = "smooth"
CONF_INITIAL_EMOTION = "initial_emotion"
CONF_EMOTION = "emotion"
CONF_TEXT = "text"
CONF_RESPONSE_KEYWORDS = "response_keywords"
CONF_RESPONSE_FALLBACK = "response_fallback"

# Expression names recognised by the C component, plus voice-assistant aliases
# handled by the C++ wrapper (kawaii_face.h). Used to validate static values.
EMOTIONS = [
    "neutral",
    "happy",
    "worried",
    "sad",
    "surprised",
    "angry",
    "sleepy",
    "wink",
    "love",
    "playful",
    "silly",
    "smirk",
    "cry",
    "working_hard",
    "excited",
    "confused",
    "cool",
    "blink",
    # Voice-assistant friendly aliases:
    "idle",
    "listening",
    "thinking",
    "speaking",
    "talking",
    "error",
]

kawaii_ns = cg.esphome_ns.namespace("lvgl_kawaii_face")
KawaiiFaceComponent = kawaii_ns.class_("KawaiiFaceComponent", cg.Component)
KawaiiFaceSetEmotionAction = kawaii_ns.class_(
    "KawaiiFaceSetEmotionAction", automation.Action
)
KawaiiFaceSetEmotionFromTextAction = kawaii_ns.class_(
    "KawaiiFaceSetEmotionFromTextAction", automation.Action
)
KawaiiFaceSetTalkingAction = kawaii_ns.class_(
    "KawaiiFaceSetTalkingAction", automation.Action
)
KawaiiFaceLookAtAction = kawaii_ns.class_("KawaiiFaceLookAtAction", automation.Action)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(KawaiiFaceComponent),
        # id of the LVGL widget or page hosting the face. Validated against the
        # ids the lvgl component declares, so a typo is a config error instead
        # of a face that silently lands on the active screen. Omit to fill the
        # active screen.
        cv.Optional(CONF_PARENT_ID): cv.use_id(lv_obj_t),
        # Colour the face canvases are cleared with. Defaults to the background
        # of the first opaque ancestor (panel, else page), so the face blends in.
        cv.Optional(CONF_BG_COLOR): cv.hex_int_range(min=0, max=0xFFFFFF),
        cv.Optional(
            CONF_ANIMATION_SPEED, default="30ms"
        ): cv.positive_time_period_milliseconds,
        cv.Optional(
            CONF_BLINK_INTERVAL, default="3000ms"
        ): cv.positive_time_period_milliseconds,
        cv.Optional(CONF_AUTO_BLINK, default=True): cv.boolean,
        cv.Optional(CONF_SMOOTH, default=True): cv.boolean,
        cv.Optional(CONF_INITIAL_EMOTION, default="neutral"): cv.one_of(
            *EMOTIONS, lower=True
        ),
        # Map an emotion to the keywords that select it when found in a response
        # (case-insensitive substring). Omit to use built-in FR/EN defaults.
        cv.Optional(CONF_RESPONSE_KEYWORDS): cv.Schema(
            {cv.one_of(*EMOTIONS, lower=True): cv.ensure_list(cv.string_strict)}
        ),
        # Emotion used when a response matches none of the keywords.
        cv.Optional(CONF_RESPONSE_FALLBACK, default="speaking"): cv.one_of(
            *EMOTIONS, lower=True
        ),
    }
).extend(cv.COMPONENT_SCHEMA)

SET_EMOTION_SCHEMA = cv.Schema(
    {
        cv.Required(CONF_ID): cv.use_id(KawaiiFaceComponent),
        cv.Required(CONF_EMOTION): cv.templatable(cv.string),
    }
)

SET_EMOTION_FROM_TEXT_SCHEMA = cv.Schema(
    {
        cv.Required(CONF_ID): cv.use_id(KawaiiFaceComponent),
        cv.Required(CONF_TEXT): cv.templatable(cv.string),
    }
)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)

    if parent_id := config.get(CONF_PARENT_ID):
        # An lvgl widget/page id is a *global* that the lvgl component only
        # assigns while the generated setup() runs. Reading it here — as this
        # component used to, via a bare RawExpression — captured a null pointer
        # whenever our statement was emitted first, and a null parent makes the
        # C component fall back to lv_screen_active(): the face always appeared
        # on the page being displayed at boot, never on the configured one.
        #
        # Wait for the id to be declared, then pass a lambda that reads the
        # global at init time instead. kawaii_parent_obj() overloads over
        # lv_obj_t* / LvCompound* / LvPageType*, so a widget id and a page id
        # both work.
        #
        # The name must be fully qualified: the lambda is emitted into the
        # generated setup() at global scope, and argument-dependent lookup
        # cannot find it there — the arguments live in the global namespace
        # (lv_obj_t) or in esphome::lvgl (LvPageType), never in ours.
        await cg.get_variable(parent_id)
        getter = (
            f"[]() -> lv_obj_t * {{ return {kawaii_ns}::kawaii_parent_obj({parent_id}); }}"
        )
        cg.add(var.set_parent_getter(cg.RawExpression(getter)))

    if (bg_color := config.get(CONF_BG_COLOR)) is not None:
        cg.add(var.set_bg_color(bg_color))

    cg.add(var.set_animation_speed(config[CONF_ANIMATION_SPEED].total_milliseconds))
    cg.add(var.set_blink_interval(config[CONF_BLINK_INTERVAL].total_milliseconds))
    cg.add(var.set_auto_blink(config[CONF_AUTO_BLINK]))
    cg.add(var.set_smooth(config[CONF_SMOOTH]))
    cg.add(var.set_initial_emotion(config[CONF_INITIAL_EMOTION]))

    # Response keyword rules (preserve YAML declaration order). When omitted the
    # C++ side installs built-in FR/EN defaults.
    for emotion, keywords in config.get(CONF_RESPONSE_KEYWORDS, {}).items():
        for keyword in keywords:
            cg.add(var.add_response_keyword(emotion, keyword))
    cg.add(var.set_response_fallback(config[CONF_RESPONSE_FALLBACK]))


@automation.register_action(
    "lvgl_kawaii_face.set_emotion",
    KawaiiFaceSetEmotionAction,
    SET_EMOTION_SCHEMA,
    synchronous=True,
)
async def kawaii_set_emotion_to_code(config, action_id, template_arg, args):
    parent = await cg.get_variable(config[CONF_ID])
    var = cg.new_Pvariable(action_id, template_arg, parent)
    templ = await cg.templatable(config[CONF_EMOTION], args, cg.std_string)
    cg.add(var.set_emotion(templ))
    return var


@automation.register_action(
    "lvgl_kawaii_face.set_emotion_from_text",
    KawaiiFaceSetEmotionFromTextAction,
    SET_EMOTION_FROM_TEXT_SCHEMA,
    synchronous=True,
)
async def kawaii_set_emotion_from_text_to_code(config, action_id, template_arg, args):
    parent = await cg.get_variable(config[CONF_ID])
    var = cg.new_Pvariable(action_id, template_arg, parent)
    templ = await cg.templatable(config[CONF_TEXT], args, cg.std_string)
    cg.add(var.set_text(templ))
    return var


CONF_TALKING = "talking"
CONF_X = "x"
CONF_Y = "y"
CONF_HOLD = "hold"

SET_TALKING_SCHEMA = cv.maybe_simple_value(
    {
        cv.GenerateID(CONF_ID): cv.use_id(KawaiiFaceComponent),
        cv.Required(CONF_TALKING): cv.templatable(cv.boolean),
    },
    key=CONF_TALKING,
)

# x/y are -100..100, (0, 0) straight ahead. Templatable, so the values can come
# from a face detector, a touchscreen, or anything else.
LOOK_AT_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_ID): cv.use_id(KawaiiFaceComponent),
        cv.Required(CONF_X): cv.templatable(cv.int_range(min=-100, max=100)),
        cv.Required(CONF_Y): cv.templatable(cv.int_range(min=-100, max=100)),
        cv.Optional(CONF_HOLD, default="2s"): cv.positive_time_period_milliseconds,
    }
)


@automation.register_action(
    "lvgl_kawaii_face.set_talking",
    KawaiiFaceSetTalkingAction,
    SET_TALKING_SCHEMA,
    synchronous=True,
)
async def kawaii_set_talking_to_code(config, action_id, template_arg, args):
    parent = await cg.get_variable(config[CONF_ID])
    var = cg.new_Pvariable(action_id, template_arg, parent)
    templ = await cg.templatable(config[CONF_TALKING], args, cg.bool_)
    cg.add(var.set_talking(templ))
    return var


@automation.register_action(
    "lvgl_kawaii_face.look_at",
    KawaiiFaceLookAtAction,
    LOOK_AT_SCHEMA,
    synchronous=True,
)
async def kawaii_look_at_to_code(config, action_id, template_arg, args):
    parent = await cg.get_variable(config[CONF_ID])
    var = cg.new_Pvariable(action_id, template_arg, parent)
    for key in (CONF_X, CONF_Y):
        templ = await cg.templatable(config[key], args, cg.int_)
        cg.add(getattr(var, f"set_{key}")(templ))
    cg.add(var.set_hold(config[CONF_HOLD].total_milliseconds))
    return var
