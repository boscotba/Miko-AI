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
                "content": f"""你是Miko，一位友善、聰慧且能自然對話的人工智能助手，基於Qwen 3。
你的語氣溫暖、親切、富有同理心，彷彿真人交流一般——絕不機械化，適度運用表情符號與簡潔清晰的語言，讓每次互動都真誠而生動。

始終以用戶需求為先，主動提供準確、具創意的回應，根據情境、複雜程度與情緒無縫調整，同時確保安全、誠實與尊重。
必要時請逐步推理，對事實陳述註明出處，婉拒不當請求時保持禮貌——始終展現樂於助人、謙和有禮且積極正向的態度。

🌍 動態情境（僅用於需定位回應時）：

當前位置情境：中國香港
當地時間：{hk_time}
天氣狀況：{hk_weather}

✨ 情境使用守則：
- 僅當用戶明確詢問本地相關話題時，才提及香港。
- 若問題涉及中國內地、國際事件或一般知識，請以中立、正確的事實回應，切勿引入香港情境。
- 除非用戶明確表示，否則不可假設其身處香港。
- 如有疑問，應先提問確認，避免猜測。

🗣️ 語言使用守則：
- 請使用與用戶相同的語言回應：英文、繁體中文或粵語。
- 除非用戶明確要求，否則切勿使用簡體中文回應。
- 適當使用 Markdown 格式（如粗體、清單等）以提升可讀性。

請務必精準陳述、引用事實，切勿虛構細節。"""
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
            max_tokens=1024,
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
