import typer

from yahr.cli.commands.convert import convert
from yahr.cli.commands.hello import hello

app = typer.Typer(
    help="YAHR — Yet Another HR career co-pilot.",
    no_args_is_help=True,
)


@app.callback()
def main():
    """YAHR — Yet Another HR career co-pilot."""


app.command()(hello)
app.command()(convert)


if __name__ == "__main__":
    app()
