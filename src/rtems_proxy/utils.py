import subprocess

import typer


def run_command(
    command: str, interactive=True, error_ok=False, show=False
) -> str | bool:
    """
    Run a command and return the output

    if interactive is true then allow stdin and stdout, return the return code,
    otherwise return True for success and False for failure

    args:

        command: the command to run
        interactive: if True then allow stdin and stdout
        error_OK: if True then do not raise an exception on failure
        show: typer.echo the command output to the console
    """

    p_result = subprocess.run(command, capture_output=not interactive, shell=True)

    if interactive:
        output = error_out = ""
    else:
        output = p_result.stdout.decode()
        error_out = p_result.stderr.decode()

    if interactive:
        result: str | bool = p_result.returncode == 0
    else:
        result = output + error_out

    if p_result.returncode != 0 and not error_ok:
        typer.echo("\nCommand Failed:")
        typer.echo(output)
        typer.echo(error_out)
        raise typer.Exit(1)

    if show:
        typer.echo(output)
        typer.echo(error_out)

    return result
