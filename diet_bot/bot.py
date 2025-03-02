import asyncio
from datetime import datetime, timedelta
import logging
import sys
from os import getenv, path
from tempfile import mktemp
from typing import Optional

from aiogram import Bot, Dispatcher, F, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiohttp import ClientSession
from pydantic import BaseModel, Field
from pydantic_core import from_json

TOKEN = getenv("BOT_TOKEN")
YA_TOKEN = getenv("YA_TOKEN")

if TOKEN is None or YA_TOKEN is None:
    sys.exit(-1)

IAM_TOKENS_URL = "https://iam.api.cloud.yandex.net/iam/v1/tokens"
LAST_TOKEN_NAME = ".token"


class IamToken(BaseModel):
    token: Optional[str] = None
    ttl: datetime = Field(default_factory=datetime.now)

    def valid(self) -> bool:
        if self.token is None:
            return False
        now = datetime.now()
        return now - self.ttl <= timedelta(hours=12)

    async def update(self):
        async with ClientSession() as session:
            async with session.post(
                url=IAM_TOKENS_URL,
                json={"yandexPassportOauthToken": YA_TOKEN},
            ) as resp:
                body = await resp.json()
                self.token = body["iamToken"]
                self.ttl = datetime.now()
                logging.info(f"{self.token} - {self.ttl}")
                with open(LAST_TOKEN_NAME, "w") as last_file:
                    last_file.write(self.model_dump_json())

    async def valid_or_update(self):
        if not self.valid():
            await self.update()


IAM_TOKEN = IamToken()
if path.exists(LAST_TOKEN_NAME):
    with open(LAST_TOKEN_NAME) as last_file:
        IAM_TOKEN = IamToken.model_validate(
            from_json(last_file.read(), allow_partial=False)
        )


bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    await message.answer(f"Hello, {html.bold(message.from_user.full_name)}!")


@dp.message(F.voice)
async def voice_handler(message: Message) -> None:
    filename = mktemp("_diet.ogg")
    logging.info(filename)
    await bot.download(message.voice, filename)
    await IAM_TOKEN.valid_or_update()
    await message.answer(str(message.voice.file_size))


async def main() -> None:
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
