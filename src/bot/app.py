import asyncio

import click

from bot.config import Config
from bot.init import initialize


@click.group
@click.pass_context
def main(context: click.Context) -> None:
    context.obj = initialize()


@main.command
@click.pass_obj
def handle_updates(config: Config) -> None:
    asyncio.run(TelegramUpdateRouter(app).run())

if __name__ == "__main__":
    main()
