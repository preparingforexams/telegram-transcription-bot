import asyncio
from typing import TYPE_CHECKING

import click
import uvloop

from bot.bot import Bot
from bot.init import initialize

if TYPE_CHECKING:
    from bot.config import Config


@click.group
@click.pass_context
def main(context: click.Context) -> None:
    context.obj = initialize()
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


@main.command
@click.pass_obj
def handle_updates(config: Config) -> None:
    bot = Bot(config)
    bot.run()


if __name__ == "__main__":
    main()
