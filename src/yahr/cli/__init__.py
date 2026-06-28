import logging

import typer

from yahr.cli.commands.ask import ask
from yahr.cli.commands.convert import convert
from yahr.cli.commands.hello import hello
from yahr.cli.commands.serve import serve

app = typer.Typer(
    help="YAHR — Yet Another HR career co-pilot.",
    no_args_is_help=True,
)


@app.callback()
def main():
    """YAHR — Yet Another HR career co-pilot."""
    # ponytail: the a2a-sdk calls logging.basicConfig at import, flipping root to
    # INFO + a RichHandler — so httpx/openai/mcp request lines spam the CLI. Reset
    # to WARNING here (runs after imports); raise the level if you ever need them.
    logging.getLogger().setLevel(logging.WARNING)


app.command()(hello)
app.command()(convert)
app.command()(serve)
app.command()(ask)


if __name__ == "__main__":
    app()
