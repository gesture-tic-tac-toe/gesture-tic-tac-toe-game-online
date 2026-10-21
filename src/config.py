"""Central configuration, constants and (English / Khmer) labels."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict, fields
from pathlib import Path

EMPTY = ""
X = "X"
O = "O"

ROOT = Path(__file__).resolve().parent.parent
SETTINGS_FILE = ROOT / "settings.json"
FONT_DIR = ROOT / "assets" / "fonts"
MODEL_DIR = ROOT / "assets" / "models"


@dataclass
class Config:
    # --- window / camera -------------------------------------------------
    window_size: tuple = (1280, 720)
    camera_index: int = 0
    camera_size: tuple = (640, 480)      # processing resolution (smaller = faster)
    mirror: bool = True
    fps_limit: int = 30

    # --- board region in WINDOW pixels: x, y, width, height -------------
    board_rect: tuple = (110, 80, 540, 540)
    cell_deadzone: int = 10              # px near inner cell borders where nothing is selected

    # --- selection (Mode A: Point & Dwell) -------------------------------
    dwell_time: float = 1.0              # seconds to hold a cell (0.8 - 1.5 recommended)
    ui_dwell_time: float = 1.0           # seconds to hold a menu button
    dwell_grace: float = 0.30            # tolerated hand-loss / flicker (seconds)
    smoothing: float = 0.45              # EMA alpha (1 = no smoothing)

    # --- players / rules --------------------------------------------------
    player_names: list = field(default_factory=lambda: ["Player 1", "Player 2"])
    first_player: int = 0                # 0 = Player 1 (X), 1 = Player 2 (O)
    alternate_first: bool = True         # swap the starter every round
    preserve_score: bool = True          # keep match score on New Round
    use_player_zones: bool = False       # P1 = left half of camera, P2 = right half
    symbol_gestures: bool = True         # X = index + thumb pinch, O = index finger only

    # --- game mode / match ------------------------------------------------
    mode: str = "pvp"                    # "pvp" = two players, "ai" = Player 1 vs computer
    ai_level: str = "medium"             # easy / medium / hard
    match_target: int = 3                # first to N round wins takes the match (0 = endless)
    turn_timer: int = 0                  # seconds per move (0 = off); a random move is played on timeout
    countdown: bool = True               # 3-2-1 before every round
    wink_exit: bool = True               # hold a WINK (one eye closed) to quit the game

    # --- look & feel ------------------------------------------------------
    theme: str = "midnight"              # midnight / neon / ocean / sunset

    # --- misc -------------------------------------------------------------
    debug: bool = False                  # show FPS and eye-openness diagnostics
    sound: bool = True
    language: str = "en"                 # "en" or "km"

    # ---------------------------------------------------------------------
    @classmethod
    def load(cls, path: Path = SETTINGS_FILE) -> "Config":
        cfg = cls()
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cfg
        names = {f.name for f in fields(cls)}
        for key, value in data.items():
            if key in names:
                if isinstance(getattr(cfg, key), tuple) and isinstance(value, list):
                    value = tuple(value)
                setattr(cfg, key, value)
        return cfg

    def save(self, path: Path = SETTINGS_FILE) -> None:
        try:
            Path(path).write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False),
                                  encoding="utf-8")
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Labels.  Khmer needs a Khmer .ttf font inside assets/fonts (e.g. NotoSansKhmer).
# Please have a native speaker review the Khmer strings before a public demo.
# ---------------------------------------------------------------------------
LABELS = {
    "en": {
        "title": "Gesture Tic-Tac-Toe",
        "subtitle": "Point with your index finger and hold still to place your mark",
        "start": "Start Game", "instructions": "Instructions", "settings": "Settings",
        "exit": "Exit", "back": "Back",
        "new_round": "New Round", "reset_score": "Reset Score", "menu": "Main Menu",
        "turn": "Turn: {name} ({symbol})", "wins": "{name} wins!", "draw": "It's a draw!",
        "occupied": "Cell already taken!", "score": "Score", "draws": "Draws",
        "round": "Round {n}",
        "show_hand": "Show your hand to the camera to begin",
        "no_hand": "{name}: show your hand",
        "fist": "Point with your INDEX finger to select",
        "gesture_X": "INDEX + THUMB touching (OK sign)", "gesture_O": "INDEX finger only",
        "gesture_help": "X = index + thumb   |   O = index finger only",
        "wrong_gesture": "{symbol}'s turn: use {gesture}",
        "symgest": "Symbol gestures: {v}",
        "swipe_hint": "Open palm + swipe LEFT = back to menu", "back_label": "Back",
        "menu_hint": "Thumb + MIDDLE finger = click   |   Thumb + index + little finger = Start",
        "start_label": "Start Game",
        "cam_lost": "Camera signal lost...",
        "dwell": "Hold time: {v:.1f}s", "zones": "Player zones: {v}",
        "first": "Diagnostics: {v}", "debug": "Diagnostics: {v}",
        "sound": "Sound: {v}", "lang": "Language: {v}",
        "on": "ON", "off": "OFF",
        "name1": "Player 1 name: {v}", "name2": "Player 2 name: {v}",
        "inst_title": "How to play",
    },
    "km": {
        "title": "ល្បែង XO ដោយចលនាដៃ",
        "subtitle": "ចង្អុលម្រាមដៃ ហើយទប់ឱ្យនឹងដើម្បីដាក់សញ្ញា",
        "start": "ចាប់ផ្តើមល្បែង", "instructions": "ការណែនាំ", "settings": "ការកំណត់",
        "exit": "ចាកចេញ", "back": "ត្រឡប់ក្រោយ",
        "new_round": "ជុំថ្មី", "reset_score": "កំណត់ពិន្ទុឡើងវិញ", "menu": "ម៉ឺនុយ",
        "turn": "វេន: {name} ({symbol})", "wins": "{name} ឈ្នះ!", "draw": "ស្មើគ្នា!",
        "occupied": "ប្រអប់នេះមានហើយ!", "score": "ពិន្ទុ", "draws": "ស្មើ",
        "round": "ជុំទី {n}",
        "show_hand": "បង្ហាញដៃរបស់អ្នកទៅកាមេរ៉ាដើម្បីចាប់ផ្តើម",
        "no_hand": "{name}: បង្ហាញដៃ",
        "fist": "ចង្អុលដោយម្រាមដៃចង្អុល",
        "gesture_X": "ម្រាមចង្អុល + មេដៃ ប៉ះគ្នា", "gesture_O": "ម្រាមចង្អុលតែមួយ",
        "gesture_help": "X = ម្រាមចង្អុល + មេដៃ   |   O = ម្រាមចង្អុលតែមួយ",
        "wrong_gesture": "វេន {symbol}: ប្រើ {gesture}",
        "symgest": "ចលនាសញ្ញា: {v}",
        "swipe_hint": "បើកបាតដៃ + អូសទៅឆ្វេង = ត្រឡប់ទៅម៉ឺនុយ", "back_label": "ត្រឡប់ក្រោយ",
        "menu_hint": "មេដៃ + ម្រាមកណ្តាល = ចុច   |   មេដៃ + ម្រាមចង្អុល + ម្រាមដៃតូច = ចាប់ផ្តើម",
        "start_label": "ចាប់ផ្តើមល្បែង",
        "cam_lost": "បាត់សញ្ញាកាមេរ៉ា...",
        "dwell": "ពេលទប់: {v:.1f}វិ", "zones": "តំបន់អ្នកលេង: {v}",
        "first": "អ្នកលេងមុន: {v}", "debug": "បង្ហាញទិន្នន័យវិនិច្ឆ័យ: {v}",
        "sound": "សំឡេង: {v}", "lang": "ភាសា: {v}",
        "on": "បើក", "off": "បិទ",
        "name1": "ឈ្មោះអ្នកលេង ១: {v}", "name2": "ឈ្មោះអ្នកលេង ២: {v}",
        "inst_title": "របៀបលេង",
    },
}


LABELS["en"].update({
    "subtitle": "Show a hand gesture, hold still, and place your mark",
    "play_ai": "Play vs Computer", "play_pvp": "Two Players", "stats": "Statistics",
    "difficulty": "Choose difficulty", "easy": "Easy", "medium": "Medium", "hard": "Hard (unbeatable)",
    "computer": "Computer", "thinking": "Computer is thinking...",
    "paused": "Paused", "resume": "Resume", "restart": "Restart Round",
    "rematch": "Rematch", "match_winner": "{name} wins the match!",
    "match_info": "First to {n} wins", "endless": "Endless match",
    "target": "Match: {v}", "target_first": "First to {n}",
    "timer": "Turn timer: {v}", "timer_off": "OFF", "timer_s": "{n}s",
    "theme": "Theme: {v}", "countdown": "Countdown: {v}",
    "timeup": "Time's up! Random move played", "hint": "Hint", "no_hint": "No hint right now",
    "wink": "Wink to exit: {v}", "wink_label": "Exit game", "wink_photo": "WINK = EXIT",
    "face_fail": "Face tracking unavailable - wink exit is off",
    "go": "GO!", "saved": "Screenshot saved", "starting": "Starting camera and hand tracking...",
    "stats_title": "Statistics", "reset_stats": "Reset Statistics",
    "st_rounds": "Rounds played", "st_streak": "Current win streak", "st_best": "Best win streak",
    "st_matches": "Matches won / lost (vs computer)", "st_ai": "Vs Computer  (W / L / D)",
    "st_pvp": "Two players", "st_pvp_row": "{p1} {a}   |   {p2} {b}   |   Draws {d}",
    "pause_hint": "P / ESC = pause   |   H = hint   |   S = screenshot",
    "menu_hint": "Thumb + MIDDLE finger = click   |   Rock sign (thumb + index + little) = quick start",
    "swipe_hint": "Open palm + swipe LEFT = pause / back",
    "inst": [
        "1. Stand about 0.5 - 1 m from the webcam with good light on your hand.",
        "2. X = INDEX finger + THUMB touching (OK sign).  O = INDEX finger only.",
        "3. Move your hand over an empty cell - a preview of your mark appears.",
        "4. Hold steady until the ring fills. Other gestures are ignored.",
        "5. Two Players: Player 1 = X, Player 2 = O.  vs Computer: you are X.",
        "6. Three in a row (line, column or diagonal) wins the round.",
        "7. First to reach the match target (Settings) wins the match.",
        "8. Optional turn timer: when it runs out a random move is played.",
        "9. Open PALM + swipe LEFT = pause (in game) / back (menus).",
        "10. In menus: THUMB + MIDDLE finger together = click the button you point at.",
        "11. Main menu: ROCK sign (thumb + index + little finger) = quick start.",
        "12. WINK (close ONE eye, like the photo) and hold about 1 second = exit the game.",
        "Keys: P/ESC pause | R restart | H hint | S screenshot | D diagnostics | M mute",
    ],
})

LABELS["km"].update({
    "play_ai": "លេងជាមួយកុំព្យូទ័រ", "play_pvp": "អ្នកលេងពីរនាក់", "stats": "ស្ថិតិ",
    "difficulty": "ជ្រើសរើសកម្រិត", "easy": "ងាយ", "medium": "មធ្យម", "hard": "ពិបាក (មិនអាចឈ្នះ)",
    "computer": "កុំព្យូទ័រ", "thinking": "កុំព្យូទ័រកំពុងគិត...",
    "paused": "ផ្អាក", "resume": "បន្ត", "restart": "ចាប់ផ្តើមជុំឡើងវិញ",
    "rematch": "លេងម្តងទៀត", "match_winner": "{name} ឈ្នះការប្រកួត!",
    "match_info": "ដល់ {n} ជុំ ឈ្នះ", "endless": "ការប្រកួតគ្មានទីបញ្ចប់",
    "target": "ការប្រកួត: {v}", "target_first": "ដល់ {n} ជុំ",
    "timer": "ម៉ោងវេន: {v}", "timer_off": "បិទ", "timer_s": "{n}វិ",
    "theme": "រចនាប័ទ្ម: {v}", "countdown": "រាប់ថយក្រោយ: {v}",
    "timeup": "អស់ម៉ោង! ដាក់ដោយចៃដន្យ", "hint": "ជំនួយ", "no_hint": "គ្មានជំនួយ",
    "wink": "ព្រិចភ្នែកដើម្បីចាកចេញ: {v}", "wink_label": "ចាកចេញ", "wink_photo": "ព្រិចភ្នែក = ចាកចេញ",
    "face_fail": "មិនអាចតាមដានមុខបាន - បិទការព្រិចភ្នែក",
    "go": "ចាប់ផ្តើម!", "saved": "បានរក្សាទុករូបថតអេក្រង់",
    "stats_title": "ស្ថិតិ", "reset_stats": "កំណត់ស្ថិតិឡើងវិញ",
    "st_rounds": "ចំនួនជុំដែលបានលេង", "st_streak": "ឈ្នះជាប់គ្នា", "st_best": "ឈ្នះជាប់គ្នាខ្ពស់បំផុត",
    "st_matches": "ការប្រកួតឈ្នះ / ចាញ់ (ជាមួយកុំព្យូទ័រ)", "st_ai": "ជាមួយកុំព្យូទ័រ (ឈ / ចា / ស្មើ)",
    "st_pvp": "អ្នកលេងពីរនាក់", "st_pvp_row": "{p1} {a}   |   {p2} {b}   |   ស្មើ {d}",
    "pause_hint": "P / ESC = ផ្អាក   |   H = ជំនួយ   |   S = រូបថតអេក្រង់",
    "swipe_hint": "បើកបាតដៃ + អូសទៅឆ្វេង = ផ្អាក / ត្រឡប់ក្រោយ",
    "inst": [
        "1. ឈរចម្ងាយប្រហែល 0.5 - 1 ម៉ែត្រពីកាមេរ៉ា ហើយមានពន្លឺល្អ។",
        "2. X = ម្រាមចង្អុល + មេដៃប៉ះគ្នា។  O = ម្រាមចង្អុលតែមួយ។",
        "3. ដាក់ដៃលើប្រអប់ទំនេរ - សញ្ញាគំរូនឹងបង្ហាញ។",
        "4. ទប់ឱ្យនឹងរហូតរង្វង់ពេញ។ ចលនាផ្សេងមិនរាប់។",
        "5. ពីរនាក់: អ្នកលេង ១ = X, អ្នកលេង ២ = O។  ជាមួយកុំព្យូទ័រ: អ្នកគឺ X។",
        "6. បានបីជាប់គ្នា (ជួរ ឈរ ឬទ្រនាប់) ឈ្នះជុំនោះ។",
        "7. អ្នកដល់ចំនួនជុំគោលដៅមុន ឈ្នះការប្រកួត។",
        "8. ម៉ោងវេន (ជម្រើស): ពេលអស់ម៉ោង ប្រព័ន្ធដាក់ដោយចៃដន្យ។",
        "9. បាតដៃ + អូសទៅឆ្វេង: ផ្អាកពេលលេង ឬត្រឡប់ទៅម៉ឺនុយ។",
        "10. ក្នុងម៉ឺនុយ: ប៉ះមេដៃ + ម្រាមកណ្តាល ដើម្បីចុចប៊ូតុង។",
        "11. ម៉ឺនុយដើម: មេដៃ + ម្រាមចង្អុល + ម្រាមដៃតូច = ចាប់ផ្តើមលឿន។",
        "12. ព្រិចភ្នែកម្ខាង (បិទភ្នែកតែមួយ ដូចក្នុងរូបថត) ហើយទប់ប្រហែល ១ វិនាទី = ចាកចេញពីល្បែង។",
        "Keys: P/ESC | R | H | S | D | M",
    ],
})


def tr(lang: str, key: str, **kw):
    table = LABELS.get(lang, LABELS["en"])
    text = table.get(key, LABELS["en"].get(key, key))
    if isinstance(text, str) and kw:
        return text.format(**kw)
    return text
