import asyncio
import logging

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 15
MAX_OUTPUT_LENGTH = 5000

async def execute_python(code: str) -> dict:
    """
    Ejecuta código Python en un contenedor Docker aislado.
    Pasa el código por stdin para evitar problemas de montaje de volúmenes.
    """
    try:
        cmd = [
            "docker", "run",
            "--rm",
            "--interactive",
            "--network", "none",
            "--memory", "128m",
            "--cpus", "0.5",
            "python:3.12-slim",
            "python", "-c", code
        ]

        logger.info("Ejecutando código en sandbox...")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            proc.kill()
            return {
                "success": False,
                "output": "",
                "error": f"Timeout: el código tardó más de {TIMEOUT_SECONDS} segundos",
                "exit_code": -1
            }

        output = stdout.decode("utf-8", errors="replace")
        error = stderr.decode("utf-8", errors="replace")

        if len(output) > MAX_OUTPUT_LENGTH:
            output = output[:MAX_OUTPUT_LENGTH] + "\n... (output truncado)"

        return {
            "success": proc.returncode == 0,
            "output": output,
            "error": error if proc.returncode != 0 else "",
            "exit_code": proc.returncode
        }

    except Exception as e:
        logger.error(f"Error en sandbox: {e}")
        return {
            "success": False,
            "output": "",
            "error": str(e),
            "exit_code": -1
        }
