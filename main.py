import os
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
OWNER_ID = os.getenv("OWNER_ID")  # Необязательно: твой ID в Telegram для защиты

bot = telebot.TeleBot(TG_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER (ЧТОБЫ НЕ ПАДАЛ) ---
app = Flask(__name__)

@app.route("/")
def index():
    return "Hermes AI Agent is running 24/7!"

def run_web():
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- ИНСТРУМЕНТЫ («РУКИ» ГЕРМЕСА) ---

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
        repos = [repo.name for repo in g.get_user().get_repos()]
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
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_user().get_repo(repo_name)
        try:
            existing = repo.get_contents(file_path)
            repo.update_file(existing.path, commit_message, content, existing.sha)
            return f"Файл {file_path} успешно обновлен в репозитории {repo_name}."
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

# --- СИСТЕМНАЯ ИНСТРУКЦИЯ И ПАМЯТЬ ---
SYSTEM_PROMPT = """Ты — Гермес, автономный ИИ-агент и правая рука своего создателя (как Джарвис для Тони Старка).
Твои правила работы:
1. Один проект = один отдельный репозиторий на GitHub. Никогда не смешивай разные проекты в одну папку. Имя своего собственного репозитория (Hermes-bot-) не трогай, если тебя прямо не попросили.
2. Когда просят создать сайт: сам придумай название репозитория, вызови create_github_repo, напиши красивый современный код (HTML/CSS/JS в файле index.html) через write_github_file и включи сайт через deploy_github_pages, выдав готовую ссылку.
3. Когда просят починить или проверить другой проект на GitHub: найди репозиторий через list_github_repos, прочитай файлы через read_github_file, найди ошибку и исправь её через write_github_file.
4. Если возникает техническая ошибка при вызове инструмента — прочитай текст ошибки, исправь параметры и попробуй снова до получения рабочего результата.
5. Перед публикацией постов в Telegram-канал или удалением важных данных сначала покажи черновик и спроси разрешение у Босса.
Общайся четко, по делу, с уважением и легкой харизмой Джарвиса."""

TOOLS = [
    web_search,
    list_github_repos,
    create_github_repo,
    read_github_file,
    write_github_file,
    deploy_github_pages,
    publish_to_telegram_channel
]

chat_sessions = {}

def get_chat(user_id):
    if user_id not in chat_sessions:
        chat_sessions[user_id] = ai_client.chats.create(
            model="gemini-3.8-flash",
            config=types.GenerateContentConfig(
               system_instruction=SYSTEM_PROMPT,
                tools=TOOLS,
                temperature=0.4
            )
        )
    return chat_sessions[user_id]

# --- ОБРАБОТКА СООБЩЕНИЙ TELEGRAM ---

@bot.message_handler(commands=["start", "reset"])
def handle_start(message):
    user_id = str(message.from_user.id)
    if OWNER_ID and user_id != str(OWNER_ID):
        bot.reply_to(message, "⛔ Доступ закрыт. Я работаю только со своим создателем.")
        return
    chat_sessions.pop(user_id, None)
    bot.reply_to(
        message,
        f"⚡ **Гермес на связи, Босс!**\nТвой ID: `{user_id}`\n\nЯ готов создавать сайты, управлять репозиториями на GitHub, искать информацию и вести каналы. Какая задача?",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: True)
def handle_task(message):
    user_id = str(message.from_user.id)
    if OWNER_ID and user_id != str(OWNER_ID):
        bot.reply_to(message, "⛔ Доступ закрыт.")
        return

    status_msg = bot.reply_to(message, "⚙️ Принял задачу. Анализирую и выполняю...")
    try:
        chat = get_chat(user_id)
        response = chat.send_message(message.text)
        final_text = response.text or "✅ Задача выполнена."
        
        if len(final_text) > 4000:
            for i in range(0, len(final_text), 4000):
                bot.send_message(message.chat.id, final_text[i:i+4000])
        else:
            bot.edit_message_text(final_text, chat_id=message.chat.id, message_id=status_msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"⚠️ Произошел сбой при выполнении: {str(e)}", chat_id=message.chat.id, message_id=status_msg.message_id)

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    print("Hermes Bot started...")
    bot.infinity_polling(skip_pending=True)
