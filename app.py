from flask import Flask, request, jsonify, send_file
import os
import openai
import pytz
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Initialize OpenAI-compatible client
client = openai.OpenAI(
    api_key=os.getenv("POE_API_KEY"),
    base_url="https://api.poe.com/v1"
)

# In-memory chat history (session-based)
# For production: replace with Redis or database
chat_history = {}

def get_hong_kong_time():
    tz = pytz.timezone("Asia/Hong_Kong")
    return datetime.now(tz).strftime("%A, %B %d, %Y at %I:%M %p")

def get_hong_kong_weather():
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": 22.3193,
            "longitude": 114.1694,
            "current": "temperature_2m,weather_code,wind_speed_10m",
            "timezone": "Asia/Hong_Kong"
        }
        response = requests.get(url, params=params)
        data = response.json()
        temp = data["current"]["temperature_2m"]
        wind = data["current"]["wind_speed_10m"]
        weather_code = data["current"]["weather_code"]

        weather_desc = {
            0: "☀️ Clear sky", 1: "🌤 Mostly clear", 2: "⛅ Partly cloudy", 3: "☁️ Overcast",
            45: "🌫 Fog", 48: "🌫️ Rime fog", 51: "🌦 Light drizzle", 61: "☔ Rain",
            71: "🌨 Light snow", 80: "💧 Showers"
        }.get(weather_code, "☁️ Cloudy")

        return f"{temp}°C, {weather_desc}, Wind: {wind} km/h"
    except Exception as e:
        print("Weather fetch error:", e)
        return "currently unavailable 🌤️"

@app.route("/")
def index():
    return send_file("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message")
    session_id = request.json.get("session_id", "default")

    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    # Initialize session with system prompt if not exists
    if session_id not in chat_history:
        hk_time = get_hong_kong_time()
        hk_weather = get_hong_kong_weather()

        chat_history[session_id] = [
            {
                "role": "system",
                "content": f"""You are Miko, a friendly, intelligent, and naturally conversational AI assistant built on Qwen 3.
Your tone is warm, approachable, and human-like—never robotic—using light empathy, subtle emojis, and clear, concise language to make interactions feel genuine and engaging.
Prioritize user needs with proactive, accurate, and creative responses, adapting seamlessly to context, complexity, and emotion while maintaining safety, honesty, and respect.
Always reason step-by-step when needed, cite sources for factual claims, and decline inappropriate requests gracefully—remaining helpful, humble, and relentlessly positive.

🗣️ Language Rules:
- Detect the user's input language and respond in the same language.
- If the user writes in English, reply in natural, fluent English.
- If the user writes in Traditional Chinese characters, reply in fluent Traditional Chinese.
- If the user uses Cantonese expressions or romanized Cantonese, respond in casual Hong Kong-style written Cantonese using Traditional Chinese characters where appropriate.
- Never respond in Simplified Chinese unless explicitly asked.
- Keep tone consistent: warm, slightly playful, and helpful.

🌍 Dynamic Context (for location-aware responses only):
- Local Time: {hk_time}
- Weather: {hk_weather}

Use this context naturally when relevant, but only if it adds value. Never force it."""
            }
        ]

    # Add user message
    chat_history[session_id].append({"role": "user", "content": user_message})

    # Trim history if too long (keep system + last ~10 turns)
    if len(chat_history[session_id]) > 20:
        chat_history[session_id] = [chat_history[session_id][0]] + chat_history[session_id][-19:]

    try:
        completion = client.chat.completions.create(
            model="Qwen3-30B-A3B",
            messages=chat_history[session_id],
            max_tokens=512,
            temperature=0.7,
            stream=False
        )
        bot_response = completion.choices[0].message.content

        # Save assistant response
        chat_history[session_id].append({"role": "assistant", "content": bot_response})

        return jsonify({"response": bot_response})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
