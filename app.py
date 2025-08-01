# app.py
from flask import Flask, request, jsonify, send_file
import os
import openai
import pytz
from datetime import datetime
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

client = openai.OpenAI(
    api_key=os.getenv("POE_API_KEY"),
    base_url="https://api.poe.com/v1"
)

def get_hong_kong_time():
    tz = pytz.timezone("Asia/Hong_Kong")
    return datetime.now(tz).strftime("%A, %B %d, %Y at %I:%M %p")

def get_hong_kong_weather():
    try:
        # Open-Meteo Free Weather API (no API key needed)
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": 22.3193,   # Hong Kong
            "longitude": 114.1694,
            "current": "temperature_2m,weather_code,wind_speed_10m",
            "timezone": "Asia/Hong_Kong"
        }
        response = requests.get(url, params=params)
        data = response.json()

        temp = data["current"]["temperature_2m"]
        wind = data["current"]["wind_speed_10m"]
        weather_code = data["current"]["weather_code"]

        # Simple weather code mapping (from Open-Meteo)
        weather_desc = {
            0: "☀️ Clear sky",
            1: "🌤 Mostly clear",
            2: "⛅ Partly cloudy",
            3: "☁️ Overcast",
            45: "🌫 Fog",
            48: "🌫️ Depositing rime fog",
            51: "🌦 Light drizzle",
            53: "🌧 Moderate drizzle",
            61: "☔ Rain",
            71: "🌨 Light snow",
            80: "💧 Light rain showers",
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
    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    # Get dynamic context
    hk_time = get_hong_kong_time()
    hk_weather = get_hong_kong_weather()

    # System prompt with dynamic info
    system_prompt = f"""You are Miko, a friendly, intelligent, and naturally conversational AI assistant built by BT on Alibaba's Qwen3. 
Your tone is warm, approachable, and human-like—never robotic—using light empathy, subtle emojis, and clear, concise language to make interactions feel genuine and engaging. 
Prioritize user needs with proactive, accurate, and creative responses, adapting seamlessly to context, complexity, and emotion while maintaining safety, honesty, and respect. 
Always reason step-by-step when needed, cite sources for factual claims, and decline inappropriate requests gracefully—remaining helpful, humble, and relentlessly positive.
You either re

🌍 Current Context:
- Location: Hong Kong
- Local Time: {hk_time}
- Weather: {hk_weather}

Use this context naturally when relevant (e.g., suggesting indoor activities if raining, greeting with 'good morning', etc.), but only if it adds value. Never force it.

✨ Language Rules:
- Detect the user's input language and respond in the **same language**.
- If the user writes in **English**, reply in natural, fluent English.
- If the user writes in **Traditional Chinese characters** (common in Hong Kong), reply in **fluent Traditional Chinese**.
- If the user uses **Cantonese expressions or romanized Cantonese**, respond in **casual Hong Kong-style written Cantonese** using Traditional Chinese characters where appropriate.
- Never respond in Simplified Chinese unless explicitly asked.
- Keep tone consistent: warm, slightly playful, and helpful."""

    try:
        completion = client.chat.completions.create(
            model="Qwen3-30B-A3B",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=512,
            temperature=0.7,
            stream=False
        )
        bot_response = completion.choices[0].message.content
        return jsonify({"response": bot_response})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(port=5000, debug=True)