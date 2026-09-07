"""
Snake Leaderboard Server
=========================
خادم بسيط بلغة Flask لمشاركة لوحة صدارة لعبة الثعبان بين لاعبين على
أجهزة مختلفة عبر الشبكة المحلية أو الإنترنت.

المتطلبات:
    pip install flask

التشغيل:
    python server.py

سيعمل الخادم افتراضيًا على المنفذ 5000 ويقبل اتصالات من أي جهاز (0.0.0.0).

للسماح للاعبين على نفس الشبكة المحلية بالاتصال:
    1. شغّل هذا الملف على جهاز واحد (سيكون بمثابة "الخادم").
    2. اعرف عنوان IP الخاص بهذا الجهاز على الشبكة المحلية (مثال: 192.168.1.10).
       - على ويندوز: افتح cmd واكتب  ipconfig
       - على ماك/لينكس: افتح Terminal واكتب  ifconfig  أو  ip addr
    3. في ملف snake_game.py عند كل لاعب آخر، غيّر قيمة SERVER_URL إلى:
       "http://192.168.1.10:5000"  (استبدل الرقم بعنوان جهاز الخادم الفعلي)
    4. تأكد أن جدار الحماية (Firewall) يسمح بالاتصال على المنفذ 5000.

للنشر على الإنترنت (بحيث يلعب أشخاص من أي مكان، وليس فقط نفس الشبكة):
    يمكن رفع هذا الملف على خدمة استضافة مثل Render أو Railway أو PythonAnywhere،
    ثم استخدام الرابط العام الذي تمنحك إياه الخدمة كقيمة لـ SERVER_URL.
"""

import json
import os
import threading

from flask import Flask, jsonify, request

app = Flask(__name__)

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leaderboard_server.json")
MAX_STORED_ENTRIES = 100
MAX_RETURNED_ENTRIES = 20

# قفل بسيط لمنع تعارض الكتابة عند وصول طلبات متزامنة من عدة لاعبين
lock = threading.Lock()


def load_data():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_data(entries):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


@app.route("/", methods=["GET"])
def health_check():
    """نقطة بسيطة للتأكد من أن الخادم يعمل."""
    return jsonify({"status": "ok", "message": "خادم لوحة صدارة Snake يعمل بنجاح"})


@app.route("/leaderboard", methods=["GET"])
def get_leaderboard():
    """يعيد أفضل النتائج مرتبة تنازليًا."""
    with lock:
        entries = load_data()
    entries.sort(key=lambda e: e.get("score", 0), reverse=True)
    return jsonify(entries[:MAX_RETURNED_ENTRIES])


@app.route("/score", methods=["POST"])
def post_score():
    """يستقبل نتيجة جديدة من لاعب ويحدّث لوحة الصدارة إذا كانت أفضل من سابقتها."""
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()[:16]
    score = payload.get("score")

    if not username:
        return jsonify({"error": "اسم مستخدم غير صالح"}), 400
    if not isinstance(score, int) or isinstance(score, bool) or score < 0:
        return jsonify({"error": "نتيجة غير صالحة"}), 400

    with lock:
        entries = load_data()
        is_new_best = True
        found = False
        for entry in entries:
            if entry.get("username", "").lower() == username.lower():
                found = True
                if score > entry.get("score", 0):
                    entry["score"] = score
                else:
                    is_new_best = False
                break
        if not found:
            entries.append({"username": username, "score": score})

        entries.sort(key=lambda e: e.get("score", 0), reverse=True)
        entries = entries[:MAX_STORED_ENTRIES]
        save_data(entries)

    return jsonify({
        "leaderboard": entries[:MAX_RETURNED_ENTRIES],
        "is_new_best": is_new_best,
    })


if __name__ == "__main__":
    print("=" * 50)
    print("خادم لوحة صدارة Snake يعمل الآن")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=False)
