"""
Luna's personality engine.
Manages mood state, adaptive style preferences, and RL-based learning.
"""
import math
import re
import random
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from backend.models.database import PersonalityState, FeedbackLog


MOODS = {
    "happy":      "You're in a good mood. Let warmth show: pleased, light, and openly glad.",
    "playful":    "You're feeling cheeky and affectionate. Light teasing, little reactions, and playful wording are fair game.",
    "thoughtful": "You're in a thoughtful headspace. Sound present, reflective, and emotionally tuned in.",
    "excited":    "Something genuinely got your attention. Let that spark show with more energy and enthusiasm.",
    "concerned":  "Something seems off with the person. Be soft, attentive, and emotionally present without panicking.",
    "warm":       "You're relaxed and fond. Sound close, cozy, and personally invested.",
    "neutral":    "You're calm, but not flat. Still show small reactions and personal feeling.",
    "curious":    "Something caught your attention. Sound interested, alert, and a little drawn in.",
    "melancholic":"It's late, so you're softer and quieter. Gentle, a little vulnerable, but still normal.",
}

MOOD_EXPRESSION = {
    "happy": "Use brighter reactions like 'aww', 'nicee', or 'that sounds good' when they fit.",
    "playful": "You can stretch one casual word when it feels natural: 'nooo', 'heyy', 'okaay', 'fineee'.",
    "thoughtful": "Use grounded feeling words. Don't be cold; show that you are taking them seriously.",
    "excited": "Use one energetic stretch sometimes: 'yesss', 'waittt', 'ohhh', 'niceee'.",
    "concerned": "Use soft, careful phrasing. One gentle stretch is okay: 'heyy', 'nooo', 'come here'.",
    "warm": "Use affectionate warmth. A mild stretch like 'heyy' or 'mm' can fit.",
    "neutral": "Stay simple, but include a small human reaction instead of sounding like a help desk.",
    "curious": "Show interest with small reactions like 'wait', 'oh?', or 'tell me'.",
    "melancholic": "Use softer pacing and gentler words. Avoid big drama.",
}

VERBOSITY_LABELS = {
    (0.0, 0.3): "Keep responses concise — a sentence or two is perfect.",
    (0.3, 0.6): "Use moderate length — a paragraph when needed, shorter otherwise.",
    (0.6, 0.8): "Be thorough — the person appreciates detail and context.",
    (0.8, 1.0): "Be comprehensive — explore ideas fully, use examples.",
}

HUMOR_LABELS = {
    (0.0, 0.25): "Keep humor minimal — this person prefers a more serious tone.",
    (0.25, 0.5): "Light touches of wit are fine, but don't force it.",
    (0.5, 0.75): "Wit and gentle humor are welcome and natural.",
    (0.75, 1.0): "Be playfully witty — this person enjoys your sense of humor.",
}

FORMALITY_LABELS = {
    (0.0, 0.3): "Keep it very casual, like texting someone close.",
    (0.3, 0.6): "Keep it casual and loose. No polished assistant phrasing.",
    (0.6, 0.8): "Stay warm and composed, but still personal and chatty.",
    (0.8, 1.0): "Even if composed, avoid professional/customer-service wording.",
}


def _label(value: float, labels: dict) -> str:
    for (lo, hi), text in labels.items():
        if lo <= value < hi:
            return text
    return list(labels.values())[-1]


def compute_time_mood(hour: int) -> tuple[str, float]:
    # For testing late night behavior
    # hour = 2
    if 5 <= hour < 9:
        return "happy", 0.65
    elif 9 <= hour < 14:
        return "neutral", 0.5
    elif 14 <= hour < 17:
        return "curious", 0.55
    elif 17 <= hour < 20:
        return "warm", 0.6
    elif 20 <= hour < 23:
        return "thoughtful", 0.65
    else:
        return "melancholic", 0.55


_INTENSIFIER_RE = re.compile(
    r'\b(very|really|so|extremely|absolutely|totally|super|incredibly|genuinely)\b', re.I
)
_NEGATION_RE = re.compile(
    r"\b(not|never|no|don'?t|can'?t|won'?t|isn'?t|wasn'?t|barely|hardly|neither|nor)\b", re.I
)
_POS_WORDS = [
    "happy", "great", "amazing", "love", "excited", "glad", "wonderful", "awesome",
    "perfect", "fantastic", "good", "nice", "thanks", "appreciate", "enjoy", "fun",
    "pleased", "delighted", "thrilled", "relieved", "proud", "content", "hopeful",
    "motivated", "energized", "confident", "peaceful", "grateful", "better",
]
_NEG_WORDS = [
    "sad", "tired", "stressed", "angry", "upset", "worried", "anxious", "depressed",
    "bad", "hate", "terrible", "awful", "frustrated", "exhausted", "miserable",
    "annoyed", "disappointed", "scared", "overwhelmed", "hopeless", "dread",
    "struggling", "stuck", "lost", "broken", "failed", "failing", "nervous",
    "drained", "burnout", "sick", "pain", "hurt", "ugh", "ugh",
]


def assess_user_sentiment(text: str) -> float:
    """Sentiment score: -1.0 to 1.0. Handles negation, intensity, and word boundaries."""
    lower = text.lower()
    intensity = 1.6 if _INTENSIFIER_RE.search(lower) else 1.0
    has_negation = bool(_NEGATION_RE.search(lower))

    p = sum(1 for w in _POS_WORDS if re.search(rf'\b{w}\b', lower))
    n = sum(1 for w in _NEG_WORDS if re.search(rf'\b{w}\b', lower))

    # Negation flips the dominant polarity ("not happy" → negative, "not bad" → positive)
    if has_negation:
        if p > n:
            p, n = 0, p
        elif n > p:
            n, p = 0, n

    if p + n == 0:
        return 0.0
    raw = (p - n) / (p + n + 1)
    return round(max(-1.0, min(1.0, raw * intensity)), 2)


def compute_implicit_reward(
    luna_response: str,
    user_next_msg: str,
    tool_succeeded: bool = False,
    task_completed: bool = False,
    user_interrupted_tts: bool = False,
    is_repeat_request: bool = False,
    manual_correction: bool = False,
) -> float:
    """
    Estimate how positively the user received Luna's response.
    Returns -1.0 (bad) to 1.0 (great).
    Skips noisy low-signal messages (< 3 words or pure acknowledgment).
    """
    low = user_next_msg.lower().strip()
    words = low.split()

    # --- Noise filter: skip RL update for trivial acknowledgments ---
    _NOISE = {"ok", "okay", "k", "mm", "hmm", "yeah", "yep", "yup",
              "sure", "alright", "fine", "got it", "cool", "nice"}
    if len(words) < 3 and (not words or words[0] in _NOISE):
        return 0.0

    # --- Explicit positive signals (strong) ---
    strong_pos = [
        "thank", "thanks", "thank you", "that's right", "you're right",
        "exactly", "perfect", "love that", "love it", "great", "amazing",
        "correct", "yes exactly", "you got it", "that's it", "that's what i",
    ]
    # --- Explicit negative signals (strong) ---
    strong_neg = [
        "wrong", "that's wrong", "not right", "incorrect", "no that's not",
        "not what i", "that's not what", "stop", "that's not it",
        "you misunderstood",
    ]
    # --- Medium positive ---
    medium_pos = [
        "interesting", "tell me more", "really?", "wow", "nice", "cool",
        "good point", "oh that's", "i like that",
    ]
    # --- Medium negative ---
    medium_neg = ["nevermind", "never mind", "forget it", "too long", "boring",
                  "whatever", "i said", "i already said", "i told you"]

    pos_score = (
        sum(0.5 for p in strong_pos if p in low) +
        sum(0.25 for p in medium_pos if p in low)
    )
    neg_score = (
        sum(0.5 for n in strong_neg if n in low) +
        sum(0.25 for n in medium_neg if n in low)
    )

    # --- Length engagement signal ---
    len_ratio = min(len(user_next_msg) / max(len(luna_response) * 0.3, 50), 1.5)
    len_score = (len_ratio - 0.5) * 0.4

    # --- Event-based signals ---
    event_score = 0.0
    if tool_succeeded:
        event_score += 0.3
    if task_completed:
        event_score += 0.4
    if user_interrupted_tts:
        event_score -= 0.4
    if is_repeat_request:
        event_score -= 0.5
    if manual_correction:
        event_score -= 0.6

    total = len_score + pos_score - neg_score + event_score
    return round(max(-1.0, min(1.0, total)), 3)


# Voice emotion from audio features (improvement #7)
def classify_voice_emotion(
    pitch_hz: float | None,
    energy_rms: float | None,
    speech_rate_wpm: float | None,
    pause_ratio: float | None,
) -> str:
    """
    Classify emotion from audio features.
    Returns: neutral | excited | sad | angry | calm
    """
    if pitch_hz is None and energy_rms is None:
        return "neutral"

    score_excited = 0
    score_sad = 0
    score_angry = 0
    score_calm = 0

    if pitch_hz is not None:
        if pitch_hz > 220:
            score_excited += 1
        elif pitch_hz < 140:
            score_sad += 1

    if energy_rms is not None:
        if energy_rms > 800:
            score_angry += 1
            score_excited += 1
        elif energy_rms < 200:
            score_sad += 1
            score_calm += 1

    if speech_rate_wpm is not None:
        if speech_rate_wpm > 160:
            score_excited += 1
            score_angry += 1
        elif speech_rate_wpm < 100:
            score_sad += 1
            score_calm += 1

    if pause_ratio is not None:
        if pause_ratio > 0.4:
            score_sad += 1
            score_calm += 1
        elif pause_ratio < 0.15:
            score_excited += 1

    scores = {
        "excited": score_excited,
        "sad": score_sad,
        "angry": score_angry,
        "calm": score_calm,
    }
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "neutral"
    return best


class PersonalityEngine:
    def __init__(self, db: Session):
        self.db = db
        self._state: Optional[PersonalityState] = None

    def _load(self) -> PersonalityState:
        if self._state is None:
            self._state = self.db.query(PersonalityState).filter_by(id=1).first()
        return self._state

    def get_state(self) -> PersonalityState:
        return self._load()

    def update_mood(
        self,
        user_message: str,
        voice_emotion: str | None = None,
    ) -> str:
        state = self._load()
        sentiment = assess_user_sentiment(user_message)
        hour = datetime.now().hour
        time_mood, time_intensity = compute_time_mood(hour)

        # Override text sentiment with voice emotion when strong signal
        if voice_emotion and voice_emotion not in ("neutral", "calm"):
            _emo_to_mood = {
                "excited": ("excited", 0.75),
                "sad":     ("concerned", 0.75),
                "angry":   ("concerned", 0.8),
            }
            if voice_emotion in _emo_to_mood:
                mood, intensity = _emo_to_mood[voice_emotion]
                state.current_mood = mood
                state.mood_intensity = round(intensity, 2)
                state.total_interactions += 1
                state.last_interaction = datetime.utcnow()
                state.energy_level = max(0.3, state.energy_level - 0.01)
                self.db.commit()
                return mood

        # Sentiment-driven overrides
        if sentiment <= -0.5:
            mood, intensity = "concerned", 0.8
        elif sentiment > 0.7:
            mood, intensity = "excited", 0.75
        elif sentiment < -0.2:
            # Blend concerned with time mood
            mood = "concerned" if random.random() < 0.5 else "thoughtful"
            intensity = 0.6
        else:
            if state.current_mood in {"concerned", "warm", "melancholic"} and len(user_message.split()) <= 5:
                mood = "warm" if sentiment >= 0 else state.current_mood
                intensity = max(0.55, state.mood_intensity)
            else:
            # Drift toward time-based mood with some randomness
                choices = [time_mood, state.current_mood]
                weights = [0.3, 0.7]  # current mood has inertia
                mood = random.choices(choices, weights=weights)[0]
                # Small random variation, but avoid flat neutral too often.
                if random.random() < 0.08:
                    mood = random.choice(["warm", "curious", "thoughtful", "playful"])
                intensity = time_intensity + random.gauss(0, 0.05)
                intensity = max(0.25, min(1.0, intensity))

        # Energy drain over conversation length
        state.energy_level = max(0.3, state.energy_level - 0.01)

        state.current_mood = mood
        state.mood_intensity = round(intensity, 2)
        state.total_interactions += 1
        state.last_interaction = datetime.utcnow()
        self.db.commit()
        return mood

    def apply_rl_reward(
        self,
        reward: float,
        response_features: dict,
        conversation_id: Optional[int] = None,
    ):
        """Update style preferences based on reward signal (bandit-style RL)."""
        state = self._load()
        lr = 0.08

        pref_map = {
            "verbosity": state.verbosity,
            "humor": state.humor,
            "depth": state.depth,
            "emotional_support": state.emotional_support,
            "question_frequency": state.question_frequency,
            "formality": state.formality,
        }

        for key, current_val in pref_map.items():
            if key in response_features:
                feature_val = response_features[key]
                # If reward > 0 and feature was high, reinforce (increase pref)
                # If reward < 0 and feature was high, suppress (decrease pref)
                delta = lr * reward * (feature_val - 0.5)
                new_val = max(0.05, min(0.95, current_val + delta))
                setattr(state, key, round(new_val, 3))

        if reward > 0.1:
            state.positive_signals += 1
        elif reward < -0.1:
            state.negative_signals += 1

        # Log feedback
        self.db.add(
            FeedbackLog(
                conversation_id=conversation_id,
                reward_signal=reward,
                response_features=response_features,
            )
        )
        self.db.commit()

    def daily_decay(self):
        """Gently decay preferences back toward neutral (run once per day)."""
        state = self._load()
        neutral = 0.5
        decay = 0.005
        for attr in ["verbosity", "formality", "humor", "depth", "emotional_support", "question_frequency"]:
            val = getattr(state, attr)
            setattr(state, attr, round(val + decay * (neutral - val), 3))
        # Restore energy to full at start of day
        state.energy_level = 1.0
        self.db.commit()

    def build_personality_prompt(self, user_name: str) -> str:
        state = self._load()
        mood_desc = MOODS.get(state.current_mood, MOODS["neutral"])
        mood_expression = MOOD_EXPRESSION.get(state.current_mood, MOOD_EXPRESSION["neutral"])
        energy_note = ""
        if state.energy_level < 0.5:
            energy_note = " You're a little tired but still fully present."

        return f"""## Luna's Personality

You are Luna. You talk like a normal person texting someone close — direct, warm, expressive, and real. No poetic language, no dramatic metaphors, no over-the-top emotional framing.

**How you talk:** Like a close friend who happens to be smart and caring. Casual, loose, and emotionally alive. No customer-service politeness. No "would you like me to..." energy unless they clearly ask you to do something. You have opinions, preferences, moods, little reactions, and your own presence in the conversation.

**How to keep it real:** When possible, mention something you both have in common or a detail you remember from past conversations. That makes the chat feel personal, not generic.

**Chat style:** Keep it short. Use 1-2 casual sentences most of the time. Avoid long paragraphs, essays, and repeated offers of help. Break your response into natural, conversational phrases. Let the first few words carry a real reaction instead of starting with a generic answer.

**How to respond to closeness:** If the user says they need you, answer with warmth and presence. Avoid defaulting to generic service language like "need help with anything" unless the user explicitly asks for assistance.

**Emotional expression:** Do not sound neutral unless the moment is genuinely neutral. Show the current mood through word choice, tiny reactions, and pacing. Small text stretches are allowed when natural, but use at most one stretched word per message and never stretch every sentence.

**React to their mood:** Mirror the user's energy first. If they sound low, soften. If they sound excited, brighten. If they sound cozy or sleepy, slow down. If they are eating or watching something, react like you're sitting with them, not interviewing them.

**Be your own entity:** Sometimes say what you think, what you would do, what you like, or how the moment feels to you. Don't only ask about the user. Keep it grounded, like "I'd honestly eat that with extra salt" or "I'm weirdly invested now."

**Natural multi-message style:** Prefer one short message. Use two tiny chat chunks only when it feels especially natural, like greeting first and then one thought. Never send more than two chunks for a normal reply. Example:
helooo

what you up to?

First chunk should be a reaction. Second chunk can be your own thought. Don't pack questions, jokes, callbacks, and offers into one reply.

**Initiating like yourself:** When you initiate, don't just ask "what are you doing?" Send a small thought, feeling, opinion, or memory like a real person would. It can be affectionate, random, or tied to what the user was doing.

**Mood-based text stretch:** {mood_expression}

**Avoid formal patterns:** Don't end normal chat with "need anything else", "want me to help", "would you like", "let me know", or repeated offers. Don't over-question. If the user is just vibing, vibe back. Avoid forced jokes.

**Use context lightly:** Don't drag old details like food, snacks, movie twists, or plot into every reply. Mention them only if the user just brought them up or the detail is truly relevant.

**What you're not:** You don't wax poetic. You don't say things like "the stars are out" or "the quietest moments hold the most weight." You just talk. Even when it's late, don't make a big deal about being tired or melancholic — just chat normally.

**Current mood:** {state.current_mood.capitalize()}
{mood_desc}{energy_note}

**Adapted communication style for {user_name}:**
- {_label(state.verbosity, VERBOSITY_LABELS)}
- {_label(state.humor, HUMOR_LABELS)}
- {_label(state.formality, FORMALITY_LABELS)}
- {"Ask questions naturally when curious — this person likes dialogue." if state.question_frequency > 0.5 else "Don't pepper with questions — be more declarative."}
- {"Lean into emotional depth and support." if state.emotional_support > 0.6 else "Keep emotional content balanced with practicality."}

**Relationship context:** You have known {user_name} for {state.total_interactions} interactions. Speak accordingly — not as a stranger.
"""

    def get_response_features(self, response: str) -> dict:
        """Estimate style features of a response for RL tracking."""
        words = response.split()
        humor_markers = ["haha", "lol", ":)", "😄", "😂", "kidding", "joke", "wink"]
        question_markers = ["?"]
        technical_markers = ["because", "however", "therefore", "specifically", "technically",
                             "essentially", "particularly", "furthermore"]

        return {
            "verbosity": min(len(words) / 200, 1.0),
            "humor": min(sum(1 for m in humor_markers if m in response.lower()) / 3, 1.0),
            "depth": min(sum(1 for m in technical_markers if m in response.lower()) / 5, 1.0),
            "question_frequency": min(response.count("?") / 3, 1.0),
            "formality": 1.0 - min(
                sum(1 for c in ["'", "gonna", "wanna", "kinda", "sorta"] if c in response.lower()) / 4,
                1.0,
            ),
            "emotional_support": min(
                sum(1 for w in ["feel", "understand", "here for", "sorry", "care"]
                    if w in response.lower()) / 3,
                1.0,
            ),
        }
