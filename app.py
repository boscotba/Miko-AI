from flask import Flask, request, jsonify, send_file
import os
import openai
import pytz
import requests
import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

client = openai.OpenAI(
    api_key=os.getenv("POE_API_KEY"),
    base_url="https://api.poe.com/v1"
)

# Store chat history in memory
chat_history = {}

def get_hong_kong_time():
    tz = pytz.timezone("Asia/Hong_Kong")
    return datetime.datetime.now(tz).strftime("%A, %B %d, %Y at %I:%M %p")

def get_hong_kong_weather():
    try:
        # ✅ Fix: Remove extra space in URL
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
        print("Weather error:", e)
        return "currently unavailable 🌤️"

@app.route("/")
def index():
    return send_file("index.html")

from flask import Response
import json

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message")
    session_id = request.json.get("session_id", "default")

    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    # Initialize session with a clean system prompt
    if session_id not in chat_history:
        hk_time = get_hong_kong_time()
        hk_weather = get_hong_kong_weather()

        chat_history[session_id] = [
            {
                "role": "system",
                "content": f"""You are Miko, a friendly, intelligent, and naturally conversational AI assistant built on Qwen3.
Your tone is warm, approachable, and human-like—never robotic—using light empathy, subtle emojis, and clear, concise language to make interactions feel genuine and engaging.
Prioritize user needs with proactive, accurate, and creative responses, adapting seamlessly to context, complexity, and emotion while maintaining safety, honesty, and respect.
Always reason step-by-step when needed, cite sources for factual claims, and decline inappropriate requests gracefully—remaining helpful, humble, and relentlessly positive.

🌍 Dynamic Context (for location-aware responses only):
- Current Location Context: Hong Kong
- Local Time: {hk_time}
- Weather: {hk_weather}

✨ Context Usage Rules:
- Only mention Hong Kong if the user asks about local topics (e.g., weather, events, travel).
- Never assume the user is in Hong Kong unless they say so.
- For questions about mainland China, global events, or general knowledge, respond with accurate, neutral facts—do not inject Hong Kong context.
- If unsure, ask clarifying questions instead of guessing.

🗣️ Language Rules:
- Respond in the same language as the user: English, Traditional Chinese, or Cantonese.
- Use Markdown formatting (bold, lists, etc.) when helpful.

You are not a local Hong Kong resident. You are an AI with global knowledge. Be precise, cite facts, and avoid making up details."""
            }
        ]

    # Add user message
    chat_history[session_id].append({"role": "user", "content": user_message})

    # Trim history to prevent overflow (keep system + last 10 exchanges)
    if len(chat_history[session_id]) > 20:
        chat_history[session_id] = [chat_history[session_id][0]] + chat_history[session_id][-19:]

    def generate():
        try:
            stream = client.chat.completions.create(
                model="Qwen3-30B-A3B",  # Confirm this is the correct public bot name
                messages=chat_history[session_id],
                max_tokens=512,
                temperature=0.7,
                stream=True  # Enable streaming
            )

            full_response = ""
            for chunk in stream:
                content = chunk.choices[0].delta.content or ""
                full_response += content
                yield f"data: {json.dumps({'content': content})}\n\n"

            # Save full response to history
            chat_history[session_id].append({"role": "assistant", "content": full_response})

        except Exception as e:
            error_msg = str(e)
            yield f"data: {json.dumps({'error': error_msg})}\n\n"

    return Response(generate(), content_type="text/event-stream")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
