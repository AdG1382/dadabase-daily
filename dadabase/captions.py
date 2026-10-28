"""Captions, titles and hashtags. Prompts rotate so posts don't read identically."""
from . import config
from .queue import Joke

PROMPTS = [
    "Rate this groan from 1 to 10 \U0001F447",
    "Tag the person who would say this at dinner \U0001F602",
    "Groan or grin? Tell us below \U0001F447",
    "Send this to your dad. You know he'll use it.",
    "Can you top this one? Drop your best dad joke below.",
    "Be honest: did you see that coming?",
]

TAGS = {
    "food": ["foodjokes", "chai", "desifood"],
    "family": ["desiparents", "indianfamily", "relatable"],
    "work": ["officehumour", "corporatelife", "officejokes"],
    "school": ["examseason", "studentlife", "indianparents"],
    "sports": ["cricket", "cricketlovers", "cricketjokes"],
    "tech": ["techhumour", "geekjokes", "relatable"],
    "travel": ["indiantraffic", "roadtrip", "mumbailocal"],
    "weather": ["monsoon", "weatherjokes", "relatable"],
    "festivals": ["festivevibes", "diwali", "indianfestivals"],
    "music": ["bollywood", "indianwedding", "musicjokes"],
    "animals": ["animaljokes", "punny", "funnyanimals"],
    "science": ["sciencejokes", "nerdhumour", "punny"],
    "puns": ["puns", "punintended", "wordplay"],
}
BASE_TAGS = ["dadjokes", "dadjoke", "desihumour", "punny", "cleanjokes", "dadabasedaily"]


def _prompt(j: Joke) -> str:
    return PROMPTS[j.index % len(PROMPTS)]


def hashtags(j: Joke, n: int = 10) -> list[str]:
    seen, out = set(), []
    for t in BASE_TAGS + TAGS.get(j.category, []):
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out[:n]


def carousel_caption(j: Joke) -> str:
    tags = " ".join(f"#{t}" for t in hashtags(j))
    return (f"{j.setup}\n\nSwipe for the punchline ➡️\n\n{_prompt(j)}\n\n"
            f"A new dad joke every day. More at {config.SITE_URL.replace('https://', '')}\n\n{tags}")


def reel_caption(j: Joke) -> str:
    tags = " ".join(f"#{t}" for t in hashtags(j))
    return f"{j.setup} \U0001F941\n\n{_prompt(j)}\n\nFollow {config.HANDLE} for one dad joke a day.\n\n{tags}"


def youtube_title(j: Joke) -> str:
    base = j.setup if len(j.setup) <= 88 else j.setup[:85].rsplit(" ", 1)[0] + "…"
    return f"{base} #shorts"


def youtube_description(j: Joke) -> str:
    tags = " ".join(f"#{t}" for t in hashtags(j, 6))
    return (f"{_prompt(j)}\n\nOne dad joke every day. Subscribe for daily groans.\n"
            f"Hundreds more jokes: {config.SITE_URL}\nInstagram: {config.INSTAGRAM_URL}\n\n{tags}")
