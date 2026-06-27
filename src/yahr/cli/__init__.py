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


app.command()(hello)
app.command()(convert)
app.command()(serve)
app.command()(ask)


if __name__ == "__main__":
    app()
