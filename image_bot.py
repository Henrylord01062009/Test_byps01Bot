import os
import io
import random
from urllib.parse import quote
import requests

TOKEN = os.environ["BOT_TOKEN"]
API = f"https://api.telegram.org/bot{TOKEN}"
MAX_IMAGES = 5

# (button name, words added to the prompt). Add more styles here, one line each.
STYLES = [
    ("Painted Anime", "painted anime style"),
    ("Casual Photo", "casual photo, natural lighting"),
    ("Cinematic", "cinematic, dramatic lighting, film still"),
    ("Digital Painting", "digital painting"),
    ("Concept Art", "concept art"),
    ("No style", ""),
    ("3D Disney Character", "3D Disney character style"),
    ("2D Disney Character", "2D Disney character style"),
    ("Disney Sketch", "Disney style sketch"),
    ("Concept Sketch", "concept sketch"),
    ("Painterly", "painterly style"),
    ("MTG Card", "magic the gathering card, incredible magic the gathering artwork"),
]

SHAPES = {
    "sq": (768, 768, "Square"),
    "po": (512, 768, "Portrait"),
    "la": (768, 512, "Landscape"),
}

pending = {}  # chat_id -> {"prompt", "style", "shape"}


def tg(method, **kwargs):
    return requests.post(f"{API}/{method}", json=kwargs, timeout=120).json()


def send_text(chat_id, text, keyboard=None):
    data = {"chat_id": chat_id, "text": text}
    if keyboard:
        data["reply_markup"] = {"inline_keyboard": keyboard}
    tg("sendMessage", **data)


def style_keyboard():
    buttons = [{"text": name, "callback_data": f"s{i}"} for i, (name, _) in enumerate(STYLES)]
    return [buttons[i:i + 2] for i in range(0, len(buttons), 2)]


def shape_keyboard():
    return [[{"text": name, "callback_data": f"h{key}"} for key, (_, _, name) in SHAPES.items()]]


def count_keyboard():
    return [[{"text": str(n), "callback_data": f"n{n}"} for n in range(1, MAX_IMAGES + 1)]]


def send_photo(chat_id, image_bytes, caption):
    requests.post(
        f"{API}/sendPhoto",
        data={"chat_id": chat_id, "caption": caption[:1000]},
        files={"photo": ("image.png", image_bytes, "image/png")},
        timeout=180,
    )


def make_image(prompt, style_words, width, height):
    full_prompt = f"{prompt}, {style_words}" if style_words else prompt
    url = f"https://image.pollinations.ai/prompt/{quote(full_prompt)}"
    params = {
        "width": width,
        "height": height,
        "seed": random.randint(1, 999999),  # different seed = different picture each time
        "nologo": "true",
    }
    r = requests.get(url, params=params, timeout=180)
    r.raise_for_status()
    return r.content


def handle_message(msg):
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip()

    if text.startswith("/image"):
        prompt = text[len("/image"):].strip()
        if not prompt:
            send_text(chat_id, "Please add a description, e.g. /image a cat wearing a saree")
            return
        pending[chat_id] = {"prompt": prompt, "style": None, "shape": None}
        send_text(chat_id, "Choose an art style:", style_keyboard())

    elif text.startswith("/styles"):
        names = "\n".join(f"• {name}" for name, _ in STYLES)
        send_text(chat_id, "Available styles:\n" + names)

    else:
        send_text(chat_id,
                  "Send /image followed by a description, e.g. /image sunset over Chennai beach\n"
                  "Send /styles to see all art styles.")


def handle_callback(cb):
    tg("answerCallbackQuery", callback_query_id=cb["id"])
    chat_id = cb["message"]["chat"]["id"]
    data = cb.get("data", "")

    if chat_id not in pending:
        send_text(chat_id, "Please send /image and a description first.")
        return

    if data.startswith("s"):
        pending[chat_id]["style"] = int(data[1:])
        send_text(chat_id, "Choose a shape:", shape_keyboard())

    elif data.startswith("h"):
        pending[chat_id]["shape"] = data[1:]
        send_text(chat_id, "How many images do you want?", count_keyboard())

    elif data.startswith("n"):
        info = pending.pop(chat_id)
        style_name, style_words = STYLES[info["style"]]
        width, height, shape_name = SHAPES[info["shape"]]
        count = int(data[1:])
        send_text(chat_id, f"Creating {count} image(s) in '{style_name}' style, {shape_name}, please wait...")
        for n in range(1, count + 1):
            try:
                send_photo(chat_id,
                           make_image(info["prompt"], style_words, width, height),
                           f"{info['prompt']} ({style_name}) {n}/{count}")
            except Exception as e:
                send_text(chat_id, f"Image {n} failed: {e}")
                break


offset = None
while True:
    updates = requests.get(f"{API}/getUpdates",
                           params={"timeout": 30, "offset": offset},
                           timeout=40).json()
    for u in updates.get("result", []):
        offset = u["update_id"] + 1
        if "message" in u:
            handle_message(u["message"])
        elif "callback_query" in u:
            handle_callback(u["callback_query"])
