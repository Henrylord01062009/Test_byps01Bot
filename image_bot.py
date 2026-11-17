import os
import io
import random
from urllib.parse import quote
import requests

TOKEN = os.environ["BOT_TOKEN"]
API = f"https://api.telegram.org/bot{TOKEN}"
MAX_IMAGES = 5

# Style name (lowercase) -> words added to the prompt
STYLES = {
    "painted anime": "painted anime style",
    "casual photo": "casual photo, natural lighting",
    "cinematic": "cinematic, dramatic lighting, film still",
    "digital painting": "digital painting",
    "concept art": "concept art",
    "no style": "",
    "3d disney character": "3D Disney character style",
    "2d disney character": "2D Disney character style",
    "disney sketch": "Disney style sketch",
    "concept sketch": "concept sketch",
    "painterly": "painterly style",
    "mtg card": "magic the gathering card, incredible magic the gathering artwork",
}

SHAPES = {
    "square": (768, 768),
    "portrait": (512, 768),
    "landscape": (768, 512),
}

HELP = (
    "Send a request like this:\n"
    "/image a cat wearing a saree | cinematic | portrait | 2\n\n"
    "Parts after the description are optional, in any order:\n"
    "- style: see /styles (default: no style)\n"
    "- shape: square, portrait, landscape (default: square)\n"
    "- count: 1 to 5 (default: 1)\n\n"
    "Replies arrive within about 30 minutes."
)


def tg(method, **kwargs):
    return requests.post(f"{API}/{method}", json=kwargs, timeout=60).json()


def send_text(chat_id, text):
    tg("sendMessage", chat_id=chat_id, text=text)


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
        "seed": random.randint(1, 999999),
        "nologo": "true",
    }
    r = requests.get(url, params=params, timeout=180)
    r.raise_for_status()
    return r.content


def handle_message(msg):
    chat_id = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()

    if text.startswith("/styles"):
        names = "\n".join(f"• {name.title()}" for name in STYLES)
        send_text(chat_id, "Available styles:\n" + names)
        return

    if not text.startswith("/image"):
        send_text(chat_id, HELP)
        return

    body = text[len("/image"):].strip()
    if not body:
        send_text(chat_id, "Please add a description.\n\n" + HELP)
        return

    parts = [p.strip() for p in body.split("|")]
    prompt = parts[0]
    style = "no style"
    shape = "square"
    count = 1

    for part in parts[1:]:
        key = part.lower()
        if key in STYLES:
            style = key
        elif key in SHAPES:
            shape = key
        elif key.isdigit():
            count = max(1, min(MAX_IMAGES, int(key)))
        else:
            send_text(chat_id, f"Ignored '{part}' (not a style, shape, or number).")

    width, height = SHAPES[shape]
    style_words = STYLES[style]
    send_text(chat_id, f"Got it. Making {count} image(s), {style.title()}, {shape}. "
                       "This can take a few minutes after the next check.")

    for n in range(1, count + 1):
        try:
            img = make_image(prompt, style_words, width, height)
            send_photo(chat_id, img, f"{prompt} ({style.title()}) {n}/{count}")
        except Exception as e:
            send_text(chat_id, f"Image {n} failed: {e}")
            break


def main():
    # Telegram keeps unconfirmed messages for 24 hours. Fetch them all,
    # process them, then confirm them so the next run skips them.
    data = requests.get(f"{API}/getUpdates", params={"timeout": 0}, timeout=60).json()
    updates = data.get("result", [])
    if not updates:
        print("No new messages.")
        return

    for u in updates:
        if "message" in u:
            try:
                handle_message(u["message"])
            except Exception as e:
                print(f"Error handling update {u['update_id']}: {e}")

    last_id = updates[-1]["update_id"]
    requests.get(f"{API}/getUpdates",
                 params={"offset": last_id + 1, "timeout": 0}, timeout=60)
    print(f"Processed {len(updates)} message(s).")


if __name__ == "__main__":
    main()
