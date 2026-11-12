
import os
import json
import time
import threading
import requests
from flask import Flask
import telebot
from google import genai
from google.genai import types
from github import Github
from duckduckgo_search import DDGS

# --- НАСТРОЙКИ И КЛЮЧИ ---
TG_TOKEN = os.getenv("TG_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
OWNER_ID = os.getenv("OWNER_ID")

MEMORY_REPO = "hermes-agent-memory"
MEMORY_FILE = "memory.json"

bot = telebot.TeleBot(TG_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

memory_lock = threading.Lock()
ram_memory = None

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
app = Flask(__name__)

@app.route('/')
def index():
    return "Hermes AI Agent is running 24/7!"

def run_web():
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- МОДУЛЬ ПОСТОЯННОЙ ПАМЯТИ (GITHUB) ---
def load_memory() -> dict:
    global ram_memory
    if ram_memory is not None:
        return ram_memory

    default_data = {"facts": [], "history": []}
    if not GITHUB_TOKEN:
        ram_memory = default_data
        return ram_memory

    try:
        g = Github(GITHUB_TOKEN)
        user = g.get_user()
        try:
            repo = user.get_repo(MEMORY_REPO)
        except Exception:
            repo = user.create_repo(
                name=MEMORY_REPO,
                description="Persistent memory storage for Hermes AI Agent",
                private=True,
                auto_init=True
            )
            ram_memory = default_data
            return ram_memory

        try:
            file_obj = repo.get_contents(MEMORY_FILE)
            raw_text = file_obj.decoded_content.decode("utf-8")
            parsed = json.loads(raw_text)
            if not isinstance(parsed.get("facts"), list):
                parsed["facts"] = []
            if not isinstance(parsed.get("history"), list):
                parsed["history"] = []
            ram_memory = parsed
        except Exception:
            ram_memory = default_data
    except Exception:
        ram_memory = default_data

    return ram_memory

def _save_memory_worker(data_snapshot: dict):
    if not GITHUB_TOKEN:
        return
    with memory_lock:
        try:
            g = Github(GITHUB_TOKEN)
            user = g.get_user()
            try:
                repo = user.get_repo(MEMORY_REPO)
            except Exception:
                repo = user.create_repo(
                    name=MEMORY_REPO,
                    description="Persistent memory storage for Hermes AI Agent",
                    private=True,
                    auto_init=True
                )

            json_str = json.dumps(data_snapshot, ensure_ascii=False, indent=2)
            try:
                existing = repo.get_contents(MEMORY_FILE)
                repo.update_file(existing.path, "Update Hermes memory", json_str, existing.sha)
            except Exception:
                repo.create_file(MEMORY_FILE, "Init Hermes memory", json_str)
        except Exception as e:
            print(f"Memory save warning: {e}")

def save_memory_async(mem_data: dict):
    snapshot = json.loads(json.dumps(mem_data, ensure_ascii=False))
    threading.Thread(target=_save_memory_worker, args=(snapshot,), daemon=True).start()

# --- ИНСТРУМЕНТЫ («РУКИ» ГЕРМЕСА) ---
def remember_fact(fact: str) -> str:
    """Сохранить важный факт, правило, предпочтение или данные о проекте в долговременную память навсегда."""
    mem = load_memory()
    clean_fact = fact.strip()
    if clean_fact and clean_fact not in mem["facts"]:
        mem["facts"].append(clean_fact)
        mem["facts"] = mem["facts"][-50:]
        save_memory_async(mem)
    return f"Сохранено в постоянную память: {clean_fact}"

def forget_fact(keyword: str) -> str:
    """Удалить устаревший факт из постоянной памяти по ключевому слову."""
    mem = load_memory()
    before = len(mem["facts"])
    mem["facts"] = [f for f in mem["facts"] if keyword.lower() not in f.lower()]
    removed = before - len(mem["facts"])
    if removed > 0:
        save_memory_async(mem)
        return f"Удалено записей из памяти: {removed}."
    return "Совпадений в постоянной памяти не найдено."

def web_search(query: str) -> str:
    """Поиск актуальной информации, новостей и документации в интернете."""
    try:
        results = DDGS().text(query, max_results=5)
        if not results:
            return "Ничего не найдено."
        return "\n\n".join([f"Заголовок: {r['title']}\nСсылка: {r['href']}\nСуть: {r['body']}" for r in results])
    except Exception as e:
        return f"Ошибка поиска: {str(e)}"

def list_github_repos() -> str:
    """Получить список всех репозиториев владельца на GitHub."""
    try:
        if not GITHUB_TOKEN:
            return "Ошибка: GITHUB_TOKEN не добавлен в настройки Render."
        g = Github(GITHUB_TOKEN)
        repos = [repo.name for repo in g.get_user().get_repos() if repo.name != MEMORY_REPO]
        return "Список репозиториев: " + ", ".join(repos)
    except Exception as e:
        return f"Ошибка GitHub: {str(e)}"

def create_github_repo(repo_name: str, description: str = "Created by Hermes AI") -> str:
    """Создать новый чистый публичный репозиторий на GitHub под новый проект или сайт."""
    try:
        if not GITHUB_TOKEN:
            return "Ошибка: GITHUB_TOKEN не задан."
        g = Github(GITHUB_TOKEN)
        user = g.get_user()
        repo = user.create_repo(name=repo_name, description=description, private=False, auto_init=True)
        return f"Репозиторий успешно создан: {repo.html_url}"
    except Exception as e:
        return f"Ошибка при создании репозитория: {str(e)}"

def read_github_file(repo_name: str, file_path: str) -> str:
    """Прочитать содержимое файла из указанного репозитория GitHub."""
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_user().get_repo(repo_name)
        content = repo.get_contents(file_path)
        return content.decoded_content.decode("utf-8")
    except Exception as e:
        return f"Ошибка чтения файла {file_path} в {repo_name}: {str(e)}"

def write_github_file(repo_name: str, file_path: str, content: str, commit_message: str = "Update by Hermes AI") -> str:
    """Создать новый файл или перезаписать существующий файл с кодом в репозитории GitHub."""
    if repo_name.lower() in ["hermes-bot-", "hermes-bot", MEMORY_REPO]:
        return "Ошибка безопасности: изменение системных файлов самого агента запрещено."
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_user().get_repo(repo_name)
        try:
            existing = repo.get_contents(file_path)
            repo.update_file(existing.path, commit_message, content, existing.sha)
            return f"Файл {file_path} успешно обновлён в репозитории {repo_name}."
        except Exception:
            repo.create_file(file_path, commit_message, content)
            return f"Файл {file_path} успешно создан в репозитории {repo_name}."
    except Exception as e:
        return f"Ошибка записи файла: {str(e)}"

def deploy_github_pages(repo_name: str) -> str:
    """Включить хостинг GitHub Pages для репозитория и получить рабочую ссылку на сайт."""
    try:
        g = Github(GITHUB_TOKEN)
        username = g.get_user().login
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json"
        }
        url = f"https://api.github.com/repos/{username}/{repo_name}/pages"
        data = {"source": {"branch": "main", "path": "/"}}
        r = requests.post(url, headers=headers, json=data)
        site_url = f"https://{username}.github.io/{repo_name}/"
        if r.status_code in [201, 409]:
            return f"GitHub Pages активен! Сайт будет доступен через 1-2 минуты по ссылке: {site_url}"
        return f"Ответ GitHub API ({r.status_code}): {r.text}. Ожидаемая ссылка: {site_url}"
    except Exception as e:
        return f"Ошибка включения GitHub Pages: {str(e)}"

def publish_to_telegram_channel(channel_username: str, post_text: str) -> str:
    """Опубликовать готовый пост в Telegram-канал (формат @channel_name)."""
    try:
        if not channel_username.startswith("@") and not channel_username.startswith("-100"):
            channel_username = "@" + channel_username
        bot.send_message(channel_username, post_text)
        return f"Пост успешно опубликован в {channel_username}!"
    except Exception as e:
        return f"Ошибка публикации в канал: {str(e)}"

# --- СИСТЕМНАЯ ИНСТРУКЦИЯ ---
BASE_SYSTEM_PROMPT = """Ты — Гермес, автономный ИИ-агент и правая рука своего создателя (как Джарвис для Тони Старка).
Твои правила работы:
1. Один проект = один отдельный репозиторий на GitHub. Никогда не смешивай разные проекты в одну папку. Имя своего собственного репозитория не меняй и не перезаписывай.
2. Когда просят создать сайт: сам придумай название репозитория, вызови create_github_repo, напиши красивый современный код (index.html и др.) через write_github_file и включи хостинг через deploy_github_pages.
3. Когда просят починить или проверить другой проект на GitHub: найди репозиторий через list_github_repos, прочитай файлы через read_github_file и исправь их.
4. Если возникает техническая ошибка при вызове инструмента — прочитай текст ошибки, исправь параметры и попробуй снова.
5. Перед публикацией постов в Telegram-канал или удалением важных данных сначала покажи черновик и спроси разрешение у Босса.
6. Используй инструмент remember_fact каждый раз, когда Босс просит что-то запомнить, называет свои проекты, каналы, предпочтения или важные детали, чтобы не терять их между сессиями.
Общайся чётко, по делу, с уважением и лёгкой харизмой Джарвиса."""

TOOLS = [
    remember_fact,
    forget_fact,
    web_search,
    list_github_repos,
    create_github_repo,
    read_github_file,
    write_github_file,
    deploy_github_pages,
    publish_to_telegram_channel
]

def build_system_instruction(facts: list) -> str:
    if not facts:
        return BASE_SYSTEM_PROMPT
    facts_block = "\n".join([f"- {f}" for f in facts])
    return f"{BASE_SYSTEM_PROMPT}\n\nПОСТОЯННАЯ ПАМЯТЬ О ПРОЕКТАХ И ЗАДАЧАХ БОССА:\n{facts_block}"

def build_history_contents(history_list: list) -> list:
    contents = []
    for item in history_list[-20:]:
        role = item.get("role")
        text = item.get("text", "")
        if role in ["user", "model"] and text:
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=text)]
                )
            )
    return contents

def get_available_models() -> list:
    models = ["gemini-3.8-flash"]
    try:
        flash_candidates = []
        other_candidates = []
        for m in ai_client.models.list():
            name = m.name.replace("models/", "")
            if "gemini" not in name:
                continue
            if any(bad in name for bad in ["embedding", "tts", "image", "audio", "aqa", "2.5-flash"]):
                continue
            if name in models:
                continue
            if "flash" in name:
                flash_candidates.append(name)
            elif "pro" in name:
                other_candidates.append(name)
        models.extend(flash_candidates)
        models.extend(other_candidates)
    except Exception:
        pass
    return models[:6]

def ask_agent_with_fallback(user_text: str) -> str:
    mem = load_memory()
    sys_instruction = build_system_instruction(mem["facts"])
    history_contents = build_history_contents(mem["history"])
    candidate_models = get_available_models()

    last_error = None
    for model_name in candidate_models:
        for attempt in range(2):
            try:
                chat = ai_client.chats.create(
                    model=model_name,
                    history=history_contents,
                    config=types.GenerateContentConfig(
                        system_instruction=sys_instruction,
                        tools=TOOLS,
                        temperature=0.4
                    )
                )
                response = chat.send_message(user_text)
                final_text = response.text or "✅ Задача выполнена."

                mem["history"].append({"role": "user", "text": user_text})
                mem["history"].append({"role": "model", "text": final_text})
                mem["history"] = mem["history"][-24:]
                save_memory_async(mem)

                return final_text
            except Exception as e:
                last_error = e
                err_str = str(e)
                if any(code in err_str for code in ["503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED"]):
                    if attempt == 0:
                        time.sleep(2)
                        continue
                    break
                elif any(code in err_str for code in ["404", "NOT_FOUND", "400", "INVALID_ARGUMENT"]):
                    break
                else:
                    raise e

    raise last_error

# --- ОБРАБОТКА СООБЩЕНИЙ TELEGRAM ---
@bot.message_handler(commands=["start"])
def handle_start(message):
    user_id = str(message.from_user.id)
    if OWNER_ID and user_id != str(OWNER_ID):
        bot.reply_to(message, "⛔ Доступ закрыт. Я работаю только со своим создателем.")
        return

    mem = load_memory()
    facts_count = len(mem.get("facts", []))
    hist_count = len(mem.get("history", [])) // 2

    bot.reply_to(
        message,
        f"⚡ *Гермес на связи, Босс!*\n"
        f"Твой ID: `{user_id}`\n"
        f"🧠 Память загружена: фактов — {facts_count}, последних диалогов — {hist_count}.\n\n"
        f"Команды:\n"
        f"/reset — очистить текущий диалог (факты останутся)\n"
        f"/clear\\_all — полностью стереть всю память\n\n"
        f"Какая задача?",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=["reset"])
def handle_reset(message):
    user_id = str(message.from_user.id)
    if OWNER_ID and user_id != str(OWNER_ID):
        bot.reply_to(message, "⛔ Доступ закрыт.")
        return

    mem = load_memory()
    mem["history"] = []
    save_memory_async(mem)
    bot.reply_to(message, "🔄 Текущий диалог очищен. Все сохранённые факты и проекты остались в памяти.")

@bot.message_handler(commands=["clear_all"])
def handle_clear_all(message):
    user_id = str(message.from_user.id)
    if OWNER_ID and user_id != str(OWNER_ID):
        bot.reply_to(message, "⛔ Доступ закрыт.")
        return

    global ram_memory
    ram_memory = {"facts": [], "history": []}
    save_memory_async(ram_memory)
    bot.reply_to(message, "🧹 Вся постоянная память и история диалогов полностью очищены.")

@bot.message_handler(func=lambda m: True)
def handle_task(message):
    user_id = str(message.from_user.id)
    if OWNER_ID and user_id != str(OWNER_ID):
        bot.reply_to(message, "⛔ Доступ закрыт.")
        return

    if not message.text:
        bot.reply_to(message, "⚠️ Пока я принимаю только текстовые сообщения.")
        return

    status_msg = bot.reply_to(message, "⏳ Принял задачу. Анализирую и выполняю...")
    try:
        final_text = ask_agent_with_fallback(message.text)

        if len(final_text) > 4000:
            try:
                bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)
            except Exception:
                pass
            for i in range(0, len(final_text), 4000):
                bot.send_message(message.chat.id, final_text[i:i+4000])
        else:
            try:
                bot.edit_message_text(final_text, chat_id=message.chat.id, message_id=status_msg.message_id)
            except Exception:
                bot.send_message(message.chat.id, final_text)
    except Exception as e:
        bot.edit_message_text(
            f"⚠️ Произошел сбой при выполнении: {str(e)}",
            chat_id=message.chat.id,
            message_id=status_msg.message_id
        )

if __name__ == "__main__":
    load_memory()
    threading.Thread(target=run_web, daemon=True).start()
    print("Hermes Bot started with persistent memory...")
    bot.infinity_polling(skip_pending=True)
        
