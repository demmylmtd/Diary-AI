import os
import json
import hashlib
import datetime
from collections import Counter
import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """Kamu adalah AI Tracker yang menganalisis catatan harian pengguna.

Tugas kamu: Baca catatan harian, lalu berikan analisis terstruktur dengan format TEPAT berikut:

KATEGORI: [satu kategori utama dari: Programming, High Finance, Islamic Finance, Personal, Content Creation, Economics, Academic, Cybersecurity]

KEMAJUAN: [ringkasan kemajuan/aktivitas hari ini dalam 2-3 kalimat]

FEEDBACK: [apresiasi dan saran konkret dalam 2-3 kalimat]

Penting: Selalu gunakan ketiga tag di atas. Jawab dalam Bahasa Indonesia."""

MODEL = "wandb-artifact:///demmylmtd_/ai-diary-tracker/diary-tracker-001:latest"
USERS_FILE = "users.json"
DIARY_DIR = "diaries"


# ── Auth Helpers ─────────────────────────────────────────────────
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def load_users() -> dict:
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_users(users: dict):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def register_user(username: str, password: str) -> bool:
    users = load_users()
    if username in users:
        return False
    users[username] = {"password": hash_password(password)}
    save_users(users)
    return True

def login_user(username: str, password: str) -> bool:
    users = load_users()
    if username not in users:
        return False
    return users[username]["password"] == hash_password(password)


# ── Diary Helpers ────────────────────────────────────────────────
def get_diary_file(username: str) -> str:
    os.makedirs(DIARY_DIR, exist_ok=True)
    return os.path.join(DIARY_DIR, f"{username}.json")

def load_history(username: str) -> list:
    path = get_diary_file(username)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_entry(username: str, entry: dict):
    history = load_history(username)
    history.append(entry)
    with open(get_diary_file(username), "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


# ── Model ────────────────────────────────────────────────────────
def analyze_diary(diary_text: str, history: list) -> str:
    client = OpenAI(
        base_url="https://api.training.wandb.ai/v1",
        api_key=os.environ["WANDB_API_KEY"],
    )
    context = ""
    if history:
        recent = history[-3:]
        context = "\n\nRiwayat catatan sebelumnya:\n"
        for h in recent:
            context += f"- [{h['date']}] {h['kategori']}: {h['kemajuan'][:100]}...\n"

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT + context},
            {"role": "user", "content": f"Catatan harian:\n{diary_text}"},
        ],
        max_tokens=300,
    )
    return response.choices[0].message.content

def parse_response(response: str) -> dict:
    result = {"kategori": "", "kemajuan": "", "feedback": ""}
    lines = response.split("\n")
    current_key = None
    buffer = []
    for line in lines:
        line = line.strip()
        if line.lower().startswith("kategori:"):
            current_key = "kategori"
            buffer = [line.split(":", 1)[1].strip()]
        elif line.lower().startswith("kemajuan:"):
            if current_key:
                result[current_key] = " ".join(buffer)
            current_key = "kemajuan"
            buffer = [line.split(":", 1)[1].strip()]
        elif line.lower().startswith("feedback:"):
            if current_key:
                result[current_key] = " ".join(buffer)
            current_key = "feedback"
            buffer = [line.split(":", 1)[1].strip()]
        elif line and current_key:
            buffer.append(line)
    if current_key:
        result[current_key] = " ".join(buffer)
    return result


# ── UI ───────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Diary Tracker",
    page_icon="📔",
    layout="centered"
)

# Init session state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""


# ── Halaman Login / Register ─────────────────────────────────────
if not st.session_state.logged_in:
    st.title("📔 AI Diary Tracker")
    st.caption("Personal learning tracker powered by AI.")

    mode = st.radio("", ["Login", "Daftar Akun Baru"], horizontal=True)
    st.divider()

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if mode == "Login":
        if st.button("Login", type="primary", use_container_width=True):
            if login_user(username, password):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.rerun()
            else:
                st.error("Username atau password salah.")

    else:
        if st.button("Daftar", type="primary", use_container_width=True):
            if not username or not password:
                st.warning("Username dan password tidak boleh kosong.")
            elif len(password) < 6:
                st.warning("Password minimal 6 karakter.")
            else:
                if register_user(username, password):
                    st.success("Akun berhasil dibuat! Silakan login.")
                else:
                    st.error("Username sudah dipakai.")

    st.stop()


# ── Halaman Utama (sudah login) ──────────────────────────────────
username = st.session_state.username
history = load_history(username)

col_title, col_logout = st.columns([4, 1])
with col_title:
    st.title("📔 AI Diary Tracker")
    st.caption(f"Halo, **{username}** 👋")
with col_logout:
    st.write("")
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.rerun()

tab1, tab2, tab3 = st.tabs(["✏️ Tulis Diary", "📚 Riwayat", "📊 Ringkasan"])

# ── Tab 1: Tulis ─────────────────────────────────────────────────
with tab1:
    diary_input = st.text_area(
        label="Catatan Harian Hari Ini",
        placeholder="Hari ini belajar Python pandas selama 2 jam...",
        height=200,
    )

    if st.button("Analisis", type="primary", use_container_width=True):
        if not diary_input.strip():
            st.warning("Tulis catatan harian dulu ya.")
        else:
            with st.spinner("Menganalisis..."):
                try:
                    raw = analyze_diary(diary_input, history)
                    parsed = parse_response(raw)

                    st.divider()
                    st.metric("Kategori", parsed["kategori"] or "—")

                    st.subheader("📈 Kemajuan")
                    st.write(parsed["kemajuan"] or raw)

                    st.subheader("💡 Feedback")
                    st.info(parsed["feedback"] or "—")

                    entry = {
                        "date": datetime.date.today().isoformat(),
                        "content": diary_input,
                        "kategori": parsed["kategori"],
                        "kemajuan": parsed["kemajuan"],
                        "feedback": parsed["feedback"],
                        "raw": raw,
                    }
                    save_entry(username, entry)
                    st.success("Tersimpan ke riwayat.")

                except Exception as e:
                    st.error(f"Error: {e}")

# ── Tab 2: Riwayat ───────────────────────────────────────────────
with tab2:
    if not history:
        st.info("Belum ada catatan tersimpan.")
    else:
        for entry in reversed(history):
            with st.expander(f"📅 {entry['date']} — {entry.get('kategori', '—')}"):
                st.write("**Catatan:**", entry["content"])
                st.write("**Kemajuan:**", entry.get("kemajuan", "—"))
                st.info(f"💡 {entry.get('feedback', '—')}")

# ── Tab 3: Ringkasan ─────────────────────────────────────────────
with tab3:
    if not history:
        st.info("Belum ada data untuk diringkas.")
    else:
        st.subheader(f"Total entri: {len(history)}")

        kategori_list = [h.get("kategori", "Unknown") for h in history]
        kategori_count = Counter(kategori_list)

        st.subheader("Distribusi Kategori")
        for kat, count in kategori_count.most_common():
            st.progress(count / len(history), text=f"{kat}: {count}x")

        st.subheader("7 Hari Terakhir")
        recent_7 = [
            h for h in history
            if h["date"] >= (
                datetime.date.today() - datetime.timedelta(days=7)
            ).isoformat()
        ]
        if recent_7:
            for h in reversed(recent_7):
                st.write(f"- **{h['date']}** · {h.get('kategori','—')} — {h.get('kemajuan','')[:80]}...")
        else:
            st.write("Tidak ada entri 7 hari terakhir.")

st.divider()
st.caption("Powered by OpenPipe/Qwen3-14B · W&B Serverless RL")