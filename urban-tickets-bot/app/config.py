import os
from dataclasses import dataclass

@dataclass
class Settings:
    bot_token: str
    db_url: str
    redis_url: str | None
    admin_chat_id: int | None
    admins: list[int]
    assets_example_path: str
    price_rub: int

def load_settings() -> Settings:
    admins_env = os.getenv("ADMINS", "")
    admins = [int(x.strip()) for x in admins_env.split(",") if x.strip().isdigit()]
    admin_chat_id = os.getenv("ADMIN_CHAT_ID")
    return Settings(
        bot_token=os.environ["BOT_TOKEN"],
        db_url=os.environ["DATABASE_URL"],
        redis_url=os.getenv("REDIS_URL"),
        admin_chat_id=int(admin_chat_id) if admin_chat_id else (admins[0] if admins else None),
        admins=admins,
        assets_example_path=os.getenv("ASSETS_EXAMPLE_PATH", "assets/example_screenshot.png"),
        price_rub=int(os.getenv("PRICE_RUB", "2500")),
    )
